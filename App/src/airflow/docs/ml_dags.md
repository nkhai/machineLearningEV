# Airflow ML DAGs

## Overview

The `airflow/` directory contains **6 Airflow DAGs** for the EV battery health prediction system. The DAGs fall into two categories:

1. **ML Pipeline DAGs** — Orchestrate training and inference by calling the AIAPI service (external FastAPI backend)
2. **Data Ingestion DAG** — Consumes raw telemetry from Kafka and uploads to HDFS

All ML training and inference workflows are **delegated to the AIAPI service**. Airflow acts as a thin orchestrator: it submits jobs via HTTP POST, polls for completion, and handles retries/scheduling.

---

## Project Structure

```
airflow/
├── dags/                           # DAG definition files (deployed to $AIRFLOW_HOME/dags/)
│   ├── train_airflow.py            # Stacking ensemble training (manual trigger)
│   ├── inference_airflow.py        # Stacking ensemble inference (daily @ midnight)
│   ├── train_xgb_simple_airflow.py # Simple XGBoost training (manual trigger)
│   ├── inference_xgb_simple_airflow.py # Simple XGBoost inference (daily @ midnight)
│   ├── kafka_to_hdfs.py            # Kafka → HDFS data ingestion (every 15 min)
│   └── readme.md                   # Placeholder
│
├── ml_airflow/                     # Python modules (imported by DAGs via sys.path)
│   ├── dags/
│   │   └── aiapi_pipeline.py       # Combined train→predict DAG (daily @ midnight)
│   ├── config/
│   │   └── config.py               # Global config (AIAPI URL, HDFS URL, window size)
│   ├── data_processing/            # (Not used in current DAGs — legacy)
│   │   ├── data_utils.py
│   │   ├── snippetbuffer.py
│   │   └── split_and_extract.py
│   ├── models/
│   │   └── nn.py                   # EnsembleNN meta-learner
│   ├── testing/                    # Pipeline wrapper modules (also DAG callables)
│   │   ├── train_xg_test.py        # Stacking ensemble training wrapper
│   │   ├── infer_nn_test.py        # Stacking ensemble inference wrapper
│   │   ├── xgb_simple_train_test.py # Simple XGBoost training wrapper
│   │   └── xgb_simple_infer_test.py # Simple XGBoost inference wrapper
│   └── visualize/
│       └── plot_curve.py           # XGBoost learning curve plotting (unused)
│
├── output_files/                   # Empty (placeholder)
└── plugins/                        # Empty (placeholder)
```

---

## DAG 1: `ev_battery_training_dag` (Stacking Ensemble Training)

**File:** `dags/train_airflow.py`

| Property | Value |
|----------|-------|
| **DAG ID** | `ev_battery_training_dag` |
| **Description** | Manual training pipeline for EV Battery with stacking ensemble |
| **Schedule** | `None` (manual trigger only) |
| **Start Date** | 2026-01-01, Asia/Ho_Chi_Minh |
| **Catchup** | False |
| **Timeout** | 6 hours |
| **Retries** | 1, with 1-minute delay |
| **Tags** | `ev`, `xgboost`, `training` |
| **Owner** | `ml_team` |

**Task Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  PythonOperator: train_and_save_model                       │
│                                                             │
│  task_wrapper_for_training(**kwargs)                        │
│    ├─ Extract conf.hdfs_url and conf.user_id from DAG run   │
│    ├─ run_train_pipeline(hdfs_url, user_id)                 │
│    │     └─ ml_airflow/testing/train_xg_test.py            │
│    │           ├─ POST /api/v1/train                        │
│    │           ├─ Poll GET /api/v1/jobs/{job_id}            │
│    │           └─ Print model version, directory, cars      │
│    └─ Print success message                                 │
└─────────────────────────────────────────────────────────────┘
```

**Trigger with conf:**
```bash
airflow dags trigger ev_battery_training_dag \
  --conf '{"hdfs_url": "http://hc1-c-0003u.hc.apac.bosch.com:9870", "user_id": "templateUser"}'
