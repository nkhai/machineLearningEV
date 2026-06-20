# Predictive AI for EV Battery Health - Codebase Guide

A complete on-premise platform for simulating, collecting, storing, and predicting EV battery degradation using LLM-generated telemetry, a Kafka-streaming lakehouse, and ensemble ML models.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Reference](#2-module-reference)
   - [2.1 AIAPI](#21-aiapi)
   - [2.2 EV Client App (LangChain Agent)](#22-ev-client-app-langchain-agent)
   - [2.3 PlotlyDash (Dashboards)](#23-plotlydash-dashboards)
   - [2.4 Airflow ML Pipelines](#24-airflow-ml-pipelines)
   - [2.5 Spark & Delta Lake](#25-spark--delta-lake)
   - [2.6 Kafka Standalone](#26-kafka-standalone)
   - [2.7 HDFS Battery Sampler](#27-hdfs-battery-sampler)
3. [End-to-End Pipeline](#3-end-to-end-pipeline)
4. [Feature Deep-Dive](#4-feature-deep-dive)
   - [4.1 LLM-Based Telemetry Simulation](#41-llm-based-telemetry-simulation)
   - [4.2 Battery Degradation Modeling](#42-battery-degradation-modeling)
   - [4.3 ML Training Pipeline](#43-ml-training-pipeline)
   - [4.4 ML Inference Pipeline](#44-ml-inference-pipeline)
   - [4.5 Admin Dashboard](#45-admin-dashboard)
   - [4.6 User Dashboard](#46-user-dashboard)
   - [4.7 Anomaly Labeling (00/10)](#47-anomaly-labeling-0010)
5. [How to Run](#5-how-to-run)
6. [Port Mapping](#6-port-mapping)
7. [Configuration](#7-configuration)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                              │
│  ┌─────────────────┐    ┌──────────────────────────────────────────┐│
│  │ Admin Dashboard │    │         User Dashboard(s)                ││
│  │ port 9050       │    │    port 9001-9010 (per EV)               ││
│  │ Multi-vehicle   │    │    Single-vehicle, dark-themed           ││
│  │ Supervisory     │    │    Infotainment-style                    ││
│  └────────┬────────┘    └──────────────┬───────────────────────────┘│
│           │ SSE (EventSource)          │ SSE (EventSource)          │
└───────────┼────────────────────────────┼────────────────────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         KAFKA LAYER                                  │
│  Topic: ev.battery.telemetry_v4  |  Broker: :9092                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Kafka Consumer (Admin)    │   Kafka Consumer (User per EV)  │   │
│  │  All vehicles              │   Filtered to one car_id        │   │
│  └────────────────────────────┘   └─────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────────┐ ┌────────────┐ ┌──────────────────────┐
│  LangChain EV Agent │ │  Quick     │ │  Airflow DAGs        │
│  (per EV: 8001-8010)│ │  Data Gen  │ │  (Kafka→HDFS)       │
│  Uvicorn backend    │ │  (HDFS)    │ │                      │
│  Kafka producer     │ │            │ │                      │
└──────────┬──────────┘ └──────┬─────┘ └──────────┬───────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────────────┐ │
│  │   HDFS      │  │   PostgreSQL    │  │   Delta Lake (Spark)    │ │
│  │ :9870       │  │  :45432         │  │  :8020 (HDFS path)      │ │
│  │ Raw data    │  │  Vehicle meta   │  │  Streamed/Aggregated     │ │
│  │ Sampled data│  │  Prediction     │  │  Data                    │ │
│  │ Models      │  │  results        │  │                          │ │
│  └─────────────┘  └─────────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ML / AI LAYER                                   │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐  │
│  │   AIAPI Service       │  │   Airflow Orchestrator             │  │
│  │  :8000 (FastAPI)     │  │  :8080 (Airflow UI)               │  │
│  │  - Train endpoint    │  │  - ev_battery_training_dag         │  │
│  │  - Predict endpoint  │  │  - ev_battery_inference_dag        │  │
│  │  - Vehicle CRUD      │  │  - kafka_to_hdfs (every 15 min)    │  │
│  │  - Job tracking      │  │  - aiapi_train_and_predict (daily) │  │
│  └──────────────────────┘  └────────────────────────────────────┘  │
│                                                                      │
│  Models: XGBoost (Charging + Driving modalities)                     │
│          EnsembleNN (Meta-learner: 2→32→16→1 MLP)                   │
│          LLM: gemma-4-31B-it-FP8 via OpenAI-compatible API          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Module Reference

### 2.1 AIAPI

**Location:** `src/AIAPI/`

A FastAPI backend service for EV battery health prediction. Handles ML model training, inference, vehicle management, and job tracking.

#### Features
- **Training API (Stacking Ensemble)** — Async training job that reads telemetry from HDFS, trains XGBoost models (charging + driving modalities separately), trains an ensemble neural network meta-learner, and saves versioned models back to HDFS.
- **Training API (Simple XGBoost)** — `/api/v1/xgb_train` — Async training job that reads all telemetry data together (no modality split), trains a single XGBoost model, and saves it to HDFS (`/models/battery_health_xgb/`).
- **Inference API (Stacking Ensemble)** — Async prediction job that loads trained models from HDFS, processes per-vehicle telemetry, and returns capacity degradation predictions using the ensemble.
- **Inference API (Simple XGBoost)** — `/api/v1/xgb_predict` — Async prediction job that loads the single XGBoost model from HDFS and runs predictions on all data without modality splitting.
- **Vehicle CRUD** — Register vehicles with full metadata (car_id, car_name, VIN, license plate, battery/motor serials) under a user account. Toggle `use_to_predict` flag. All read/query endpoints support `?user_id=<user_id>` query parameter as a temporary auth fallback when Azure AD is disabled.
- **Job Tracking** — Submit a job, poll for status via `job_id`. ReadWriteLock prevents HDFS lease conflicts during concurrent operations.
- **Authentication** — Azure AD JWT validation (toggleable). Falls back to a template user when disabled.

#### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/train` | Submit async training job (`HDFS_URL`, `user_id`) |
| POST | `/api/v1/predict` | Submit async prediction job (`HDFS_URL`, `car_ids`, `predict_date`, `user_id`) |
| GET | `/api/v1/jobs` | List all jobs (admin: all; user: their vehicles) |
| GET | `/api/v1/jobs/{job_id}` | Get job status/result |
| POST | `/api/v1/xgb_train` | Submit simple XGBoost training job (combined charging+driving, no ensemble NN) |
| POST | `/api/v1/xgb_predict` | Submit simple XGBoost prediction job (single model, no modality split) |
| POST | `/api/v1/vehicles` | Create a vehicle |
| GET | `/api/v1/vehicles` | List vehicles for current user; or filter by `?user_id=<user_id>` query param |
| GET | `/api/v1/vehicles/{car_id}` | Get vehicle details; or use `?user_id=<user_id>` for temporary auth |
| PATCH | `/api/v1/vehicles/{car_id}/use_to_predict` | Toggle prediction eligibility; or use `?user_id=<user_id>` |
| GET | `/api/v1/vehicles/{car_id}/predictions` | Prediction history for a car; or use `?user_id=<user_id>` |

#### Database Tables (PostgreSQL)

| Table | Description |
|-------|-------------|
| `users` | User accounts (user_id, user_name, role: Admin/User) |
| `vehicles` | Vehicle registry (car_id PK, car_name, vin_number, user_id FK) |
| `sessions` | Training/prediction job sessions (job_id, job_type, status, metrics, result paths) |
| `predict_infos` | Per-car prediction results (car_id FK, session_id FK, final_ensemble_pred, gt_capacity, error) |
| `session_vehicles` | Many-to-many: session ↔ vehicle mapping |

#### Training Pipeline (Internal)

1. Load CSV data from HDFS (`/raw_sample_data/sampled_training`), chunked via `GlobalSnippetBuffer` into fixed 128-row sliding windows.
2. Split by car: 80% train, 20% validation (seed=168). Filter by modality (charger_connected=1 for charging, =0 for driving).
3. Train XGBoost regressor (charging): StandardScaler + XGBoost (gbtree, lr=0.05, max_depth=8, early_stop=50).
4. Train XGBoost regressor (driving): Same as above.
5. Train EnsembleNN meta-learner: Run both XGBoost models on validation data, collect `[xgb_chg_pred, xgb_drv_pred]` → `gt_capacity`, train MLP (2→32→16→1), 300 epochs, Adam lr=0.01.
6. Save models to HDFS at `/models/battery_health_ensemble/v_YYYYMMDD_HHmmss/` with write lock. Update `latest.json` symlink.

#### Inference Pipeline (Internal)

1. Load models from HDFS (`latest.json` → versioned dir), read lock for concurrent access.
2. Load telemetry from HDFS (`/raw_data/battery_telemetry_v4`), filter by requested `car_ids` and date.
3. Run each modality through its XGBoost model → per-car mean predictions.
4. Ensemble: If both modalities + NN loaded → feed through EnsembleNN. If both but NN unavailable → simple average. If only one modality → use that.
5. Save results CSV to HDFS at `/output_data/inference_ensemble_result_YYYYMMDD_HHmmss.csv`.
6. Persist prediction details to `predict_infos` table.

---

### 2.2 EV Client App (LangChain Agent)

**Location:** `src/ev_client_app/`

Autonomous EV battery telemetry generation system using LLM-powered agents to simulate realistic battery sensor data.

#### Features

- **EV Agent** — State machine that simulates EV driving and charging behavior. Uses an LLM to generate 3 sequential telemetry records per call (simulating t+10s, t+20s, t+30s).
- **Decision Engine** — SOC-based probabilistic logic: switches between driving and charging based on remaining SOC, with "range anxiety" thresholds.
- **4 Agent Tools** — Each tool simulates a specific scenario with distinct physics:
  - **Urban Driving** — Stop-and-go traffic, 0-65 km/h, speed drops from traffic, regenerative braking, HVAC active.
  - **Highway Driving** — 60-120 km/h sustained, aerodynamic drag (power ∝ v³), higher temps (45-50°C).
  - **Fast Charging** — DC fast charging 50-150 kW, aggressive CC-CV profile, temperature rise from Joule heating.
  - **Home Charging** — 220V AC 2-7 kW, grid instability (10-15% current dip), slow SOC increase, garage temps (18-32°C).
- **Battery Degradation** — Capacity decreases with mileage (6% per 100,000 km) and charge cycles. LLM receives degradation multiplier feedback.
- **Kafka Producer** — Serializes telemetry records and publishes to `ev.battery.telemetry_v4` topic.
- **State Persistence** — Saves agent state to `data/{car_id}.json` between sessions (SOC, mileage, cycle count, thresholds).
- **Per-Vehicle FastAPI Backend** — Each EV runs its own Uvicorn server with Kafka consumer, SSE streaming, and REST endpoints.

#### Telemetry Record Schema (25 Fields)

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Session ID (DRxxxxxx for driving, RCxxxxxx for charging) |
| `id_segment` | str | Session_Segment (e.g., DR205432_5) |
| `volt_V` | float | Pack voltage (clamped 300-445V) |
| `current_A` | float | Current (positive = draining, negative = charging) |
| `soc_pct` | float | State of charge 0-100% |
| `max_single_volt_V` | float | Max cell voltage (2.0-4.45V) |
| `min_single_volt_V` | float | Min cell voltage (2.0-4.45V) |
| `max_temp_C` | float | Max cell temperature (-30 to 65°C) |
| `min_temp_C` | float | Min cell temperature (-30 to 65°C) |
| `timestamp_s` | int | Elapsed time in segment (0-1270, resets at 1270) |
| `avg_speed_kmh` | float | Average speed (0 during charging) |
| `hvac_active` | int | 0 or 1 |
| `payload_kg` | float | Vehicle payload (0-100 kg) |
| `regenerative_braking_Ah` | float | Energy recovered from braking |
| `motor_rpm` | float | Motor RPM (0 during charging) |
| `gear_position` | Literal["P","D"] | Gear (P during charging) |
| `accelerator_pedal_pct` | float | 0-80% driving, 0 charging |
| `brake_pedal_pct` | float | 0-100% driving, 0 charging |
| `charger_connected` | int | 1 during charging, 0 driving |
| `label` | str | Anomaly label ("00" or "10") |
| `car_id` | str | Vehicle identifier |
| `car_model` | str | Vehicle model name |
| `mileage_km` | float | Odometer (constant during charging) |
| `actual_max_capacity_Ah` | float | Degrading capacity |
| `nominal_capacity_Ah` | float | Original rated capacity |

#### FastAPI Backend (per EV)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/latest` | Latest telemetry record for this car |
| GET | `/api/history` | Full telemetry history for this car |
| GET | `/api/stream` | SSE stream of latest records |
| GET | `/api/health` | `{"running": bool, "label": str}` |
| POST | `/api/start` | Start the EV agent producer |
| POST | `/api/stop` | Stop the EV agent producer |
| POST | `/api/set_label` | Set label to "00" or "10" |
| GET | `/api/status/latest/{car_id}` | Latest status for any car |
| GET | `/api/status/history/{car_id}` | Full status history for any car |
| GET | `/api/status/stream/{car_id}` | SSE for any car |

---

### 2.3 PlotlyDash (Dashboards)

**Location:** `src/plotlydash/`

Two dashboard implementations — old Dash-based (`.py`) and new FastAPI-based (server + HTML/JS).

#### Admin Dashboard (`admin_server.py` / `admin.html` / `admin.js`)

Port **9050**. Multi-vehicle supervisory panel.

**Features:**
- Vehicle list sidebar with scrollable buttons
- Vehicle registration modal (+ New EV button, creates vehicle in PostgreSQL)
- 4 KPI cards: STATUS, SOC (%), CAPACITY (Ah), MILEAGE (km)
- Cell voltage health panel (max, min, imbalance)
- Thermal & power panel (temperature range, computed power kW)
- SVG speedometer gauge (green/orange/red at 80/140 thresholds)
- Vehicle information panel (Car ID, Name, User ID, VIN, License Plate, Battery/Motor serials)
- System logs panel (terminal-style, per-car per-level, 50-line cap, INFO/DEBUG toggle)
- SSE streaming per vehicle

**API Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `admin.html` |
| GET | `/api/health` | `{"status": "ok", "vehicle_count": N}` |
| GET | `/api/ev` | List all vehicles |
| GET | `/api/ev/{car_id}/details` | Vehicle details |
| POST | `/api/ev` | Register/update vehicle (requires car_id + user_id) |
| GET | `/api/status/latest/{car_id}` | Latest telemetry record |
| GET | `/api/status/history/{car_id}` | Full status history |
| GET | `/api/status/stream/{car_id}` | SSE stream per car |

#### User Dashboard (`user_server.py` / `user.html` / `user.js`)

Port **9001-9010** (one per EV instance). Single-vehicle dark-themed infotainment display.

**Features:**
- Label toggle button (top-left, "00" green / "10" red)
- Status box (top-right, NORMAL green glow / ANOMALY red glow)
- SVG speedometer (260px, 240 km/h max, same color thresholds)
- Stats panel: Voltage (V), Current (A), Capacity (Ah), Battery visual, SOC display, Max/Min Temp, Mileage
- Voltage trend chart: Canvas-based line chart, last 50 points, cyan fill
- SSE-driven updates (no polling)

**API Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves `user.html` |
| GET | `/api/config` | `{"car_id", "car_name", "vin"}` |
| POST | `/api/set_label` | Set label 0 or 10 |
| GET | `/api/label` | Current label value |
| GET | `/api/trend` | Trend data: `[{time, volt}, ...]` (max 50) |
| GET | `/api/status/stream` | SSE stream for this car |

---

### 2.4 Airflow ML Pipelines

**Location:** `src/airflow/`

Apache Airflow orchestrates the ML lifecycle: data ingestion, training, and inference.

#### DAGs

| DAG | Schedule | Tasks | Description |
|-----|----------|-------|-------------|
| `ev_battery_training_dag` | Manual trigger | `train_and_save_model` | Triggers training via AIAPI `POST /api/v1/train`, polls for completion |
| `ev_battery_inference_dag` | Daily at midnight | `load_model_and_predict` | Triggers prediction via AIAPI `POST /api/v1/predict`, polls for completion |
| `kafka_to_hdfs` | Every 15 minutes | `read_kafka_save_csv` → `upload_csv_to_hdfs` | Consumes Kafka, saves per-vehicle CSVs, uploads to HDFS |
| `aiapi_train_and_predict` | Daily at midnight | `run_train` → `run_predict` | Chains training + prediction via AIAPI REST calls |

#### Training DAG Flow

```
DAG trigger (manual, with conf: hdfs_url + user_id)
  → task_wrapper_for_training(**kwargs)
    → train_xg_test.submit_train_job(HDFS_URL, user_id)
      → POST http://localhost:8000/api/v1/train
        → AIAPI returns job_id
    → train_xg_test.poll_job_status(job_id)
      → GET http://localhost:8000/api/v1/jobs/{job_id} every 10s, timeout 30min
    → Print results: status, model version, model directory, training cars, saved files
```

#### Inference DAG Flow

```
DAG trigger (daily at midnight, or manual)
  → task_wrapper_for_inference()
    → infer_nn_test.submit_predict_job(HDFS_URL, car_ids=["EV_104","EV_105","EV_109","EV_110"], predict_date="latest", user_id="system_admin")
      → POST http://localhost:8000/api/v1/predict
        → AIAPI returns job_id
    → infer_nn_test.poll_job_status(job_id)
      → GET http://localhost:8000/api/v1/jobs/{job_id} every 10s, timeout 30min
    → Print results: status, cars predicted, metrics, predictions, result CSV directory
```

#### Kafka to HDFS DAG

```
Every 15 minutes:
  read_kafka_save_csv:
    → KafkaConsumer(topic, group_id, timeout=60s)
    → Group messages by msg.key (vehicle name)
    → Write per-vehicle CSV to /opt/airflow/data/
    → XCom push: csv_files = [list of CSV paths]
  
  upload_csv_to_hdfs:
    → XCom pull: csv_files
    → InsecureClient(HDFS_URL)
    → For each CSV: makedirs(HDFS_DIR/vehicle_name/), upload CSV
```

#### Data Processing

**GlobalSnippetBuffer** — Converts raw irregular CSV files into fixed 128-row sliding windows:
1. Validates `id_segment` column, clips SOC to [0,100], computes step_idx.
2. Groups by (car_id, id_segment), extracts metadata (capacity, mileage, label).
3. For each group: computes `num_windows = total_rows // 128`.
4. For each window: validates step continuity (max-min == 127, unique == 128).
5. Extracts 7 features: `volt_V`, `current_A`, `soc_pct`, `max_single_volt_V`, `min_single_volt_V`, `max_temp_C`, `min_temp_C`.
6. Buffering remainder: pads short windows during inference, saves to buffer for next chunk during training.

**Feature Extraction:**
- `extract_features_3d()` → shape `(N, 128, 7)` for XGBoost
- `extract_features_2d()` → shape `(N, 128*7)` for Neural Network

**Train/Test Split:** By car, not by sample. 80% train, 20% validation, seed=168. Prevents data leakage.

---

### 2.5 Spark & Delta Lake

**Location:** `src/spark/`

#### Kafka to Delta Streaming (`kafka_to_delta.py`)
PySpark Structured Streaming job that reads JSON from `lakehouse_input` topic, parses with explicit schema, adds `processed_at` timestamp, and writes to Delta Lake at `/delta/lakehouse/streaming_data` in append mode with checkpoint for fault tolerance.

#### Delta Batch Processing (`delta_batch_processing.py`)
Batch job that reads streaming Delta data, performs hourly windowed aggregations (`record_count`, `avg_metric`, `max_metric`, `min_metric`), writes to `/delta/lakehouse/aggregated_data` in overwrite mode, then runs Delta compaction and 7-day vacuum.

---

### 2.6 Kafka Standalone

**Location:** `src/kafka/`

Example producer/consumer for the `lakehouse_input` topic:
- Producer: 1 message/second, JSON format, `acks=all`, 3 retries
- Consumer: Group `lakehouse_consumer_group`, `auto_offset_reset=earliest`, prints each message with topic/partition/offset

---

### 2.7 HDFS Battery Sampler

**Location:** `src/battery_hdfs_sampler.py`

Sophisticated data sampling pipeline for model training:

1. Queries PostgreSQL for cars where `use_to_predict = false` (eligible for training).
2. Connects to HDFS, discovers raw CSV files in `/raw_data/battery_telemetry_v4`.
3. Incremental processing: reads `processed_registry.json` to skip already-processed files.
4. Loads data chunked via `load_data_universal()`.
5. Optional modality filter (charging, driving, or all).
6. Feature extraction + StandardScaler normalization.
7. K-means clustering (elbow selection: tests k=5 to 20 by silhouette score).
8. Stratified sampling: proportionally from each cluster, capped at 10,000 samples.
9. Writes sampled CSVs to HDFS at `/raw_sample_data/sampled_training/` with 23 output columns.
10. Updates registry for incremental runs.

---

## 3. End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          DATA GENERATION                                 │
│                                                                          │
│  For each EV (EV_101 - EV_110):                                          │
│    ┌─────────────────────────┐                                           │
│    │  LangChain EV Agent      │                                           │
│    │  (LLM: gemma-4-31B-it)  │                                           │
│    │                         │                                           │
│    │  Decision Engine        │                                           │
│    │  SOC > 40% → Drive      │                                           │
│    │  SOC 30-40% → 60% charge│                                           │
│    │  SOC 0-10% → 95% charge │                                           │
│    │                         │                                           │
│    │  LLM Tool Execute:      │                                           │
│    │  urban_drive → 3 records│                                           │
│    │  highway_drive → 3 rcds │                                           │
│    │  fast_charge → 3 rcds   │                                           │
│    │  home_charge → 3 rcds   │                                           │
│    └──────────┬──────────────┘                                           │
│               │ JSON telemetry (25 fields)                                │
│               ▼                                                          │
│    ┌─────────────────────┐                                              │
│    │  Kafka Producer      │                                              │
│    │  Topic:              │                                              │
│    │  ev.battery.         │                                              │
│    │  telemetry_v4        │                                              │
│    │  Key: car_id         │                                              │
│    └──────────┬──────────┘                                              │
│               │                                                          │
└───────────────┼──────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      DATA CONSUMPTION                                    │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Kafka Consumer → Dashboards                                     │   │
│  │  ┌──────────────┐  ┌──────────────────────────────────────────┐  │   │
│  │  │ Admin (port  │  │  User Dashboard (port 9001-9010 per EV)  │  │   │
│  │  │   9050)      │  │  ┌────────────────────────────────────┐  │  │   │
│  │  │ All vehicles │  │  │ Speed gauge, stats, voltage trend  │  │  │   │
│  │  │ SSE stream   │  │  │ Anomaly label toggle (00/10)       │  │  │   │
│  │  │ Per-car state│  │  └────────────────────────────────────┘  │  │   │
│  │  └──────────────┘  └──────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Airflow DAG: kafka_to_hdfs (every 15 min)                       │   │
│  │  Kafka → Per-vehicle CSV → HDFS (/raw_data/battery_telemetry/)   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  HDFS Battery Sampler (manual/on-demand)                          │   │
│  │  Raw HDFS → Windowing → Clustering → Stratified Sampling         │   │
│  │  → Sampled training data at /raw_sample_data/sampled_training/   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      ML TRAINING & INFERENCE                             │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Airflow DAG: ev_battery_training_dag (manual trigger)           │   │
│  │  OR                                                              │   │
│  │  AIAPI: POST /api/v1/train (direct API call)                     │   │
│  │                                                                   │   │
│  │  HDFS sampled data → GlobalSnippetBuffer → Train/Test split      │   │
│  │  → XGBoost (charging) + XGBoost (driving) → EnsembleNN           │   │
│  │  → Save models to HDFS (versioned: v_YYYYMMDD_HHmmss/)          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Airflow DAG: ev_battery_inference_dag (daily at midnight)       │   │
│  │  OR                                                              │   │
│  │  AIAPI: POST /api/v1/predict (direct API call)                   │   │
│  │                                                                   │   │
│  │  HDFS raw data → Load models → XGBoost per modality             │   │
│  │  → EnsembleNN → Save predictions to HDFS CSV                     │   │
│  │  → Persist to predict_infos table                                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Feature Deep-Dive

### 4.1 LLM-Based Telemetry Simulation

The core of the data generation system is an LLM-driven agent. Four YAML prompt templates define the simulation behavior:

- `prompts/urban_driving.yaml` — Urban cruise scenario
- `prompts/highway_driving.yaml` — Inter-city highway
- `prompts/fast_charging.yaml` — DC fast charging (CC-CV)
- `prompts/home_charging.yaml` — Residential AC charging

Each prompt defines:
1. System role (simulator persona)
2. Scenario context (Vietnamese driving/charging conditions)
3. Output format (strict JSON array of exactly 3 objects, 25 keys)
4. Car model specs (SimuProA = 210Ah, SimuProB = 185Ah)
5. Physics and non-linear dynamics rules
6. Per-field constraints and correlations
7. Session ID and timestamp progression rules

The LLM API is OpenAI-compatible (Gemma 4 31B IT at `http://hc1-c-0003u.hc.apac.bosch.com:30000/v1`). Each call returns exactly 3 records. The agent calls the LLM iteratively until the current segment reaches 128 records.

### 4.2 Battery Degradation Modeling

Degradation occurs at two points:

1. **Session initialization:** `actual_max_capacity_Ah = nominal_capacity_Ah * (1.0 - mileage_km * 0.06/100000 + noise)`
2. **Charge-to-drive transition:** `actual_max_capacity_Ah = min(previous, expected_capacity)` — capacity only decreases.

The LLM receives the degradation ratio `(nominal_capacity / actual_capacity)` and applies it to SOC change rates — a degraded battery drains faster during driving and charges faster during charging.

Each drive-charge-drive cycle increments `cycle_count` by 1.

### 4.3 ML Training Pipeline

The system trains two independent XGBoost models — one for charging sessions, one for driving sessions. Each model predicts `actual_max_capacity_Ah` (battery health in Ah) from a 128-timestep sliding window of 7 features.

The models are combined via an ensemble neural network (MLP: 2→32→16→1) that takes `[xgb_charging_pred, xgb_driving_pred]` as input and outputs a single final prediction. The ensemble is trained on validation set predictions from both XGBoost models.

All model artifacts (XGBoost JSON + scikit-learn joblib scaler + PyTorch .pth weights) are saved to versioned HDFS directories.

### 4.4 ML Inference Pipeline

During inference:
1. Models are loaded from HDFS (read lock allows concurrent inference jobs).
2. Telemetry data for requested vehicles and dates is loaded from HDFS.
3. Each session is classified as charging or driving, passed through the corresponding XGBoost model.
4. Per-car mean predictions from each modality are collected.
5. Ensemble logic: Both modalities + NN loaded → EnsembleNN; Both but no NN → simple average; One modality → that prediction.
6. Results are saved as CSV to HDFS and persisted to PostgreSQL `predict_infos` table.

### 4.5 Admin Dashboard

The admin dashboard provides fleet-wide supervisory control:
- Register new vehicles in PostgreSQL with full metadata
- Select any registered vehicle to view its real-time telemetry
- 4 KPI cards with color-coded status indicators
- Cell voltage health monitoring (max, min, imbalance)
- Temperature and power computation
- SVG speedometer with green/orange/red thresholds
- System logs panel with per-car per-level logging
- SSE-driven real-time updates (no page refresh needed)

### 4.6 User Dashboard

The user dashboard is a single-vehicle infotainment-style display:
- Large SVG speedometer with 240 km/h max range
- Battery visual with SOC percentage
- Voltage, current, capacity, and temperature info boxes
- Real-time voltage trend chart (canvas-based, last 50 points)
- Anomaly label toggle button (00 = normal, 10 = anomaly)
- Dark theme optimized for vehicle displays
- SSE-driven updates (no polling)

### 4.7 Anomaly Labeling (00/10)

The label toggle allows manual marking of anomalous telemetry:
- "00" (green) = Normal operation
- "10" (red) = Anomaly detected

The label is stored in the in-memory state of the user dashboard server and also sent back via SSE in each telemetry record. The LLM tools receive the label as context, allowing it to adjust its simulation behavior accordingly. The label is also persisted in every telemetry record sent to Kafka.

---

## 5. How to Run

### Prerequisites
- Docker and Docker Compose
- Python 3.10+
- Environment variables in `infra/.env`

### Step 1: Start Infrastructure

```bash
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/infra
docker compose up -d
```

This starts 14 services: Kafka, HDFS (NameNode + DataNode), YARN, PostgreSQL, pgAdmin, Redis, and all Airflow components.

Wait ~2-3 minutes for all services to become healthy.

### Step 2: Start EV Fleet

```bash
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/src/ev_client_app/langchain/
./scripts/start_all.sh
```

This sequentially starts 10 EV instances (EV_101 through EV_110, skipping EV_105). Each EV runs a Uvicorn backend server and a PlotlyDash frontend. The script waits for "Application startup complete" in each EV's log before launching the next.

### Step 3: Start Admin Dashboard

```bash
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/src/ev_client_app/langchain/
./scripts/start_admin.sh
```

Starts the admin dashboard on port 9050.

### Step 4: Access Dashboards

| Service | URL | Port |
|---------|-----|------|
| Admin Dashboard | `http://localhost:9050` | 9050 |
| EV_101 Dashboard | `http://localhost:9010` | 9010 |
| EV_102 Dashboard | `http://localhost:9011` | 9011 |
| ... | ... | ... |
| EV_110 Dashboard | `http://localhost:9019` | 9019 |

### Step 5: Run ML Pipelines (Optional)

**Training (manual):**
```bash
# Via Airflow UI at http://localhost:8080
# OR via CLI:
airflow dags trigger ev_battery_training_dag --conf '{"hdfs_url": "http://localhost:9870", "user_id": "system_admin"}'
```

**Inference (runs daily at midnight automatically, or manually):**
```bash
airflow dags trigger ev_battery_inference_dag
```

**AIAPI (direct API calls):**
```bash
# Training
curl -X POST http://localhost:8000/api/v1/train \
  -H "Content-Type: application/json" \
  -d '{"HDFS_URL": "http://localhost:9870", "user_id": "system_admin"}'

# Poll result
curl http://localhost:8000/api/v1/jobs/{job_id}
```

### Step 6: Generate Training Data (Optional)

```bash
# Quick data generation for all cars
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/src/ev_client_app/langchain/
python quick_data_gen.py --all-cars --mode both

# Single car, specific phases
python quick_data_gen.py --car-id EV_104 --car-model SimuProA-4 --mode both \
  --drive-start 90 --drive-end 15 --charge-start 10 --charge-end 90

# HDFS Battery Sampler
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/src/
python battery_hdfs_sampler.py
```

### Step 7: Stop Everything

```bash
# Stop EV fleet
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/src/ev_client_app/langchain/
./scripts/stop_all.sh

# Stop Docker infrastructure
cd /home/yht7hc/original_genai/eet-dp-predictive-ai-concept/infra
docker compose down
```

---

## 6. Port Mapping

### Infrastructure Ports

| Service | Port | Purpose |
|---------|------|---------|
| Kafka | 9092 | PLAINTEXT broker |
| HDFS NameNode RPC | 8020 | Hadoop RPC |
| HDFS NameNode HTTP | 9870 | Web UI |
| HDFS DataNode HTTP | 9864 | DataNode UI |
| HDFS DataNode Transfer | 9866 | Data transfer |
| YARN ResourceManager | 8088 | YARN Web UI |
| PostgreSQL | 45432 | Airflow/DB (host:container 45432:5432) |
| pgAdmin | 46016 | DB admin UI |
| Redis | 6379 | Celery broker |
| Airflow API | 8080 | Airflow REST API |

### Application Ports

| Service | Port | Description |
|---------|------|-------------|
| AIAPI | 8000 | ML backend service |
| Admin Dashboard | 9050 | Fleet supervisory UI |
| EV_103 | 8001 / 9001 | Backend / Frontend |
| EV_104 | 8002 / 9002 | Backend / Frontend |
| EV_105 | 8003 / 9003 | Backend / Frontend |
| EV_101 | 8010 / 9010 | Backend / Frontend |
| EV_102 | 8011 / 9011 | Backend / Frontend |
| EV_106 | 8004 / 9004 | Backend / Frontend |
| EV_107 | 8006 / 9006 | Backend / Frontend (8005 skipped) |
| EV_108 | 8007 / 9007 | Backend / Frontend |
| EV_109 | 8008 / 9008 | Backend / Frontend |
| EV_110 | 8009 / 9009 | Backend / Frontend |

Port allocation is dynamic — each `start_EV_*.sh` script scans upward from its base port, skipping 8005 and 8050, ensuring both backend and frontend ports are free before starting.

---

## 7. Configuration

### Environment Variables (`infra/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST_NAME` | `localhost` | Hostname for Docker networking and Kafka advertised listeners |
| `DATA_ROOT_PATH` | `./data` | Base path for all Docker volume mounts |
| `AIRFLOW_PROJ_DIR` | `../src/airflow` | Airflow source code mount path |
| `AIRFLOW_UID` | `1000` | UID for Airflow containers |
| `REDIS_PASSWORD` | `redis123` | Redis authentication |
| `_PIP_ADDITIONAL_REQUIREMENTS` | (multi-line) | Extra pip packages for Airflow containers: kafka-python, pyspark, delta-spark, hdfs, python-dotenv, pyyaml, pendulum, matplotlib, etc. |
| `LLM_API_URL` | `http://hc1-c-0003u:30000/v1/chat/completions` | OpenAI-compatible LLM API endpoint |
| `LLM_API_KEY` | `EMPTY` | LLM API key |
| `LLM_MODEL` | `/models/gemma-4-31B-it-FP8` | Model identifier |
| `DB_USER` | `airflow` | PostgreSQL username |
| `DB_PASSWORD` | `airflow` | PostgreSQL password |
| `DB_HOST` | `hc1-c-0003u.hc.apac.bosch.com` | Database host |
| `DB_PORT` | `45432` | Database port |
| `DB_NAME` | `ev_tracker_app` | Database name |
| `KAFKA_BROKERS` | `hc1-c-0003u.hc.apac.bosch.com:9092` | Kafka broker connection string |

### AIAPI Configuration (`src/AIAPI/core/config.py`)

| Constant | Default | Description |
|----------|---------|-------------|
| `HDFS_URL` | `http://hc1-c-0003u.hc.apac.bosch.com:9870` | HDFS NameNode URL |
| `HDFS_USER` | `hdfs` | HDFS user |
| `RAW_DATA_DIR` | `/raw_data/battery_telemetry_v4` | Raw data path on HDFS |
| `INFERENCE_BASE_DIR` | `/raw_data/battery_telemetry_v4` | Inference data path |
| `WINDOW_SIZE` | `128` | Sliding window size (rows) |
| `FEATURE_COLS` | `volt_V, current_A, soc_pct, max_single_volt_V, min_single_volt_V, max_temp_C, min_temp_C` | ML features |
| `AUTH_ENABLED` | `False` | Azure AD auth toggle |

### EV Agent Configuration (`src/ev_client_app/langchain/core/constants.py`)

| Constant | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `/models/gemma-4-31B-it-FP8` | LLM model |
| `LLM_TEMPERATURE` | `0.85` | Generation temperature |
| `LLM_MAX_RETRIES` | `2` | Max LLM API retries |
| `LLM_TIMEOUT` | `600` | LLM API timeout (seconds) |
| `RECORD_INTERVAL_SECONDS` | `3` | Time between batches |
| `KAFKA_BROKERS` | `hc1-c-0003u.hc.apac.bosch.com:9092` | Kafka broker |
| `TELEMETRY_TOPIC` | `ev.battery.telemetry_v4` | Kafka topic |

### Docker Compose Services

| Service | Image | Purpose |
|---------|-------|---------|
| `kafka` | `confluentinc/cp-kafka:7.7.7` | Kafka broker (KRaft mode) |
| `namenode` | `apache/hadoop:3.4.2` | HDFS NameNode |
| `datanode-1` | `apache/hadoop:3.4.2` | HDFS DataNode |
| `resourcemanager` | `apache/hadoop:3.4.2` | YARN ResourceManager |
| `nodemanager-1` | `apache/hadoop:3.4.2` | YARN NodeManager |
| `postgres` | `postgres:17` | PostgreSQL (Airflow metadata + app DB) |
| `pgadmin` | `dpage/pgadmin4:latest` | PostgreSQL admin UI |
| `redis` | `redis:7.2.4` | Redis (Celery broker) |
| `airflow-apiserver` | Custom | Airflow REST API |
| `airflow-scheduler` | Custom | Airflow DAG scheduler |
| `airflow-dag-processor` | Custom | DAG processor |
| `airflow-worker` | Custom | Celery worker |
| `airflow-triggerer` | Custom | Airflow triggerer |
| `flower` | Custom | Celery monitoring (optional profile) |
