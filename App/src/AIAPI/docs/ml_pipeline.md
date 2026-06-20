# AIAPI Machine Learning Pipeline

## Overview

The `AIAPI/` directory contains a FastAPI backend that serves **two distinct ML pipelines** for EV battery health prediction (maximum capacity estimation in Ah):

1. **Stacking Ensemble** — Two XGBoost models (charging + driving) + EnsembleNN meta-learner
2. **Simple XGBoost** — Single XGBoost model trained on combined charging + driving data

Both pipelines ingest telemetry from HDFS, extract time-windowed features, train/predict asynchronously via background jobs, and persist models to versioned HDFS directories. The system uses a `ReadWriteLock` for concurrent model I/O safety and persists job metadata and prediction results to PostgreSQL.

---

## Project Structure

```
AIAPI/
├── main.py                     # FastAPI entry point, registers all routers
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container build
├── docker-compose.yaml         # Docker orchestration
├── .env / .env.example         # Environment configuration
│
├── api/                        # Route handlers (ML pipeline endpoints)
│   ├── __init__.py
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── train_pipeline.py       # Stacking ensemble TRAINING endpoint (/train)
│   ├── train.py                # Stacking ensemble INFERENCE endpoint (/predict)
│   ├── xgb_train.py            # Simple XGBoost TRAINING endpoint (/xgb_train)
│   ├── xgb_predict.py          # Simple XGBoost INFERENCE endpoint (/xgb_predict)
│   ├── jobs.py                 # Job status/listing endpoints
│   └── vehicles.py             # Vehicle CRUD + prediction history
│
├── core/                       # Shared core utilities
│   ├── __init__.py
│   ├── config.py               # Global config (window size, feature columns, HDFS paths)
│   ├── database.py             # DB session bootstrap
│   ├── models.py               # SQLAlchemy ORM models (users, vehicles, sessions, predict_infos)
│   ├── auth.py                 # Azure AD authentication
│   ├── job_manager.py          # ThreadPoolExecutor + ReadWriteLock + DB persistence
│   ├── nn.py                   # EnsembleNN (meta-learner neural network)
│   ├── data_utils.py           # HDFS I/O, data loading, artifact save/load
│   ├── snippetbuffer.py        # Raw CSV-to-windowed-sample buffer (snippet extraction)
│   └── split_and_extract.py    # Train/val splitting, feature extraction helpers
│
└── docs/                       # Documentation
    ├── ml_pipeline.md          # This file
    ├── api_usage_flow.png
    ├── auth_flow.png
    ├── db_schema.png
    ├── generate_flow_diagrams.py
    └── generate_db_diagram.py
```

---

## Two ML Approaches

### Approach 1: Stacking Ensemble (2 XGBoost + EnsembleNN)

**Files:** `api/train_pipeline.py` (training), `api/train.py` (inference)

This is the more sophisticated approach using a **three-level stacking ensemble**:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    Stacking Ensemble Architecture                         │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │  Level 1 — Base Models: Two XGBoost Models                        │   │
│  │                                                                   │   │
│  │  ┌──────────────────────┐    ┌──────────────────────┐            │   │
│  │  │ XGBoost-Charging     │    │ XGBoost-Driving      │            │   │
│  │  │ (charger_connected=1)│    │ (charger_connected=0)│            │   │
│  │  │                      │    │                      │            │   │
│  │  │ lr=0.05, max_depth=N │    │ lr=0.05, max_depth=8 │            │   │
│  │  │ 300 rounds, early     │    │ 300 rounds, early    │            │   │
│  │  │   stopping=50         │    │   stopping=50        │            │   │
│  │  └──────────┬───────────┘    └──────────┬───────────┘            │   │
│  │             │                            │                        │   │
│  │             ▼                            ▼                        │   │
│  │        pred_chg                      pred_drv                    │   │
│  └─────────────┼────────────────────────────┼───────────────────────┘   │
│                │                            │                           │
│                ▼                            ▼                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Level 2 — Meta-Learner: EnsembleNN (PyTorch)                   │   │
│  │                                                                 │   │
│  │  Input: [mean(pred_chg), mean(pred_drv)] → 2 features           │   │
│  │    Linear(2, 32) → ReLU → Linear(32, 16) → ReLU → Linear(16,1) │   │
│  │         │                                                        │   │
│  │         ▼                                                        │   │
│  │  Output: final battery capacity prediction (Ah)                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │  Fallback Logic                                                   │   │
│  │  • Both modalities + NN available  → NN(pred_chg, pred_drv)       │   │
│  │  • Both modalities, no NN          → (pred_chg + pred_drv) / 2    │   │
│  │  • Charging only                   → pred_chg                     │   │
│  │  • Driving only                    → pred_drv                     │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

