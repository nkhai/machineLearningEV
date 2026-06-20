import io
import json
import os
import re
import numpy as np
import xgboost as xgb
import torch
from collections import defaultdict
from datetime import datetime, timedelta
from sklearn.metrics import mean_squared_error
from hdfs import InsecureClient
from fastapi import APIRouter, HTTPException

from api.schemas import PredictRequest
from fastapi import APIRouter, HTTPException, Depends, Request

from core.config import HDFS_USER, NUM_FILES_LIMIT
from core.auth import get_user, azure_scheme, AUTH_ENABLED, TEMPLATE_USER_ID
from core.data_utils import (
    get_hdfs_files_filtered,
    load_data_universal,
    filter_by_modality,
    save_csv_hdfs,
    load_artifacts_from_hdfs,
)
from core.split_and_extract import extract_features_2d
from core.nn import EnsembleNN
from core.job_manager import submit_job, model_lock

router = APIRouter()

INFERENCE_BASE_DIR = "/raw_data/battery_telemetry_v4"
HDFS_MODEL_DIR = "/models/battery_health_ensemble"
HDFS_IMAGE_DIR = "/models/learning_curve"


def _resolve_model_dir(client):
    """Read latest.json to find the current model version directory."""
    latest_path = f"{HDFS_MODEL_DIR}/latest.json"
    try:
        with client.read(latest_path) as reader:
            latest_info = json.loads(reader.read().decode("utf-8"))
        return latest_info["path"]
    except Exception:
        # Fallback: no versioning yet, use base dir (backward-compatible)
        return HDFS_MODEL_DIR