```

---

## DAG 2: `ev_battery_inference_dag` (Stacking Ensemble Inference)

**File:** `dags/inference_airflow.py`

| Property | Value |
|----------|-------|
| **DAG ID** | `ev_battery_inference_dag` |
| **Description** | Daily inference pipeline using saved HDFS models (stacking ensemble) |
| **Schedule** | `0 0 * * *` (every day at midnight) |
| **Start Date** | 2026-01-01, Asia/Ho_Chi_Minh |
| **Catchup** | False |
| **Timeout** | 4 hours |
| **Retries** | 2, with 1-minute delay |
| **Tags** | `ev`, `xgboost`, `inference` |
| **Owner** | `ml_team` |

**Task Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  PythonOperator: load_model_and_predict                     │
│                                                             │
│  task_wrapper_for_inference()                               │
│    ├─ run_inference_pipeline_nn()                           │
│    │     └─ ml_airflow/testing/infer_nn_test.py            │
│    │           ├─ POST /api/v1/predict                      │
│    │           │   car_ids = ['EV_104', 'EV_105', ...]      │
│    │           │   predict_date = 'latest'                  │
│    │           ├─ Poll GET /api/v1/jobs/{job_id}            │
│    │           └─ Print predictions + metrics               │
│    └─ Print success message                                 │
└─────────────────────────────────────────────────────────────┘
```

**Hardcoded defaults:**
- `car_ids = ['EV_104', 'EV_105', 'EV_109', 'EV_110']`
- `predict_date = 'latest'`
- `HDFS_URL` from env var or config default

---

## DAG 3: `ev_xgb_simple_training_dag` (Simple XGBoost Training)

**File:** `dags/train_xgb_simple_airflow.py`

| Property | Value |
|----------|-------|
| **DAG ID** | `ev_xgb_simple_training_dag` |
| **Description** | Manual simple XGBoost training pipeline (single model, no ensemble NN) |
| **Schedule** | `None` (manual trigger only) |
| **Start Date** | 2026-01-01, Asia/Ho_Chi_Minh |
| **Catchup** | False |
| **Timeout** | 6 hours |
| **Retries** | 1, with 1-minute delay |
| **Tags** | `ev`, `xgboost`, `training`, `xgb-simple` |
| **Owner** | `ml_team` |

**Task Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  PythonOperator: xgb_train_and_save_model                   │
│                                                             │
│  task_wrapper_for_xgb_training(**kwargs)                    │
│    ├─ Extract conf.hdfs_url and conf.user_id from DAG run   │
│    ├─ run_xgb_train_pipeline(hdfs_url, user_id)             │
│    │     └─ ml_airflow/testing/xgb_simple_train_test.py    │
│    │           ├─ POST /api/v1/xgb_train                    │
│    │           ├─ Poll GET /api/v1/jobs/{job_id}            │
│    │           └─ Print model version, directory, cars      │
│    └─ Print success message                                 │
└─────────────────────────────────────────────────────────────┘
```

**Trigger with conf:**
```bash
airflow dags trigger ev_xgb_simple_training_dag \
  --conf '{"hdfs_url": "http://hc1-c-0003u.hc.apac.bosch.com:9870", "user_id": "templateUser"}'
```

---

## DAG 4: `ev_xgb_simple_inference_dag` (Simple XGBoost Inference)

**File:** `dags/inference_xgb_simple_airflow.py`

| Property | Value |
|----------|-------|
| **DAG ID** | `ev_xgb_simple_inference_dag` |
| **Description** | Daily simple XGBoost inference pipeline using single HDFS model |
| **Schedule** | `0 0 * * *` (every day at midnight) |
| **Start Date** | 2026-01-01, Asia/Ho_Chi_Minh |
| **Catchup** | False |
| **Timeout** | 4 hours |
| **Retries** | 2, with 1-minute delay |
| **Tags** | `ev`, `xgboost`, `inference`, `xgb-simple` |
| **Owner** | `ml_team` |

**Task Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│  PythonOperator: xgb_load_model_and_predict                 │
│                                                             │
│  task_wrapper_for_xgb_inference()                           │
│    ├─ run_xgb_predict_pipeline()                            │
│    │     └─ ml_airflow/testing/xgb_simple_infer_test.py    │
│    │           ├─ POST /api/v1/xgb_predict                  │
│    │           │   car_ids = ['EV_104', 'EV_105', ...]      │
│    │           │   predict_date = 'latest'                  │
│    │           ├─ Poll GET /api/v1/jobs/{job_id}            │
│    │           └─ Print predictions + metrics               │
│    └─ Print success message                                 │
└─────────────────────────────────────────────────────────────┘
```