**Training Flow (`train_pipeline.py`):**

```
[HDFS: /raw_sample_data/sampled_training/*.csv]
        │
        ▼
  load_data_universal() → GlobalSnippetBuffer → windowed samples
        │
        ▼
  split_train_test_by_car()        -- 80% train / 20% val (by car identity)
        │
        ▼
  filter_by_modality()
        ├─ charger_connected=1 → XGBoost-Charging
        └─ charger_connected=0 → XGBoost-Driving
        │
        ▼
  extract_features_2d()  -- flatten 2D windows → 1D feature vector (128 * 7 = 928 dims)
        │
        ▼
  StandardScaler + xgb.train() (both modalities independently)
        │
        ▼
  EnsembleNN Meta-Learner Training:
    1. Run both XGBoost models on validation set → per-car predictions
    2. Average per modality per car: mean(preds_chg), mean(preds_drv)
    3. Build NN training data: [mean_pred_chg, mean_pred_drv] → actual_max_capacity_Ah
    4. Train: MSE loss, Adam optimizer (lr=0.01), 300 epochs
    5. Only cars with BOTH modalities + ground truth included
        │
        ▼
  Save to HDFS: /models/battery_health_ensemble/v_YYYYMMDD_HHmmss/
    ├── xgb_model_chg.json, scaler_chg.joblib
    ├── xgb_model_drv.json, scaler_drv.joblib
    └── ensemble_nn.pth
```

**Inference Flow (`train.py`):**

```
[HDFS: /models/battery_health_ensemble/latest.json]
        │
        ▼
  Read latest.json → resolve model version directory
        │
        ▼
  Load: XGBoost-Chg, XGBoost-Drv, EnsembleNN (if exists)
        │
        ▼
[HDFS: /raw_data/battery_telemetry_v4/*.csv]
        │
        ▼
  Load telemetry data for requested car_ids
  Smart date resolution (different dates for charging vs driving):
    • Specific date (YYYYMMDD) → find files matching that date
    • "latest" → independently find newest file with charging data
                   and newest file with driving data (may differ)
        │
        ▼
  filter_by_modality() → inf_chg, inf_drv
        │
        ▼
  predict: XGB-Chg on inf_chg, XGB-Drv on inf_drv
        │
        ▼
  Average per modality per car → ensemble → NN or fallback
        │
        ▼
  Save results to /output_data/inference_ensemble_result_*.csv
  Metrics: RMSE per modality + overall
```

---

### Approach 2: Simple XGBoost (Single Model)

**Files:** `api/xgb_train.py`, `api/xgb_predict.py`

