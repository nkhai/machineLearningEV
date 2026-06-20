"""
HDFS Battery Data Sampler

Reads raw CSV telemetry files from HDFS, queries DB for eligible cars
(use_to_predict=False), runs GlobalSnippetBuffer windowing, and clusters +
stratified-samples a small subset, then writes results back to HDFS.

Reuses shared modules from src/AIAPI/core/ for:
  - GlobalSnippetBuffer (windowing + metadata extraction)
  - get_hdfs_files_filtered (HDFS discovery with car/date filter)
  - load_data_universal (chunked CSV loading with retry)
  - filter_by_modality (charging vs driving split)
  - extract_features_2d (flattened feature matrix for clustering)
"""
import os
import io
import sys
import json
import warnings
import time

import numpy as np
import pandas as pd
from collections import defaultdict
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score
from hdfs import InsecureClient

warnings.filterwarnings("ignore")
np.random.seed(42)

# ================================================================
# Path setup — allow imports from AIAPI/core/ and ev_client_app/
# ================================================================
_HERE = os.path.dirname(os.path.abspath(__file__))

AIAPI_DIR = os.path.join(_HERE, "AIAPI")
EV_APP = os.path.join(_HERE, "ev_client_app")

for _p in (AIAPI_DIR, EV_APP):
    abs_p = os.path.abspath(_p)
    if abs_p not in sys.path:
        sys.path.insert(0, abs_p)

# ================================================================
# DB: Query eligible cars (use_to_predict = False)
# ================================================================
from dotenv import load_dotenv
_env_path = os.path.join(_HERE, '..', 'infra', '.env')
load_dotenv(_env_path, override=True)

from ev_client_app.database.connection import SessionLocal

db = SessionLocal()
try:
    result = db.execute(
        __import__('sqlalchemy').text(
            "SELECT car_id FROM vehicles WHERE use_to_predict = false"
        )
    )
    ELIGIBLE_CARS = [row[0] for row in result.fetchall()]
except Exception as e:
    print(f"[DB] Could not query DB: {e}")
    ELIGIBLE_CARS = None
finally:
    db.close()

print(f"[DB] Eligible cars (use_to_predict=False): {ELIGIBLE_CARS}")
if not ELIGIBLE_CARS:
    raise RuntimeError("No vehicles with use_to_predict=False. Update the vehicles table first.")

# ================================================================
# CONFIG
# ================================================================
from core.config import HDFS_URL, HDFS_USER, WINDOW_SIZE

RAW_DATA_DIR = "/raw_data/battery_telemetry_v4"
OUTPUT_DIR   = "/raw_sample_data/sampled_training"
REGISTRY_FILE = f"{OUTPUT_DIR}/processed_registry.json"

K_RANGE    = range(5, 21)
N_SAMPLE   = 1000
FILE_LIMIT = None
MIN_DATE   = None
MODALITY   = "all"  # 'all', 'charging', or 'driving'

ALL_OUTPUT_COLS = [
    "id", "id_segment", "volt_V", "current_A", "soc_pct", "max_single_volt_V",
    "min_single_volt_V", "max_temp_C", "min_temp_C", "timestamp_s", "avg_speed_kmh",
    "hvac_active", "payload_kg", "regenerative_braking_Ah", "motor_rpm", "gear_position",
    "accelerator_pedal_pct", "brake_pedal_pct", "charger_connected", "label",
    "car_id", "car_model", "mileage_km", "actual_max_capacity_Ah", "nominal_capacity_Ah"
]

print("[Config] Ready")

# ================================================================
# Import shared modules from AIAPI/core/
# ================================================================
from core.data_utils import (
    get_hdfs_files_filtered,
    load_data_universal,
    filter_by_modality,
)
from core.split_and_extract import extract_features_2d


def _safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# ================================================================
# HDFS Connection & File Discovery
# ================================================================
client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=300)
print(f"[HDFS] Connected to {HDFS_URL}")

all_csv_files = get_hdfs_files_filtered(
    client, RAW_DATA_DIR,
    min_date_str=MIN_DATE, limit=FILE_LIMIT, eligible_cars=ELIGIBLE_CARS
)
print(f"[HDFS] Found {len(all_csv_files)} total CSV files for eligible cars.")