def _run_predict_pipeline(job, hdfs_url: str, car_ids: list, predict_date: str):
    """The actual inference logic, runs in a background thread."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=60)
    saved_outputs = []

    # ── STEP 1: LOAD MODELS & SCALERS FROM HDFS (read-locked) ──
    job.progress = "Step 1/4: Loading models from HDFS..."

    model_lock.acquire_read()
    try:
        model_dir = _resolve_model_dir(client)
        xgb_model_chg, scaler_chg = load_artifacts_from_hdfs(client, model_dir, "chg")
        xgb_model_drv, scaler_drv = load_artifacts_from_hdfs(client, model_dir, "drv")

        nn_model = EnsembleNN()
        try:
            with client.read(f"{model_dir}/ensemble_nn.pth") as reader:
                model_bytes = reader.read()
            buffer = io.BytesIO(model_bytes)
            nn_model.load_state_dict(torch.load(buffer, map_location=device, weights_only=True))
            nn_model.to(device)
            nn_model.eval()
        except Exception:
            nn_model = None
    finally:
        model_lock.release_read()

# ── STEP 2: LOAD INFERENCE DATA ──
    job.progress = "Step 2/4: Loading inference data..."
    all_inf_files = get_hdfs_files_filtered(client, INFERENCE_BASE_DIR, limit=NUM_FILES_LIMIT)

    # Filter by requested car_ids
    inf_files = [f for f in all_inf_files if any(ev in f for ev in car_ids)]

    if not inf_files:
        raise ValueError(f"No inference data found for target EVs on HDFS.")

            # --- VALID DATE SEARCH LOGIC BY READING FILE CONTENT ---
    final_inf_files = []
    fallback_dates_used = []

        # Group files by car
    car_file_map = defaultdict(list)
    for fp in inf_files:
        for cid in car_ids:
            if cid in fp:
                car_file_map[cid].append(fp)

    for cid in car_ids:
        files_for_car = car_file_map.get(cid, [])
        if not files_for_car:
            continue

        found_valid_data = False

        # Group files by car and date
        date_to_files = defaultdict(list)
        for fp in files_for_car:
            m = re.search(r'(\d{8})', os.path.basename(fp))
            if m:
                try:
                    fd = datetime.strptime(m.group(1), "%Y%m%d")
                    date_to_files[fd].append(fp)
                except ValueError:
                    pass
        
        if not date_to_files:
            continue

        if predict_date.lower() != "latest":
            # --- CASE 1: FIND BY SPECIFIC DATE ---
            try:
                target_date = datetime.strptime(predict_date, "%Y%m%d")
                candidate_files = date_to_files.get(target_date, [])
            except ValueError:
                candidate_files = []

            if candidate_files:
                # Try loading to check if there's valid data inside
                temp_raw = load_data_universal(client, candidate_files, mode="inference", pad_short_windows=True)
                if temp_raw:
                    final_inf_files.extend(candidate_files)
                    has_chg = any(meta.get("charger_connected") == 1 for _, meta, _ in temp_raw)
                    has_drv = any(meta.get("charger_connected") == 0 for _, meta, _ in temp_raw)
                    dual_label = "dual" if (has_chg and has_drv) else "single"
                    fallback_dates_used.append(f"{predict_date} ({dual_label})")
                    found_valid_data = True
        else:
            # --- CASE 2: "LATEST" - INDEPENDENTLY FIND NEWEST FOR CHARGING AND DRIVING ---
            sorted_dates = sorted(date_to_files.keys(), reverse=True)
            
            found_chg = False
            found_drv = False
            chg_files = []
            drv_files = []
            chg_date_str = ""
            drv_date_str = ""
            
            # Scan from newest date backward
            for fd in sorted_dates:
                candidate_files = date_to_files[fd]
                temp_raw = load_data_universal(client, candidate_files, mode="inference", pad_short_windows=True)
                
                if not temp_raw:
                    continue # Skip this date if no valid data can be extracted
                
                # If charging file not found yet, check if this date has charging data
                if not found_chg:
                    if any(meta.get("charger_connected") == 1 for _, meta, _ in temp_raw):
                        chg_files = candidate_files
                        chg_date_str = fd.strftime('%Y%m%d')
                        found_chg = True
                        
                # If driving file not found yet, check if this date has driving data
                if not found_drv:
                    if any(meta.get("charger_connected") == 0 for _, meta, _ in temp_raw):
                        drv_files = candidate_files
                        drv_date_str = fd.strftime('%Y%m%d')
                        found_drv = True
                
                # If both charging and driving found (may be on different dates), stop searching for this car
                if found_chg and found_drv:
                    break
            
            # Combine file lists (use set to remove duplicates if charging and driving are on the same date)
            combined_files = list(set(chg_files + drv_files))
            
            if combined_files:
                final_inf_files.extend(combined_files)
                label_parts = []
                if found_chg: label_parts.append(f"Chg:{chg_date_str}")
                if found_drv: label_parts.append(f"Drv:{drv_date_str}")
                fallback_dates_used.append(" + ".join(label_parts))
                found_valid_data = True

        if not found_valid_data:
            print(f"[Warning] Could not find any valid snippets for {cid}.")

    if not final_inf_files:
        raise ValueError(f"No valid inference snippets found for any target EVs.")

    print(f"[Info] Using dates: {dict(zip(car_ids, fallback_dates_used))}")

    # Reload actual data (with pad_short_windows=True enabled)
    inf_raw = load_data_universal(client, final_inf_files, mode="inference", pad_short_windows=True)

    inf_chg = filter_by_modality(inf_raw, is_charge=True)
    inf_drv = filter_by_modality(inf_raw, is_charge=False)

    # ── STEP 3: PREDICT ──
    job.progress = "Step 3/4: Running predictions..."
    inf_preds_chg = defaultdict(list)
    inf_preds_drv = defaultdict(list)
    inf_true_cap = {}
    inf_mileage = {}

    if inf_chg and xgb_model_chg is not None:
        X_inf_chg, _ = extract_features_2d(inf_chg)
        if scaler_chg is not None:
            X_inf_chg = scaler_chg.transform(X_inf_chg)
        preds_chg = xgb_model_chg.predict(xgb.DMatrix(X_inf_chg))
        for p, (_, meta, _) in zip(preds_chg, inf_chg):
            inf_preds_chg[meta["car_id"]].append(p)
            inf_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)
            inf_mileage[meta["car_id"]] = max(inf_mileage.get(meta["car_id"], 0), meta.get("mileage_km", 0))

    if inf_drv and xgb_model_drv is not None:
        X_inf_drv, _ = extract_features_2d(inf_drv)
        if scaler_drv is not None:
            X_inf_drv = scaler_drv.transform(X_inf_drv)
        preds_drv = xgb_model_drv.predict(xgb.DMatrix(X_inf_drv))
        for p, (_, meta, _) in zip(preds_drv, inf_drv):
            inf_preds_drv[meta["car_id"]].append(p)
            inf_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)
            inf_mileage[meta["car_id"]] = max(inf_mileage.get(meta["car_id"], 0), meta.get("mileage_km", 0))

    # ── STEP 4: ENSEMBLE & BUILD RESULTS ──
    job.progress = "Step 4/4: Ensemble & saving results..."
    final_results = []
    all_inf_cars = set(list(inf_preds_chg.keys()) + list(inf_preds_drv.keys()))
    has_ground_truth = False
    metrics = {}

    for car_id in all_inf_cars:
        gt = inf_true_cap.get(car_id, -1)
        if gt > 0:
            has_ground_truth = True

        p_chg = np.mean(inf_preds_chg[car_id]) if car_id in inf_preds_chg else None
        p_drv = np.mean(inf_preds_drv[car_id]) if car_id in inf_preds_drv else None

        if p_chg is not None and p_drv is not None:
            if nn_model is not None:
                t_chg = torch.tensor([[p_chg]], dtype=torch.float32).to(device)
                t_drv = torch.tensor([[p_drv]], dtype=torch.float32).to(device)
                with torch.no_grad():
                    final_pred = nn_model(t_chg, t_drv).item()
                method = "Ensemble (Neural Network)"
            else:
                final_pred = (p_chg + p_drv) / 2.0
                method = "Ensemble (Simple Avg Fallback)"
        elif p_chg is not None:
            final_pred = p_chg
            method = "XGB (Charging Only)"
        elif p_drv is not None:
            final_pred = p_drv
            method = "XGB (Driving Only)"
        else:
            continue

        err = float(final_pred - gt) if gt > 0 else 0.0

        final_results.append([
            car_id, inf_mileage.get(car_id, 0), method,
            float(gt) if gt > 0 else -1.0,
            float(p_chg) if p_chg else -1.0,
            float(p_drv) if p_drv else -1.0,
            float(final_pred), err,
        ])

    # ── COMPUTE METRICS ──
    if has_ground_truth:
        fair_comp = [r for r in final_results if r[3] > 0 and r[4] > 0 and r[5] > 0]
        if fair_comp:
            true_vals = [r[3] for r in fair_comp]
            metrics = {
                "rmse_charging": float(np.sqrt(mean_squared_error(true_vals, [r[4] for r in fair_comp]))),
                "rmse_driving": float(np.sqrt(mean_squared_error(true_vals, [r[5] for r in fair_comp]))),
                "rmse_ensemble": float(np.sqrt(mean_squared_error(true_vals, [r[6] for r in fair_comp]))),
                "num_cars_compared": len(fair_comp),
            }

        all_valid = [r for r in final_results if r[3] > 0]
        if all_valid:
            metrics["rmse_overall"] = float(np.sqrt(mean_squared_error(
                [r[3] for r in all_valid], [r[6] for r in all_valid]
            )))

    # ── SAVE RESULTS CSV TO HDFS ──
    header = ["car_id", "max_mileage_km", "prediction_method", "gt_capacity",
              "pred_xgboost_chg", "pred_xgboost_drv", "final_ensemble_pred", "error"]
    result_path = save_csv_hdfs(final_results, header, "inference_ensemble_result")
    if result_path:
        saved_outputs.append(result_path)

    hdfs_browse = f"{hdfs_url}/explorer.html#"
    return {
        "result_csv_directory": f"{hdfs_browse}/output_data",
        "models_loaded_from": f"{hdfs_browse}{model_dir}",
        "cars_predicted": [r[0] for r in final_results],
        "predictions": [
            {
                "car_id": r[0],
                "max_mileage_km": str(r[1]),
                "prediction_method": r[2],
                "gt_capacity": str(r[3]),
                "pred_xgboost_chg": str(r[4]),
                "pred_xgboost_drv": str(r[5]),
                "final_ensemble_pred": str(r[6]),
                "error": str(r[7]),
            }
            for r in final_results
        ],
        "metrics": metrics,
        "saved_files": [f"{hdfs_browse}{p}" for p in saved_outputs],
    }


# Create a dynamic dependency based on environment variable
auth_deps = [Depends(azure_scheme)] if AUTH_ENABLED else []

# Attach auth_deps to endpoint
@router.post("/predict", dependencies=auth_deps)
def start_predict(
    request: PredictRequest, 
    fastapi_req: Request # Dùng biến này để lấy HTTP request gốc
):
    """
    Submit a prediction/inference job to run in background (non-blocking).
    """
    hdfs_url = request.HDFS_URL
    car_ids = request.car_ids
    predict_date = request.predict_date

    # Get user_id from token or use template user
    # Lấy từ Token nếu bật Auth, ngược lại lấy trực tiếp từ request body
    user_id = get_user(fastapi_req).id if AUTH_ENABLED else request.user_id

    # Quick HDFS connectivity check before submitting
    try:
        client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=10)
        client.status("/", strict=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to HDFS at {hdfs_url}: {e}")

    # Validate car_ids exist in DB with use_to_predict=True
    from core.database import SessionLocal
    from core.models import Vehicle
    db = SessionLocal()
    try:
        db_cars = db.query(Vehicle).filter(Vehicle.car_id.in_(car_ids), Vehicle.use_to_predict == True).all()
        found_ids = {v.car_id for v in db_cars}
    finally:
        db.close()

    missing = set(car_ids) - found_ids
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cars not found or use_to_predict=False: {list(missing)}. "
                   f"Only cars with use_to_predict=True can be predicted."
        )

    # TRUYỀN USER_ID XUỐNG DATABASE
    job = submit_job(
        "predict", 
        hdfs_url, 
        _run_predict_pipeline, 
        hdfs_url, 
        car_ids, 
        predict_date, 
        user_id=user_id # <--- RECORD USER
    )

    return {
        "status": "accepted",
        "message": "Prediction job submitted. Use /api/v1/jobs/{job_id} to check progress.",
        "job_id": job.job_id,
        "hdfs_url_used": hdfs_url,
        "car_ids": car_ids,
        "predict_date": predict_date,
        "user_id": user_id
    }