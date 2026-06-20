import json
import numpy as np
import torch
import xgboost as xgb
import pendulum
from sklearn.preprocessing import StandardScaler
from hdfs import InsecureClient
from fastapi import APIRouter, HTTPException, Depends, Request

from api.schemas import TrainRequest
from core.config import HDFS_USER
from core.auth import get_user, azure_scheme, AUTH_ENABLED, TEMPLATE_USER_ID
from core.data_utils import (
    get_hdfs_files_filtered,
    load_data_universal,
    save_artifacts_to_hdfs,
)
from core.split_and_extract import split_train_test_by_car, extract_features_2d
from core.job_manager import submit_job, model_lock

router = APIRouter()

SAMPLED_DATA_DIR = "/raw_sample_data/sampled_training"
HDFS_MODEL_DIR = "/models/battery_health_xgb"


def _run_train_pipeline(job, hdfs_url: str):
    """Train a single XGBoost model on all data (charging + driving combined)."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=60)

    # ── STEP 1: LOAD & SPLIT DATA ──
    job.progress = "Step 1/3: Loading & splitting data..."

    all_sampled_files = get_hdfs_files_filtered(client, SAMPLED_DATA_DIR)
    train_files = [f for f in all_sampled_files if f.endswith(".csv")]

    if not train_files:
        raise ValueError(f"No training files found in {SAMPLED_DATA_DIR}. Please run the Sampler script first.")

    train_raw = load_data_universal(client, train_files, mode="train")

    target_train_evs = list(set([meta["car_id"] for _, meta, _ in train_raw]))

    train_set, val_set = split_train_test_by_car(train_raw)

    # No modality split - use all data together
    if len(train_set) == 0:
        raise ValueError("No training samples after splitting by car.")
    if len(val_set) == 0:
        raise ValueError("No validation samples after splitting by car.")

    # ── STEP 2: TRAIN SINGLE XGBOOST ──
    job.progress = "Step 2/3: Training XGBoost on combined data..."

    X_train, y_train = extract_features_2d(train_set)
    X_val, y_val = extract_features_2d(val_set)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)

    dtrain = xgb.DMatrix(X_train_scaled, label=y_train)

    xgb_params = {
        "booster": "gbtree",
        "learning_rate": 0.05,
        "objective": "reg:squarederror",
        "seed": 168,
        "nthread": -1,
        "device": device.type,
        "tree_method": "hist",
        "max_depth": 8,
    }

    evals = [(dtrain, "train")]
    X_val_scaled = scaler.transform(X_val)
    dval = xgb.DMatrix(X_val_scaled, label=y_val)
    evals.append((dval, "val"))

    evals_result = {}
    xgb_model = xgb.train(
        xgb_params, dtrain, num_boost_round=300,
        evals=evals, evals_result=evals_result,
        early_stopping_rounds=50, verbose_eval=50,
    )

    # ── STEP 3: SAVE MODELS TO HDFS (versioned + write-locked) ──
    job.progress = "Step 3/3: Saving model to HDFS..."

    vn_now = pendulum.now("Asia/Ho_Chi_Minh")
    version_id = vn_now.format("YYYYMMDD_HHmmss")
    versioned_dir = f"{HDFS_MODEL_DIR}/v_{version_id}"

    model_lock.acquire_write()
    try:
        try:
            client.status(versioned_dir)
        except Exception:
            client.makedirs(versioned_dir)

        saved_artifacts = []

        save_artifacts_to_hdfs(client, versioned_dir, "xgb", xgb_model, scaler=scaler)
        saved_artifacts.append(f"{versioned_dir}/xgb_model_xgb.json")
        saved_artifacts.append(f"{versioned_dir}/scaler_xgb.joblib")

        # Update the "latest" pointer
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


auth_deps = [Depends(azure_scheme)] if AUTH_ENABLED else []

@router.post("/xgb_train", dependencies=auth_deps)
def start_xgb_train(
    request: TrainRequest,
    fastapi_req: Request
):
    """Submit a training job for single XGBoost model on combined charging+driving data."""
    hdfs_url = request.HDFS_URL
    user_id = get_user(fastapi_req).id if AUTH_ENABLED else request.user_id

    try:
        client = InsecureClient(hdfs_url, user=HDFS_USER, timeout=10)
        client.status("/", strict=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot connect to HDFS at {hdfs_url}: {e}")

    job = submit_job(
        "xgb_train",
        hdfs_url,
        _run_train_pipeline,
        hdfs_url,
        user_id=user_id
    )

    return {
        "status": "accepted",
        "message": "XGBoost training job submitted. Use /api/v1/jobs/{job_id} to check progress.",
        "job_id": job.job_id,
        "hdfs_url_used": hdfs_url,
        "user_id": user_id
    }