A simpler, faster approach that trains a **single XGBoost model** on all data (charging + driving combined), without modality splitting or a neural network meta-learner.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Simple XGBoost Architecture                        │
│                                                                     │
│  Input: [volt_V, current_A, soc_pct, max_single_volt_V,            │
│         min_single_volt_V, max_temp_C, min_temp_C]                  │
│         × 128 time steps = 928 features (flattened)                 │
│         │                                                           │
│         ▼                                                           │
│  StandardScaler → XGBoost (gbtree)                                  │
│    lr=0.05, max_depth=8                                             │
│    300 rounds, early_stopping=50                                    │
│    tree_method=hist                                                 │
│         │                                                           │
│         ▼                                                           │
│  Output: predicted battery capacity (Ah)                            │
│                                                                     │
│  Single model — no modality split, no meta-learner                  │
└─────────────────────────────────────────────────────────────────────┘
```

**Training Flow (`xgb_train.py`):**

```
[HDFS: /raw_sample_data/sampled_training/*.csv]
        │
        ▼
  load_data_universal() → GlobalSnippetBuffer → windowed samples
        │
        ▼
  split_train_test_by_car()        -- 80% train / 20% val
        │
        ▼
  NO modality split — use all data together
        │
        ▼
  extract_features_2d() → StandardScaler → xgb.train()
        │
        ▼
  Save to HDFS: /models/battery_health_xgb/v_YYYYMMDD_HHmmss/
    ├── xgb_model_xgb.json
    └── scaler_xgb.joblib
```

**Inference Flow (`xgb_predict.py`):**

```
[HDFS: /models/battery_health_xgb/latest.json]
        │
        ▼
  Load single XGBoost model + scaler
        │
        ▼
[HDFS: /raw_data/battery_telemetry_v4/*.csv]
        │
        ▼
  Load telemetry for car_ids, resolve date (latest or YYYYMMDD)
        │
        ▼
  extract_features_2d() → scaler.transform() → xgb_model.predict()
        │
        ▼
  Average per car → save to /output_data/inference_xgb_result_*.csv
```

---

## Data Flow Pipeline

Both approaches share the same data loading and feature extraction pipeline:

```
[HDFS: *.csv raw telemetry files]
        │
        ▼
  data_utils.get_hdfs_files_filtered()  -- scan HDFS for CSV files
        │
        ▼
  data_utils.load_data_universal()       -- download & parse CSVs (200K-row chunks)
        │
        ▼
  GlobalSnippetBuffer.add_chunk()        -- core/snippetbuffer.py
        │
        ├── Groups by (car_id, id_segment)
        ├── Validates: 128 unique step_idx values (window must span 0-127)
        ├── Emits: (feature_matrix, meta_dict, window_df)
        └── When buffer doesn't fill: stores remainder for next chunk
        │
        ▼
  GlobalSnippetBuffer.flush_remainder()  -- pad incomplete windows in inference mode
        │
        ▼
  split_and_extract.split_train_test_by_car()  -- 80/20 split by car identity
        │
   ┌───┴───┐
   ▼       ▼
Train     Val
  │         │
  ▼         ▼
filter_by_modality()
  (ensemble only; simple XGBoost skips this)
  │
  ▼
extract_features_2d()  -- flatten 2D (128, 7) → 1D (928,) per sample
  │
  ▼
StandardScaler + XGBoost training
```

**Feature columns** (from `config.py`):
- `volt_V`, `current_A`, `soc_pct`, `max_single_volt_V`, `min_single_volt_V`, `max_temp_C`, `min_temp_C`
- Window size: 128 steps → flattened to 128 * 7 = **928 features**

**Snippet buffer** (`core/snippetbuffer.py`):
- Reads raw telemetry CSVs in 200K-row chunks
- Groups by `(car_id, id_segment)`
- Extracts fixed-length windows of 128 rows where `step_idx` spans exactly 0-127
- Validation: `max_step - min_step == 127` AND `unique_steps == 128`
- Padding: in inference mode, short remaining segments are zero-padded to `WINDOW_SIZE`
- Each window uses different feature columns based on modality (though currently same set for both)

---

## Model Storage & Versioning

Both pipelines use **versioned directories** on HDFS to avoid overwriting active models:

| Pipeline | HDFS Model Root | Artifacts |
|----------|----------------|-----------|
| Stacking Ensemble | `/models/battery_health_ensemble/` | `xgb_model_chg.json`, `scaler_chg.joblib`, `xgb_model_drv.json`, `scaler_drv.joblib`, `ensemble_nn.pth` |
| Simple XGBoost | `/models/battery_health_xgb/` | `xgb_model_xgb.json`, `scaler_xgb.joblib` |

**Versioning mechanism:**
- Each training run creates: `{model_root}/v_YYYYMMDD_HHmmss/`
- A `latest.json` file at the root points to the current version path:
  ```json
  {"version": "20260115_143022", "path": "/models/battery_health_ensemble/v_20260115_143022", "created_at": "2026-01-15T14:30:22+07:00"}
  ```
- Inference reads `latest.json` to resolve the active model directory
- Fallback: if `latest.json` doesn't exist, uses the base directory (backward-compatible)

---

## Concurrency Control

**`ReadWriteLock`** (`core/job_manager.py`):
- Multiple readers can hold the lock simultaneously (concurrent inference jobs)
- Only one writer can hold the lock, and no readers may hold it during write (training blocks inference reads)
- Prevents HDFS lease conflicts when model files are being read/written simultaneously
- Used in: `_resolve_model_dir()` (read lock) and model saving (write lock)

---

## Job Management & Persistence

Jobs run in a **ThreadPoolExecutor** (max 2 workers, configurable via `MAX_WORKERS` env var) so the API is non-blocking:

**Job lifecycle:**

```
POST /api/v1/{train|predict|train_xgb|predict_xgb}
        │
        ▼
  submit_job() → creates JobInfo (PENDING) → submits to ThreadPoolExecutor
        │
        ▼
  Background thread: job status → RUNNING
        │
        ▼
  Pipeline executes in steps, updating job.progress string:
    Training:  "Step 1/3: Loading & splitting data..."
               "Step 2/3: Training XGBoost on combined data..."
               "Step 3/3: Saving model to HDFS..."
    Inference: "Step 1/3: Loading XGBoost model from HDFS..."
               "Step 2/3: Loading inference data..."
               "Step 3/3: Running predictions..."
        │
        ▼
  Job status → COMPLETED or FAILED
        │
        ▼
  _persist_session() → save to PostgreSQL
        ├── PredictSession: job-level metadata, status, metrics, saved files
        └── PredictInfo: per-vehicle predictions (car_id, gt_capacity, preds, errors)
```

**Job states:** `pending` → `running` → `completed` / `failed`
**Progress:** Updated in real-time via `job.progress` strings, pollable via `GET /api/v1/jobs/{job_id}`
**Persistence:** Completed/failed jobs persisted to PostgreSQL; historical jobs loadable from DB

---

## Database Schema (ORM Models in `core/models.py`)

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| `users` | `user_id`, `user_name`, `role` (Admin/User) | User accounts (seeded on startup) |
| `vehicles` | `car_id`, `car_name`, `vin_number`, `battery_serial`, `use_to_predict`, `user_id` | Registered EV vehicles |
| `sessions` | `job_id`, `job_type`, `status`, `hdfs_url`, `metrics`, `saved_files`, `result_csv_directory`, `models_loaded_from` | Job/session metadata |
| `session_vehicles` | `job_id` + `car_id` (many-to-many join) | Links sessions to vehicles |
| `predict_infos` | `car_id` + `session_id` (composite PK), `max_mileage_km`, `pred_xgboost_chg`, `pred_xgboost_drv`, `final_ensemble_pred`, `gt_capacity`, `error` | Per-vehicle prediction results |

---

## API Endpoints Summary

### Training Endpoints

| Endpoint | Method | File | Description |
|----------|--------|------|-------------|
| `/api/v1/train` | POST | `train_pipeline.py` | Train stacking ensemble (2 XGBoost + NN meta-learner) |
| `/api/v1/xgb_train` | POST | `xgb_train.py` | Train simple combined XGBoost model |

**Request body (both):**
```json
{
  "HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870",
  "user_id": "templateUser"
}
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Training job submitted...",
  "job_id": "uuid-here",
  "hdfs_url_used": "...",
  "user_id": "..."
}
```

### Inference Endpoints

| Endpoint | Method | File | Description |
|----------|--------|------|-------------|
| `/api/v1/predict` | POST | `train.py` | Run stacking ensemble inference |
| `/api/v1/xgb_predict` | POST | `xgb_predict.py` | Run simple XGBoost inference |

**Request body (both):**
```json
{
  "HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870",
  "car_ids": ["EV_104", "EV_105", "EV_109", "EV_110"],
  "predict_date": "latest",
  "user_id": "templateUser"
}
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Prediction job submitted...",
  "job_id": "uuid-here",
  "hdfs_url_used": "...",
  "car_ids": [...],
  "predict_date": "latest",
  "user_id": "..."
}
```

### Job & Vehicle Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/jobs` | GET | List all jobs (role-filtered) |
| `/api/v1/jobs/{id}` | GET | Get specific job status/progress/result |
| `/api/v1/vehicles` | POST/GET | Create/list vehicles |
| `/api/v1/vehicles/{car_id}/predictions` | GET | Get prediction history for a car |

---

## Configuration

**`core/config.py`** — Shared configuration:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `HDFS_URL` | `http://hc1-c-0003u.hc.apac.bosch.com:9870` | HDFS NameNode URL |
| `HDFS_USER` | `hdfs` | HDFS user for InsecureClient |
| `WINDOW_SIZE` | `128` | Time steps per window |
| `FEATURE_COLS` | 7 columns | Feature columns for window extraction |
| `DEVICE` | `cuda` or `cpu` | Compute device (auto-detected) |
| `HDFS_OUTPUT_DIR` | `/output_data` | Directory for result CSVs |
| `NUM_FILES_LIMIT` | `None` | Max files to process (None = all) |

**Auth:** Azure AD auth is DISABLED by default (`auth_deps = []`). Set `AUTH_ENABLED=true` and uncomment the auth deps to re-enable.

---

## Running

### Docker (recommended)
```bash
cd src/AIAPI
docker build -t aiapi-backend .
docker compose up -d
```

### Local
```bash
cd src/AIAPI
cp .env.example .env          # edit proxy / DB / HDFS creds
pip install -r requirements.txt
PYTHONPATH=../ev_client_app:$PYTHONPATH uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

With auth disabled:
```bash
AUTH_ENABLED=false              # skip Azure AD, use template user
```

### Train (Stacking Ensemble)
```bash
curl -X POST http://localhost:8000/api/v1/train \
  -H "Content-Type: application/json" \
  -d '{"HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870", "user_id": "templateUser"}'
# → {"job_id": "...", "status": "accepted"}
# → curl http://localhost:8000/api/v1/jobs/{job_id}
```

### Train (Simple XGBoost)
```bash
curl -X POST http://localhost:8000/api/v1/xgb_train \
  -H "Content-Type: application/json" \
  -d '{"HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870", "user_id": "templateUser"}'
```

### Predict (Stacking Ensemble)
```bash
curl -X POST http://localhost:8000/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{"HDFS_URL": "...", "car_ids": ["EV_104"], "predict_date": "latest"}'
```

### Predict (Simple XGBoost)
```bash
curl -X POST http://localhost:8000/api/v1/xgb_predict \
  -H "Content-Type: application/json" \
  -d '{"HDFS_URL": "...", "car_ids": ["EV_104"], "predict_date": "latest"}'
```

### Health Check
```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

---

## Model Parameters

### Stacking Ensemble

| Component | Parameters |
|-----------|-----------|
| XGBoost-Charging | `booster=gbtree`, `lr=0.05`, `objective=reg:squarederror`, `seed=168`, `nthread=-1`, `tree_method=hist`, `early_stopping=50`, `300 rounds` |
| XGBoost-Driving | Same as Charging + `max_depth=8` |
| EnsembleNN | `Linear(2,32)` → ReLU → `Linear(32,16)` → ReLU → `Linear(16,1)` |
| EnsembleNN Training | MSE loss, Adam (lr=0.01), 300 epochs |

### Simple XGBoost

| Parameter | Value |
|-----------|-------|
| `booster` | `gbtree` |
| `learning_rate` | `0.05` |
| `objective` | `reg:squarederror` |
| `max_depth` | `8` |
| `seed` | `168` |
| `tree_method` | `hist` |
| `num_boost_round` | `300` |
| `early_stopping_rounds` | `50` |
| Features | 928 (128 steps × 7 columns, flattened) |
| Split | 80% train / 20% val (by car identity) |

---

## Key Differences: Stacking Ensemble vs Simple XGBoost

| Aspect | Stacking Ensemble | Simple XGBoost |
|--------|------------------|----------------|
| **Models** | 2 XGBoost + 1 NN | 1 XGBoost |
| **Modality split** | Yes (charging vs driving) | No (combined) |
| **Meta-learner** | EnsembleNN (PyTorch) | None |
| **Training time** | Longer (3 models + NN training) | Faster (1 model) |
| **Model storage** | `/models/battery_health_ensemble/` | `/models/battery_health_xgb/` |
| **Artifacts per model** | 5 files | 2 files |
| **Inference complexity** | Higher (3 model loads + averaging + NN) | Lower (1 model load) |
| **Fallback when modality missing** | Uses available modality | No modality to split |
| **Output columns** | `pred_xgboost_chg`, `pred_xgboost_drv`, `final_ensemble_pred` | `final_pred` |
| **Training endpoint** | `/api/v1/train` | `/api/v1/xgb_train` |
| **Inference endpoint** | `/api/v1/predict` | `/api/v1/xgb_predict` |
| **Result CSV prefix** | `inference_ensemble_result_*.csv` | `inference_xgb_result_*.csv` |

---

## Data Paths

| Purpose | HDFS Path |
|---------|-----------|
| Training data (sampled) | `/raw_sample_data/sampled_training/` |
| Inference raw data | `/raw_data/battery_telemetry_v4/` |
| Ensemble model root | `/models/battery_health_ensemble/` |
| Simple XGBoost model root | `/models/battery_health_xgb/` |
| Learning curve images | `/models/learning_curve/` |
| Result CSVs | `/output_data/` |

---

## File Mapping (Before / After)

| File | Purpose | Key Functions/Classes |
|------|---------|----------------------|
| `api/train_pipeline.py` | Stacking ensemble training | `_run_train_pipeline()`, `start_train()` |
| `api/train.py` | Stacking ensemble inference | `_run_predict_pipeline()`, `start_predict()` |
| `api/xgb_train.py` | Simple XGBoost training | `_run_train_pipeline()`, `start_xgb_train()` |
| `api/xgb_predict.py` | Simple XGBoost inference | `_run_predict_pipeline()`, `start_xgb_predict()` |
| `api/schemas.py` | Pydantic request schemas | `TrainRequest`, `PredictRequest`, `TrainResponse`, `ErrorResponse` |
| `api/jobs.py` | Job management API | `get_jobs_list()`, `get_job_status()` |
| `api/vehicles.py` | Vehicle CRUD + predictions | Vehicle endpoints with `user_id` query param |
| `core/nn.py` | Neural network meta-learner | `EnsembleNN` class (2→32→16→1) |
| `core/data_utils.py` | HDFS I/O & data utilities | `load_data_universal()`, `save_artifacts_to_hdfs()`, `load_artifacts_from_hdfs()` |
| `core/snippetbuffer.py` | Windowed sample extraction | `GlobalSnippetBuffer` class with `add_chunk()` and `flush_remainder()` |
| `core/split_and_extract.py` | Splitting & feature extraction | `split_train_test_by_car()`, `extract_features_2d()`, `extract_features_3d()` |
| `core/job_manager.py` | Job management + concurrency | `JobInfo`, `JobStatus`, `ReadWriteLock`, `submit_job()`, `get_job()` |
| `core/config.py` | Global configuration | `WINDOW_SIZE`, `FEATURE_COLS`, `HDFS_*` constants |
| `core/models.py` | SQLAlchemy ORM models | `User`, `Vehicle`, `PredictSession`, `PredictInfo` |
| `main.py` | FastAPI app entry point | `app` instance, router registration, startup migration |

---

## Circular Import Resolution

`GlobalSnippetBuffer` lives in `core/snippetbuffer.py` (not in `data_utils.py`) to keep dependencies clean. The `add_chunk()` method references `config.py` for `WINDOW_SIZE`, `FEATURE_COLS_CHG`, and `FEATURE_COLS_DRV`.

## Dependencies

| Package | Purpose |
|---------|---------|
| `xgboost` | Gradient boosted trees (both pipelines) |
| `torch` | Neural network for meta-learner (stacking ensemble) |
| `scikit-learn` | `StandardScaler` for feature normalization |
| `hdfs` | HDFS client (`InsecureClient`) for data/model I/O |
| `fastapi` | Web framework |
| `pydantic>=2.0` | Request/response validation |
| `SQLAlchemy` | Database ORM |
| `pendulum` | Timezone-aware datetime handling |
| `joblib` | Scaler serialization |
| `kafka-python` | Kafka integration (indirect, via ev_client_app) |
| `python-dotenv` | Environment variable loading |
| `psycopg2-binary` | PostgreSQL driver |
