import io
import json
import numpy as np
import xgboost as xgb
import torch
from collections import defaultdict
from sklearn.metrics import mean_squared_error
from hdfs import InsecureClient
from fastapi import APIRouter, HTTPException

from api.schemas import TrainRequest

from core.config import HDFS_USER, NUM_FILES_LIMIT
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

INFERENCE_BASE_DIR = "/raw_data/battery_telemetry_v2"
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


def _run_predict_pipeline(job, hdfs_url: str):
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

    target_inf_evs = ["EV_015", "EV_016"]
    inf_files = [f for f in all_inf_files if any(ev in f for ev in target_inf_evs)]

    if not inf_files:
        raise ValueError("No inference data found for target EVs on HDFS.")

    inf_raw = load_data_universal(client, inf_files, mode="inference")
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
        for p, (_, meta) in zip(preds_chg, inf_chg):
            inf_preds_chg[meta["car_id"]].append(p)
            inf_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)
            inf_mileage[meta["car_id"]] = max(inf_mileage.get(meta["car_id"], 0), meta.get("mileage_km", 0))

    if inf_drv and xgb_model_drv is not None:
        X_inf_drv, _ = extract_features_2d(inf_drv)
        if scaler_drv is not None:
            X_inf_drv = scaler_drv.transform(X_inf_drv)
        preds_drv = xgb_model_drv.predict(xgb.DMatrix(X_inf_drv))
        for p, (_, meta) in zip(preds_drv, inf_drv):
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


@router.post("/predict")
def start_predict(request: TrainRequest):
    """
    Submit a prediction/inference job to run in background (non-blocking).

    Returns immediately with a job_id to poll status.
    """
    hdfs_url = request.HDFS_URL

    # Quick HDFS connectivity check before submitting
    try:
        client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=10)
        client.status("/", strict=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to HDFS at {hdfs_url}: {e}")

    job = submit_job("predict", hdfs_url, _run_predict_pipeline, hdfs_url)

    return {
        "status": "accepted",
        "message": "Prediction job submitted. Use /api/v1/jobs/{job_id} to check progress.",
        "job_id": job.job_id,
        "hdfs_url_used": hdfs_url,
    }