**Hardcoded defaults:**
- `car_ids = ['EV_104', 'EV_105', 'EV_109', 'EV_110']`
- `predict_date = 'latest'`

---

## DAG 5: `kafka_to_hdfs` (Data Ingestion)

**File:** `dags/kafka_to_hdfs.py`

| Property | Value |
|----------|-------|
| **DAG ID** | `kafka_to_hdfs` |
| **Description** | Consume raw telemetry from Kafka, save per-vehicle CSVs, upload to HDFS |
| **Schedule** | Every 15 minutes |
| **Start Date** | 2024-01-01 |
| **Catchup** | False |
| **Owner** | `airflow` |
| **Tasks** | 2: `read_kafka_save_csv` → `upload_csv_to_hdfs` |

**Task Flow:**

```
┌──────────────────────────────────────────────────────────────┐
│  Task 1: read_kafka_save_csv                                  │
│                                                              │
│  read_kafka_and_save_csv(**context)                           │
│    ├─ Connect to Kafka (via Airflow connection "kafka_default")│
│    ├─ Consume from TOPIC (Variable: KAFKA_TOPIC)             │
│    ├─ Group messages by vehicle name (msg.key)               │
│    ├─ Write per-vehicle CSVs to /opt/airflow/data/           │
│    │   Format: {vehicle}_{YYYYMMDD_HHMMSS}.csv               │
│    └─ Push CSV file paths to XCom                            │
└──────────────────┬───────────────────────────────────────────┘
                   │ XCom: csv_files
                   ▼
┌──────────────────────────────────────────────────────────────┐
│  Task 2: upload_csv_to_hdfs                                   │
│                                                              │
│  upload_csv_to_hdfs(**context)                                │
│    ├─ Pull csv_files from XCom                               │
│    ├─ Connect to HDFS (via Airflow connection "hdfs_default")│
│    ├─ Create per-vehicle HDFS directories                    │
│    │   Path: {HDFS_DIR}/{vehicle_name}/{filename}.csv         │
│    └─ Upload each CSV file                                   │
└──────────────────────────────────────────────────────────────┘
```

**Configuration via Airflow:**
- Connection: `kafka_default` → broker host:port
- Connection: `hdfs_default` → HDFS host:port
- Variable: `KAFKA_TOPIC`
- Variable: `KAFKA_GROUP_ID`
- Variable: `HDFS_USER`
- Variable: `HDFS_DIR`

---

## DAG 6: `aiapi_train_and_predict` (Combined Training + Inference)

**File:** `ml_airflow/dags/aiapi_pipeline.py`

| Property | Value |
|----------|-------|
| **DAG ID** | `aiapi_train_and_predict` |
| **Description** | Train stacking ensemble then run prediction in one DAG (sequential) |
| **Schedule** | `@daily` |
| **Start Date** | 2024-01-01 |
| **Catchup** | False |
| **Owner** | `airflow` |
| **Tasks** | 2: `run_train` → `run_predict` (sequential) |

**Task Flow:**

```
┌──────────────────────────────────────────────────────────────────┐
│  Task 1: run_train                                               │
│                                                                  │
│  submit_train(**context)                                         │
│    ├─ POST /api/v1/train (HDFS_URL, user_id="airflow")          │
│    ├─ Poll GET /api/v1/jobs/{job_id} every 30s for up to 1hr   │
│    ├─ Fail if job status = "failed"                              │
│    └─ XCom push job_id                                          │
└──────────────┬───────────────────────────────────────────────────┘
               │ (sequential dependency)
               ▼
┌──────────────────────────────────────────────────────────────────┐
│  Task 2: run_predict                                             │
│                                                                  │
│  submit_predict(**context)                                       │
│    ├─ POST /api/v1/predict (HDFS_URL, car_ids, predict_date)    │
│    ├─ Poll GET /api/v1/jobs/{job_id} every 30s for up to 1hr   │
│    ├─ Fail if job status = "failed"                              │
│    └─ Print predictions: car_id, final_ensemble_pred, gt_capacity│
└──────────────────────────────────────────────────────────────────┘
```