if not all_csv_files:
    raise RuntimeError("No CSV files found. Check RAW_DATA_DIR, FILE_LIMIT, and vehicle use_to_predict flag.")

# --- Load processed registry for incremental processing ---
processed_registry = set()
try:
    with client.read(REGISTRY_FILE, encoding='utf-8') as reader:
        processed_registry = set(json.load(reader))
    print(f"[Incremental] Loaded {len(processed_registry)} previously processed files from HDFS.")
except Exception:
    print("[Incremental] No previous registry found on HDFS. Starting fresh.")

csv_files = [f for f in all_csv_files if f not in processed_registry]
print(f"[Incremental] -> Found {len(csv_files)} NEW files to process.")

if not csv_files:
    print("\n[Incremental] All files are already processed! Exiting early to save time.")
    sys.exit(0)

# ================================================================
# Data Loading (reuses shared load_data_universal)
# ================================================================
data = load_data_universal(client, csv_files, mode='train')

if not data:
    print("[Warning] No valid samples extracted from the new files. Updating registry and exiting.")
    processed_registry.update(csv_files)
    with client.write(REGISTRY_FILE, overwrite=True, encoding='utf-8') as writer:
        json.dump(list(processed_registry), writer)
    sys.exit(0)

print(f"[Data] Samples: {len(data):,}")

# ================================================================
# Modality Filter (reuses shared filter_by_modality)
# ================================================================
if MODALITY == "charging":
    data_work = filter_by_modality(data, is_charge=True)
elif MODALITY == "driving":
    data_work = filter_by_modality(data, is_charge=False)
else:
    data_work = data

# ================================================================
# Feature Extraction for Clustering (reuses shared extract_features_2d)
# ================================================================
X, y = extract_features_2d(data_work)
print(f"[Modality] Working set (New data): {len(data_work):,} samples  |  X={X.shape}")

# ================================================================
# Preprocessing
# ================================================================
mask_valid = np.isfinite(X).all(axis=1)
X_clean    = X[mask_valid]

scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X_clean)

# ================================================================
# Clustering (only on NEW data)
# ================================================================
MAX_SUBSET = 20_000
if len(X_scaled) > MAX_SUBSET:
    X_sub = X_scaled[np.random.choice(len(X_scaled), MAX_SUBSET, replace=False)]
else:
    X_sub = X_scaled

sil_scores = []
for k in K_RANGE:
    km  = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=2048)
    lbl = km.fit_predict(X_sub)
    sil = silhouette_score(X_sub, lbl, sample_size=min(5000, len(X_sub)))
    sil_scores.append(sil)

best_k = list(K_RANGE)[np.argmax(sil_scores)]
km     = MiniBatchKMeans(n_clusters=best_k, random_state=42, n_init=5, batch_size=4096)
labels = km.fit_predict(X_scaled)

# ================================================================
# Stratified Sampling
# ================================================================
valid_indices = np.where(mask_valid)[0]
cluster_to_orig = {}
for pos, orig_idx in enumerate(valid_indices):
    cluster_to_orig.setdefault(labels[pos], []).append(orig_idx)

cluster_counts = {c: len(v) for c, v in cluster_to_orig.items()}
total_valid    = sum(cluster_counts.values())

sampled_indices = []
for c, orig_idxs in cluster_to_orig.items():
    n_from = max(1, round(N_SAMPLE * cluster_counts[c] / total_valid))
    n_from = min(n_from, len(orig_idxs))
    chosen = np.random.choice(orig_idxs, n_from, replace=False)
    sampled_indices.extend(chosen.tolist())

sampled_indices = sorted(set(sampled_indices))
if len(sampled_indices) > N_SAMPLE:
    sampled_indices = sorted(np.random.choice(sampled_indices, N_SAMPLE, replace=False).tolist())

sampled_data = [data_work[i] for i in sampled_indices]

# ================================================================
# Save to HDFS & Update Registry
# ================================================================
try:
    client.status(OUTPUT_DIR)
except Exception:
    client.makedirs(OUTPUT_DIR)

file_to_samples = defaultdict(list)
for sample in sampled_data:
    _, meta, _ = sample
    for fp in meta["file_paths"]:
        file_to_samples[fp].append(sample)

saved_csv_paths = []
newly_processed_files = set()

