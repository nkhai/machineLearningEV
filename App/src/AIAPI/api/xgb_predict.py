import io
import json
import os
import re
import joblib
import numpy as np
import xgboost as xgb
import torch
from collections import defaultdict
from datetime import datetime
from hdfs import InsecureClient
from sklearn.metrics import mean_squared_error
from fastapi import APIRouter, HTTPException, Depends, Request

from api.schemas import PredictRequest

from core.config import HDFS_USER, NUM_FILES_LIMIT
from core.auth import get_user, azure_scheme, AUTH_ENABLED, TEMPLATE_USER_ID
from core.data_utils import (
    get_hdfs_files_filtered,
    load_data_universal,
    save_csv_hdfs,
    load_artifacts_from_hdfs
)
from core.split_and_extract import extract_features_2d
from core.job_manager import submit_job, model_lock

router = APIRouter()

INFERENCE_BASE_DIR = "/raw_data/battery_telemetry_v4"
HDFS_MODEL_DIR = "/models/battery_health_xgb"


def _resolve_model_dir(client):
    """Read latest.json to find the current model version directory."""
    latest_path = f"{HDFS_MODEL_DIR}/latest.json"
    try:
        with client.read(latest_path) as reader:
            latest_info = json.loads(reader.read().decode("utf-8"))
        return latest_info["path"]
    except Exception:
        return HDFS_MODEL_DIR