**Configuration:**
- `AIAPI_BASE_URL` env var (default: `http://localhost:8000`)
- `HDFS_URL` hardcoded: `http://hc1-c-0003u.hc.apac.bosch.com:9870`
- `PREDICT_CAR_IDS`: `["EV_104", "EV_105", "EV_109", "EV_110"]`
- `PREDICT_DATE`: `"latest"`
- `POLL_INTERVAL`: 30 seconds
- `POLL_MAX_RETRIES`: 120 (→ 3600s = 1 hour max wait)

---

## How DAGs Interact with the AIAPI

All ML training and inference workflows in this codebase are **delegated to the AIAPI service**. Airflow DAGs act as thin orchestrators that:

1. **Submit jobs** via HTTP POST to AIAPI endpoints
2. **Poll for status** at `GET /api/v1/jobs/{job_id}` until completion or failure
3. **Handle retries** via Airflow's built-in retry mechanism
4. **Log results** by printing job output

### Request/Response Contract

**Training requests** (both `/train` and `/xgb_train`):
```json
{
  "HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870",
  "user_id": "templateUser"
}
```

**Prediction requests** (both `/predict` and `/xgb_predict`):
```json
{
  "HDFS_URL": "http://hc1-c-0003u.hc.apac.bosch.com:9870",
  "car_ids": ["EV_104", "EV_105", "EV_109", "EV_110"],
  "predict_date": "latest",
  "user_id": "system_admin"
}
```

**Job polling responses** include:
```json
{
  "job_id": "uuid-here",
  "job_type": "train",
  "user_id": "templateUser",
  "status": "completed",
  "progress": "Step 3/3: Saving models to HDFS...",
  "hdfs_url": "...",
  "created_at": "...",
  "started_at": "...",
  "completed_at": "...",
  "result": {
    "version": "20260115_143022",
    "model_directory": "http://.../explorer.html#/models/...",
    "saved_files": ["..."],
    "train_cars": ["EV_101", "EV_102", ...],
    "cars_predicted": [...],
    "predictions": [...],
    "metrics": {"rmse_overall": 12.5, "num_cars_compared": 4},
    "result_csv_directory": "...",
    "models_loaded_from": "..."
  },
  "error": null
}
```

---

## AIAPI Endpoints Used by DAGs

| AIAPI Endpoint | Used By | Purpose |
|----------------|---------|---------|
| `POST /api/v1/train` | `train_airflow.py`, `aiapi_pipeline.py` | Submit stacking ensemble training job |
| `POST /api/v1/xgb_train` | `train_xgb_simple_airflow.py` | Submit simple XGBoost training job |
| `POST /api/v1/predict` | `inference_airflow.py`, `aiapi_pipeline.py` | Submit stacking ensemble prediction job |
| `POST /api/v1/xgb_predict` | `inference_xgb_simple_airflow.py` | Submit simple XGBoost prediction job |
| `GET /api/v1/jobs/{job_id}` | All training/inference DAGs | Poll job status (pending → running → completed/failed) |

---

## Pipeline Wrapper Modules

All four pipeline wrapper files under `ml_airflow/testing/` follow the same pattern:

```python
def run_<pipeline>_pipeline(hdfs_url=None, user_id=None, car_ids=None, predict_date=None):
    """
    1. Accept optional parameters (fall back to env vars / config defaults)
    2. Submit job to AIAPI via HTTP POST
    3. Poll job status every 10 seconds until completion or timeout (30 min)
    4. Print structured results
    5. Return job status dict
    """
    ...
    job_id = submit_<type>_job(hdfs_url, ...)
    job = poll_job_status(job_id)
    print(f"Status: {job['status']}")
    if job['status'] == 'completed':
        print_results(job['result'])
    return job
```

| File | Pipeline | AIAPI Endpoint | Default car_ids |
|------|----------|---------------|-----------------|
| `train_xg_test.py` | Stacking ensemble training | `POST /api/v1/train` | N/A |
| `infer_nn_test.py` | Stacking ensemble inference | `POST /api/v1/predict` | `['EV_104', 'EV_105', 'EV_109', 'EV_110']` |
| `xgb_simple_train_test.py` | Simple XGBoost training | `POST /api/v1/xgb_train` | N/A |
| `xgb_simple_infer_test.py` | Simple XGBoost inference | `POST /api/v1/xgb_predict` | `['EV_104', 'EV_105', 'EV_109', 'EV_110']` |