for src_path, samples in file_to_samples.items():
    basename = os.path.basename(src_path)
    out_path = f"{OUTPUT_DIR}/{basename}"

    all_rows = []
    for values, meta, window_df in samples:
        for row_idx in range(WINDOW_SIZE):
            wr = window_df.iloc[row_idx]
            row = {
                "id": wr.get("id", ""),
                "id_segment": meta["id_segment"],
                "volt_V": _safe_float(wr.get("volt_V", 0)),
                "current_A": _safe_float(wr.get("current_A", 0)),
                "soc_pct": _safe_float(wr.get("soc_pct", 0)),
                "max_single_volt_V": _safe_float(wr.get("max_single_volt_V", 0)),
                "min_single_volt_V": _safe_float(wr.get("min_single_volt_V", 0)),
                "max_temp_C": _safe_float(wr.get("max_temp_C", 0)),
                "min_temp_C": _safe_float(wr.get("min_temp_C", 0)),
                "timestamp_s": wr.get("timestamp_s", 0),
                "avg_speed_kmh": _safe_float(wr.get("avg_speed_kmh", 0)),
                "hvac_active": _safe_int(wr.get("hvac_active", 0)),
                "payload_kg": _safe_float(wr.get("payload_kg", 0)),
                "regenerative_braking_Ah": _safe_float(wr.get("regenerative_braking_Ah", 0)),
                "motor_rpm": _safe_float(wr.get("motor_rpm", 0)),
                "gear_position": wr.get("gear_position", 0),
                "accelerator_pedal_pct": _safe_float(wr.get("accelerator_pedal_pct", 0)),
                "brake_pedal_pct": _safe_float(wr.get("brake_pedal_pct", 0)),
                "charger_connected": meta["charger_connected"],
                "label": meta["label"],
                "car_id": meta["car_id"],
                "car_model": meta["car_model"],
                "mileage_km": meta["mileage_km"],
                "actual_max_capacity_Ah": meta["actual_max_capacity_Ah"],
                "nominal_capacity_Ah": meta["nominal_capacity_Ah"],
            }
            all_rows.append(row)

    df_out = pd.DataFrame(all_rows)
    df_out = df_out[[c for c in ALL_OUTPUT_COLS if c in df_out.columns]]

    csv_buf = io.StringIO()
    df_out.to_csv(csv_buf, index=False)
    csv_data = csv_buf.getvalue().encode("utf-8")

    max_retries = 3
    success = False

    for attempt in range(1, max_retries + 1):
        try:
            with client.write(out_path, overwrite=True) as wf:
                wf.write(csv_data)
            saved_csv_paths.append(out_path)
            print(f"[HDFS] Saved {out_path}  ({len(all_rows):,} rows)")
            success = True
            newly_processed_files.add(src_path)
            break

        except Exception as e:
            err_type = type(e).__name__
            print(f"  -> [Warning] Write failed for {basename} (attempt {attempt}/{max_retries}): {err_type}")
            time.sleep(3)

    if not success:
        print(f"  -> [Error] Skipped {basename} after {max_retries} failed attempts.")

# Files that produced no output still go into registry
empty_files = set(csv_files) - set(file_to_samples.keys())
newly_processed_files.update(empty_files)

# --- Update registry on HDFS ---
processed_registry.update(newly_processed_files)
try:
    with client.write(REGISTRY_FILE, overwrite=True, encoding='utf-8') as writer:
        json.dump(list(processed_registry), writer)
    print(f"\n[Incremental] Updated registry! Now tracking {len(processed_registry)} total files.")
except Exception as e:
    print(f"\n[Incremental] Warning: Failed to save registry to HDFS. Error: {e}")

# ================================================================
# Summary
# ================================================================
print("=" * 55)
print(f"  Total eligible raw files : {len(all_csv_files)}")
print(f"  Files skipped (cached)   : {len(all_csv_files) - len(csv_files)}")
print(f"  Files processed (NEW)    : {len(csv_files)}")
print(f"  Valid samples found      : {len(sampled_data):,}")
print(f"  Best K                   : {best_k}")
print(f"  HDFS output dir          : {OUTPUT_DIR}/")
print(f"    - {len(saved_csv_paths)} NEW sampled CSV files")
print(f"    - Registry updated at {REGISTRY_FILE}")
print("=" * 55)