def _run_predict_pipeline(job, hdfs_url: str, car_ids: list, predict_date: str):
    """Simple inference with a single XGBoost model on combined data."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=60)
    saved_outputs = []

    # ── STEP 1: LOAD MODEL & SCALER FROM HDFS (read-locked) ──
    job.progress = "Step 1/3: Loading XGBoost model from HDFS..."

    model_lock.acquire_read()
    try:
        model_dir = _resolve_model_dir(client)
        
        # Use helper function instead of manual reading
        xgb_model, scaler = load_artifacts_from_hdfs(client, model_dir, "xgb")

        if xgb_model is None:
            raise ValueError(f"XGBoost model not found at {model_dir}")
    finally:
        model_lock.release_read()

    # ── STEP 2: LOAD INFERENCE DATA ──

    # ── STEP 2: LOAD INFERENCE DATA ──
    job.progress = "Step 2/3: Loading inference data..."
    all_inf_files = get_hdfs_files_filtered(client, INFERENCE_BASE_DIR, limit=NUM_FILES_LIMIT)

    inf_files = [f for f in all_inf_files if any(ev in f for ev in car_ids)]

    if not inf_files:
        raise ValueError(f"No inference data found for target EVs on HDFS.")

    # Group files by car and by date
    car_file_map = defaultdict(list)
    for fp in inf_files:
        for cid in car_ids:
            if cid in fp:
                car_file_map[cid].append(fp)

    # Find valid files matching the requested date (or latest)
    final_inf_files = []
    fallback_dates_used = []

    for cid in car_ids:
        files_for_car = car_file_map.get(cid, [])
        if not files_for_car:
            continue

        found_valid_data = False

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
            try:
                target_date = datetime.strptime(predict_date, "%Y%m%d")
                candidate_files = date_to_files.get(target_date, [])
            except ValueError:
                candidate_files = []

            if candidate_files:
                temp_raw = load_data_universal(client, candidate_files, mode="inference", pad_short_windows=True)
                if temp_raw:
                    final_inf_files.extend(candidate_files)
                    fallback_dates_used.append(f"{predict_date} (all)")
                    found_valid_data = True
        else:
            sorted_dates = sorted(date_to_files.keys(), reverse=True)

            found_any = False
            for fd in sorted_dates:
                candidate_files = date_to_files[fd]
                temp_raw = load_data_universal(client, candidate_files, mode="inference", pad_short_windows=True)

                if not temp_raw:
                    continue

                final_inf_files.extend(candidate_files)
                fallback_dates_used.append(fd.strftime('%Y%m%d'))
                found_any = True
                break

            if not found_any:
                print(f"[Warning] Could not find any valid snippets for {cid}.")

        if not found_valid_data and predict_date.lower() == "latest":
            pass  # Already handled above

    if not final_inf_files:
        raise ValueError(f"No valid inference snippets found for any target EVs.")

    print(f"[Info] Using dates: {dict(zip(car_ids, fallback_dates_used))}")

    # Load all data together (no modality split)
    inf_raw = load_data_universal(client, final_inf_files, mode="inference", pad_short_windows=True)

    if not inf_raw:
        raise ValueError("No valid snippets extracted after loading data.")

    # ── STEP 3: PREDICT ──
    job.progress = "Step 3/3: Running predictions..."

    X_inf, _ = extract_features_2d(inf_raw)
    if scaler is not None:
        X_inf = scaler.transform(X_inf)

    dinf = xgb.DMatrix(X_inf)
    preds = xgb_model.predict(dinf)

    # Group predictions by car
    inf_preds = defaultdict(list)
    inf_true_cap = {}
    inf_mileage = {}

    for p, (_, meta, _) in zip(preds, inf_raw):
        cid = meta["car_id"]
        inf_preds[cid].append(p)
        inf_true_cap[cid] = meta.get("actual_max_capacity_Ah", -1)
        inf_mileage[cid] = max(inf_mileage.get(cid, 0), meta.get("mileage_km", 0))

    # Build results
    final_results = []
    has_ground_truth = False

    for car_id in inf_preds:
        gt = inf_true_cap.get(car_id, -1)
        if gt > 0:
            has_ground_truth = True

        p_mean = np.mean(inf_preds[car_id])
        err = float(p_mean - gt) if gt > 0 else 0.0

        final_results.append([
            car_id,
            inf_mileage.get(car_id, 0),
            "XGBoost (Combined)",
            float(gt) if gt > 0 else -1.0,
            float(p_mean),
            err,
        ])

    # Compute metrics
    metrics = {}
    if has_ground_truth:
        all_valid = [r for r in final_results if r[3] > 0]
        if all_valid:
            metrics["rmse_overall"] = float(np.sqrt(mean_squared_error(
                [r[3] for r in all_valid], [r[4] for r in all_valid]
            )))
            metrics["num_cars_compared"] = len(all_valid)

    # Save results CSV to HDFS
    header = ["car_id", "max_mileage_km", "prediction_method", "gt_capacity",
              "final_pred", "error"]
    result_path = save_csv_hdfs(final_results, header, "inference_xgb_result")
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
                "final_pred": str(r[4]),
                "error": str(r[5]),
            }
            for r in final_results
        ],
        "metrics": metrics,
        "saved_files": [f"{hdfs_browse}{p}" for p in saved_outputs],
    }


auth_deps = [Depends(azure_scheme)] if AUTH_ENABLED else []

@router.post("/xgb_predict", dependencies=auth_deps)
def start_xgb_predict(
    request: PredictRequest,
    fastapi_req: Request
):
    """Submit a prediction job using the simple XGBoost model on combined data."""
    hdfs_url = request.HDFS_URL
    car_ids = request.car_ids
    predict_date = request.predict_date
    user_id = get_user(fastapi_req).id if AUTH_ENABLED else request.user_id

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

    job = submit_job(
        "xgb_predict",
        hdfs_url,
        _run_predict_pipeline,
        hdfs_url,
        car_ids,
        predict_date,
        user_id=user_id
    )

    return {
        "status": "accepted",
        "message": "XGBoost prediction job submitted. Use /api/v1/jobs/{job_id} to check progress.",
        "job_id": job.job_id,
        "hdfs_url_used": hdfs_url,
        "car_ids": car_ids,
        "predict_date": predict_date,
        "user_id": user_id
    }
