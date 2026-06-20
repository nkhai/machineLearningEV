import io
import json
import numpy as np
import xgboost as xgb
import torch
import torch.nn as nn
import torch.optim as optim
import pendulum
from collections import defaultdict
from sklearn.preprocessing import StandardScaler
from hdfs import InsecureClient
from fastapi import APIRouter, HTTPException

from api.schemas import TrainRequest
from core.config import HDFS_USER
from core.data_utils import (
    get_hdfs_files_filtered,
    load_data_universal,
    filter_by_modality,
    save_artifacts_to_hdfs,
)
from core.split_and_extract import split_train_test_by_car, extract_features_2d
from core.nn import EnsembleNN
from core.job_manager import submit_job, model_lock

router = APIRouter()

RAW_DATA_DIR = "/raw_data/battery_telemetry_v2"
HDFS_MODEL_DIR = "/models/battery_health_ensemble"
HDFS_IMAGE_DIR = "/models/learning_curve"


def _run_train_pipeline(job, hdfs_url: str):
    """The actual training logic, runs in a background thread."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=60)

    # ── STEP 1: LOAD & SPLIT DATA ──
    job.progress = "Step 1/3: Loading & splitting data..."
    all_train_files = get_hdfs_files_filtered(client, RAW_DATA_DIR)

    target_train_evs = ["EV_012", "EV_013", "EV_014"]
    train_files = [f for f in all_train_files if any(ev in f for ev in target_train_evs)]

    if not train_files:
        raise ValueError("No training files found for target EVs.")

    train_raw = load_data_universal(client, train_files, mode="train")
    train_set, val_set = split_train_test_by_car(train_raw)

    train_chg = filter_by_modality(train_set, is_charge=True)
    train_drv = filter_by_modality(train_set, is_charge=False)
    val_chg = filter_by_modality(val_set, is_charge=True)
    val_drv = filter_by_modality(val_set, is_charge=False)

    # ── STEP 2A: TRAIN XGBOOST (Charging) ──
    job.progress = "Step 2A/3: Training XGBoost (Charging)..."
    X_train_chg, y_train_chg = extract_features_2d(train_chg)
    X_val_chg, y_val_chg = extract_features_2d(val_chg)

    xgb_model_chg = None
    scaler_chg = None
    evals_result_chg = {}
    X_val_chg_scaled = None

    if len(X_train_chg) > 0:
        scaler_chg = StandardScaler()
        X_train_chg_scaled = scaler_chg.fit_transform(X_train_chg)

        dtrain_chg = xgb.DMatrix(X_train_chg_scaled, label=y_train_chg)
        xgb_params = {
            "booster": "gbtree",
            "learning_rate": 0.0001,
            "objective": "reg:squarederror",
            "seed": 168,
            "nthread": -1,
            "device": device.type,
            "tree_method": "hist",
        }

        evals = [(dtrain_chg, "train")]
        if len(X_val_chg) > 0:
            X_val_chg_scaled = scaler_chg.transform(X_val_chg)
            dval_chg = xgb.DMatrix(X_val_chg_scaled, label=y_val_chg)
            evals.append((dval_chg, "val"))

        xgb_model_chg = xgb.train(
            xgb_params, dtrain_chg, num_boost_round=300,
            evals=evals, evals_result=evals_result_chg,
            early_stopping_rounds=50, verbose_eval=50,
        )

    # ── STEP 2B: TRAIN XGBOOST (Driving) ──
    job.progress = "Step 2B/3: Training XGBoost (Driving)..."
    X_train_drv, y_train_drv = extract_features_2d(train_drv)
    X_val_drv, y_val_drv = extract_features_2d(val_drv)

    xgb_model_drv = None
    scaler_drv = None
    evals_result_drv = {}
    X_val_drv_scaled = None

    if len(X_train_drv) > 0:
        scaler_drv = StandardScaler()
        X_train_drv_scaled = scaler_drv.fit_transform(X_train_drv)

        dtrain_drv = xgb.DMatrix(X_train_drv_scaled, label=y_train_drv)
        xgb_params_drv = {
            "booster": "gbtree",
            "learning_rate": 0.0001,
            "objective": "reg:squarederror",
            "seed": 168,
            "nthread": -1,
            "device": device.type,
            "tree_method": "hist",
        }

        evals_drv = [(dtrain_drv, "train")]
        if len(X_val_drv) > 0:
            X_val_drv_scaled = scaler_drv.transform(X_val_drv)
            dval_drv = xgb.DMatrix(X_val_drv_scaled, label=y_val_drv)
            evals_drv.append((dval_drv, "val"))

        xgb_model_drv = xgb.train(
            xgb_params_drv, dtrain_drv, num_boost_round=300,
            evals=evals_drv, evals_result=evals_result_drv,
            early_stopping_rounds=50, verbose_eval=50,
        )

    # ── STEP 2C: TRAIN META-LEARNER (EnsembleNN) ──
    job.progress = "Step 2C/3: Training Meta-Learner (EnsembleNN)..."
    val_preds_chg = defaultdict(list)
    val_preds_drv = defaultdict(list)
    val_true_cap = {}
    nn_model = None

    if xgb_model_chg is not None and X_val_chg_scaled is not None:
        preds_chg = xgb_model_chg.predict(xgb.DMatrix(X_val_chg_scaled))
        for p, (_, meta) in zip(preds_chg, val_chg):
            val_preds_chg[meta["car_id"]].append(p)
            val_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)

    if xgb_model_drv is not None and X_val_drv_scaled is not None:
        preds_drv = xgb_model_drv.predict(xgb.DMatrix(X_val_drv_scaled))
        for p, (_, meta) in zip(preds_drv, val_drv):
            val_preds_drv[meta["car_id"]].append(p)
            val_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)

    meta_X_chg, meta_X_drv, meta_y = [], [], []
    all_val_cars = set(list(val_preds_chg.keys()) + list(val_preds_drv.keys()))

    for car_id in all_val_cars:
        gt = val_true_cap.get(car_id, -1)
        if gt <= 0:
            continue
        p_chg = np.mean(val_preds_chg[car_id]) if car_id in val_preds_chg else None
        p_drv = np.mean(val_preds_drv[car_id]) if car_id in val_preds_drv else None
        if p_chg is not None and p_drv is not None:
            meta_X_chg.append([p_chg])
            meta_X_drv.append([p_drv])
            meta_y.append([gt])

    if len(meta_y) > 0:
        t_chg = torch.tensor(meta_X_chg, dtype=torch.float32).to(device)
        t_drv = torch.tensor(meta_X_drv, dtype=torch.float32).to(device)
        t_y = torch.tensor(meta_y, dtype=torch.float32).to(device)

        nn_model = EnsembleNN().to(device)
        criterion = nn.MSELoss()
        optimizer = optim.Adam(nn_model.parameters(), lr=0.01)

        for epoch in range(300):
            optimizer.zero_grad()
            outputs = nn_model(t_chg, t_drv)
            loss = criterion(outputs, t_y)
            loss.backward()
            optimizer.step()

        # Move back to CPU for saving
        nn_model = nn_model.cpu()

    # ── STEP 3: SAVE MODELS TO HDFS (versioned + write-locked) ──
    job.progress = "Step 3/3: Saving models to HDFS..."

    # Generate a versioned directory to avoid overwriting active models
    vn_now = pendulum.now("Asia/Ho_Chi_Minh")
    version_id = vn_now.format("YYYYMMDD_HHmmss")
    versioned_dir = f"{HDFS_MODEL_DIR}/v_{version_id}"

    # Acquire write lock — blocks until all readers finish
    model_lock.acquire_write()
    try:
        try:
            client.status(versioned_dir)
        except Exception:
            client.makedirs(versioned_dir)

        saved_artifacts = []

        if xgb_model_chg is not None:
            save_artifacts_to_hdfs(client, versioned_dir, "chg", xgb_model_chg, scaler=scaler_chg)
            saved_artifacts.append(f"{versioned_dir}/xgb_model_chg.json")
            saved_artifacts.append(f"{versioned_dir}/scaler_chg.joblib")

        if xgb_model_drv is not None:
            save_artifacts_to_hdfs(client, versioned_dir, "drv", xgb_model_drv, scaler=scaler_drv)
            saved_artifacts.append(f"{versioned_dir}/xgb_model_drv.json")
            saved_artifacts.append(f"{versioned_dir}/scaler_drv.joblib")

        if nn_model is not None:
            buffer = io.BytesIO()
            torch.save(nn_model.state_dict(), buffer)
            buffer.seek(0)
            pth_path = f"{versioned_dir}/ensemble_nn.pth"
            client.write(pth_path, buffer, overwrite=True)
            saved_artifacts.append(pth_path)

        # Update the "latest" pointer so predict knows which version to load
        latest_info = json.dumps({
            "version": version_id,
            "path": versioned_dir,
            "created_at": vn_now.to_iso8601_string(),
        }).encode("utf-8")
        client.write(f"{HDFS_MODEL_DIR}/latest.json", data=latest_info, overwrite=True)
    finally:
        model_lock.release_write()

    hdfs_browse = f"{hdfs_url}/explorer.html#"
    return {
        "model_directory": f"{hdfs_browse}{versioned_dir}",
        "version": version_id,
        "saved_files": [f"{hdfs_browse}{p}" for p in saved_artifacts],
        "train_cars": target_train_evs,
    }


@router.post("/train")
def start_train(request: TrainRequest):
    """
    Submit a training job to run in background (non-blocking).

    Returns immediately with a job_id to poll status.
    """
    hdfs_url = request.HDFS_URL

    # Quick HDFS connectivity check before submitting
    try:
        client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=10)
        client.status("/", strict=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to HDFS at {hdfs_url}: {e}")

    job = submit_job("train", hdfs_url, _run_train_pipeline, hdfs_url)

    return {
        "status": "accepted",
        "message": "Training job submitted. Use /api/v1/jobs/{job_id} to check progress.",
        "job_id": job.job_id,
        "hdfs_url_used": hdfs_url,
    }