**Default values** (from env vars):
- `HDFS_URL`: `http://hc1-c-0003u.hc.apac.bosch.com:9870`
- `USER_ID`: `system_admin` (env: `AIRFLOW_USER_ID`)
- `AIAPI_URL`: `http://localhost:8000` (from `ml_airflow/config/config.py`)
- `AIAPI_TIMEOUT`: `1800` seconds (30 minutes)

---

## Summary of All 6 DAGs

| # | DAG ID | Schedule | Purpose | AIAPI Endpoints | Timeout |
|---|--------|----------|---------|----------------|---------|
| 1 | `ev_battery_training_dag` | Manual (`None`) | Train stacking ensemble (XGBoost base learners + NN meta-learner) | `POST /api/v1/train` | 6 hours |
| 2 | `ev_battery_inference_dag` | Daily @ midnight | Infer using stacking ensemble model from HDFS | `POST /api/v1/predict` | 4 hours |
| 3 | `ev_xgb_simple_training_dag` | Manual (`None`) | Train simple XGBoost model (no ensemble) | `POST /api/v1/xgb_train` | 6 hours |
| 4 | `ev_xgb_simple_inference_dag` | Daily @ midnight | Infer using simple XGBoost model from HDFS | `POST /api/v1/xgb_predict` | 4 hours |
| 5 | `kafka_to_hdfs` | Every 15 min | Ingest raw telemetry from Kafka into HDFS as per-vehicle CSVs | (none — pure data pipeline) | — |
| 6 | `aiapi_train_and_predict` | Daily @ midnight | Train + predict in one DAG (train → predict sequential) | `POST /api/v1/train` → `POST /api/v1/predict` | 1 hour each |

---

## Airflow Configuration

**DAG path in Docker:** `/opt/airflow/src` (mounted as `DOCKER_SRC_PATH` in DAG files)
**sys.path injection:** `if DOCKER_SRC_PATH not in sys.path: sys.path.append(DOCKER_SRC_PATH)`

**Key environment variables:**
| Variable | Default | Purpose |
|----------|---------|---------|
| `HDFS_URL` | `http://hc1-c-0003u.hc.apac.bosch.com:9870` | HDFS NameNode URL |
| `AIRFLOW_USER_ID` | `system_admin` | User ID for AIAPI requests |
| `AIAPI_BASE_URL` | `http://localhost:8000` | AIAPI service URL |

**Airflow connections required by `kafka_to_hdfs`:**
- `kafka_default` — Kafka broker host:port
- `hdfs_default` — HDFS host:port

**Airflow variables required by `kafka_to_hdfs`:**
- `KAFKA_TOPIC` — Kafka topic name
- `KAFKA_GROUP_ID` — Consumer group ID
- `HDFS_USER` — HDFS user
- `HDFS_DIR` — HDFS upload directory

---

## Running

### Trigger Training DAGs (Manual)
```bash
airflow dags trigger ev_battery_training_dag \
  --conf '{"hdfs_url": "http://hc1-c-0003u.hc.apac.bosch.com:9870", "user_id": "templateUser"}'

airflow dags trigger ev_xgb_simple_training_dag \
  --conf '{"hdfs_url": "http://hc1-c-0003u.hc.apac.bosch.com:9870", "user_id": "templateUser"}'
```

### Trigger Combined DAG
```bash
airflow dags trigger aiapi_train_and_predict
```

### View DAG Runs & Logs
```bash
airflow dags list
airflow dags list-runs ev_battery_training_dag
airflow tasks list ev_battery_training_dag
```

### Standalone Test (bypass Airflow)
```bash
# Training
cd src/airflow
python ml_airflow/testing/xgb_simple_train_test.py

# Inference
python ml_airflow/testing/xgb_simple_infer_test.py

# Stacking ensemble
python ml_airflow/testing/train_xg_test.py
python ml_airflow/testing/infer_nn_test.py
```
