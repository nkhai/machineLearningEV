"""
Standalone admin server.

Serves the admin frontend (admin.html + admin.js) and provides all /api/*
endpoints: vehicle CRUD via PostgreSQL, SSE streaming, and Kafka consumer
for real-time telemetry.

Run:
    cd src/plotlydash
    PYTHONPATH=../ev_client_app:$PYTHONPATH uvicorn admin_server:app --host 0.0.0.0 --port 9050

Or from project root:
    PYTHONPATH=src/ev_client_app:$PYTHONPATH uvicorn plotlydash.admin_server:app --host 0.0.0.0 --port 9050
"""

import asyncio
import json
import os
import sys
import tempfile
import threading

import pandas as pd

# Load .env from project root/infra/ before any DB imports
_current_dir = os.path.dirname(os.path.abspath(__file__))
_env_candidates = [
    os.path.join(_current_dir, "..", "..", "infra", ".env"),
    os.path.join(_current_dir, "..", ".env"),
    os.path.join(_current_dir, ".env"),
]
from dotenv import load_dotenv
for _env_path in _env_candidates:
    if os.path.isfile(_env_path):
        print(f"[Admin] Loading .env from {_env_path}")
        load_dotenv(_env_path, override=True)
        break

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Add ev_client_app to path so we can import database and core modules
_ev_client_dir = os.path.join(_current_dir, "..", "ev_client_app")
if _ev_client_dir not in sys.path:
    sys.path.insert(0, _ev_client_dir)

from database.connection import get_db, engine, Base
from database import crud, schemas
from langchain.core.state import (
    get_latest_status_record,
    get_status_history,
    set_latest_status_record,
    add_log,
)

# ===========================
# CONFIG
# ===========================
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "hc1-c-0003u.hc.apac.bosch.com:9092").split(",")
STATUS_TOPIC = os.getenv("STATUS_TOPIC", "ev.battery.telemetry_v4")
ADMIN_GROUP_ID = "admin-status-group"

# ===========================
# HDFS CONFIG
# ===========================
HDFS_URL = os.getenv("HDFS_URL", "http://hc1-c-0003u.hc.apac.bosch.com:9870")
HDFS_USER_VAR = os.getenv("HDFS_USER", "hdfs")
HDFS_RAW_DIR = "/raw_data/battery_telemetry_v4"

consumer_stop_event = threading.Event()

# ===========================
# FASTAPI INIT
# ===========================
app = FastAPI(title="EV Admin Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (admin.js, admin.html) from the same directory
app.mount("/static", StaticFiles(directory=_current_dir), name="static")

# ===========================
# FRONTEND ROUTE
# ===========================
@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(_current_dir, "admin.html"))

# ===========================
# STARTUP
# ===========================
@app.on_event("startup")
def startup():
    # Ensure DB tables exist (non-fatal if DB is unreachable)
    try:
        Base.metadata.create_all(bind=engine)
        add_log("INFO", "admin_server", "Database tables ensured")
    except Exception as e:
        add_log("ERROR", "admin_server", f"Could not ensure DB tables: {e}. Continuing anyway...")

    # Start Kafka consumer in background thread
    start_admin_consumer()


import time # Nhớ thêm thư viện này ở đầu file cùng với os, sys...

def start_admin_consumer():
    """Start the Kafka consumer thread for real-time telemetry with retry."""
    try:
        import kafka
        from kafka import KafkaConsumer
        from kafka.errors import NoBrokersAvailable
    except ImportError:
        add_log("WARNING", "admin_server", "kafka-python not installed, skipping Kafka consumer")
        return

    def admin_loop():
        # Vòng lặp vĩnh cửu giúp Thread sống lại nếu Kafka bị rớt
        while not consumer_stop_event.is_set():
            consumer = None
            try:
                consumer = KafkaConsumer(
                    STATUS_TOPIC,
                    bootstrap_servers=KAFKA_BROKERS,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    group_id=ADMIN_GROUP_ID,
                    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                    key_deserializer=lambda x: x.decode("utf-8") if x else None,
                )
                add_log("INFO", "admin_server", f"Connected to Kafka topic: {STATUS_TOPIC}")

                for message in consumer:
                    if consumer_stop_event.is_set():
                        break
                    try:
                        record = message.value
                        car_id = message.key
                        if not car_id and isinstance(record, dict):
                            car_id = record.get("car_id")
                        if not car_id:
                            continue

                        set_latest_status_record(car_id, record)
                        # Comment lại dòng DEBUG này để tránh trôi log admin nếu có quá nhiều xe
                        # add_log("DEBUG", "admin_server", f"[Telemetry] EV={car_id} ts={record.get('timestamp_s')}")
                    except Exception:
                        import traceback
                        add_log("ERROR", "admin_server", traceback.format_exc())

            except NoBrokersAvailable:
                add_log("ERROR", "admin_server", "Cannot connect to Kafka broker. Retrying in 5 seconds...")
                time.sleep(5) # Rest 5 seconds then loop to try reconnecting
            except Exception as e:
                add_log("ERROR", "admin_server", f"Kafka consumer error: {e}. Retrying in 5 seconds...")
                time.sleep(5)
            finally:
                if consumer:
                    try:
                        consumer.close()
                    except:
                        pass
        
        add_log("INFO", "admin_server", "Admin consumer stopped")

    thread = threading.Thread(target=admin_loop, daemon=True)
    thread.start()
    add_log("INFO", "admin_server", "Admin Kafka consumer thread started")

# ===========================
# API ENDPOINTS
# ===========================

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    vehicles = crud.list_vehicles(db)
    return {"status": "ok", "vehicle_count": len(vehicles)}


@app.get("/api/ev")
def list_all_vehicles(db: Session = Depends(get_db)):
    vehicles = crud.list_vehicles(db)
    return [
        {
            "car_id": v.car_id,
            "car_name": v.car_name,
            "vin_number": v.vin_number,
            "license_plate": v.license_plate,
            "battery_serial": v.battery_serial,
            "motor_serial": v.motor_serial,
            "user_id": v.user_id,
        }
        for v in vehicles
    ]


@app.get("/api/ev/{car_id}/details")
def get_vehicle_details(car_id: str, db: Session = Depends(get_db)):
    v = crud.get_vehicle(db, car_id)
    if not v:
        return {}
    return {
        "car_id": v.car_id,
        "car_name": v.car_name,
        "vin_number": v.vin_number,
        "license_plate": v.license_plate,
        "battery_serial": v.battery_serial,
        "motor_serial": v.motor_serial,
        "user_id": v.user_id,
    }


@app.post("/api/ev")
def register_vehicle(vehicle: schemas.VehicleCreate, db: Session = Depends(get_db)):
    add_log("INFO", "admin_server", f"Register vehicle request: {vehicle.car_id}")
    existing = crud.get_vehicle(db, vehicle.car_id)

    if existing:
        if not vehicle.user_id:
            raise HTTPException(status_code=400, detail="user_id is required to update a vehicle")
        updated = crud.update_vehicle(
            db=db,
            car_id=vehicle.car_id,
            car_name=vehicle.car_name,
            vin_number=vehicle.vin_number,
            license_plate=vehicle.license_plate,
            battery_serial=vehicle.battery_serial,
            motor_serial=vehicle.motor_serial,
            user_id=vehicle.user_id,
        )
        add_log("INFO", "admin_server", f"Vehicle updated in PostgreSQL: {vehicle.car_id}")
        return {
            "message": "Vehicle updated",
            "car_id": updated.car_id,
            "car_name": updated.car_name,
        }

    v = crud.create_vehicle(
        db=db,
        car_id=vehicle.car_id,
        car_name=vehicle.car_name,
        vin_number=vehicle.vin_number,
        license_plate=vehicle.license_plate,
        battery_serial=vehicle.battery_serial,
        motor_serial=vehicle.motor_serial,
        user_id=vehicle.user_id,
    )
    add_log("INFO", "admin_server", f"Vehicle saved to PostgreSQL: {v.car_id}")
    return {
        "message": "Vehicle registered",
        "car_id": v.car_id,
        "car_name": v.car_name,
    }


@app.get("/api/status/latest/{car_id}")
def api_status_latest(car_id: str):
    return get_latest_status_record(car_id) or {}


@app.get("/api/status/history/{car_id}")
def api_status_history(car_id: str):
    return get_status_history(car_id)


@app.get("/api/status/stream/{car_id}")
async def api_status_stream(car_id: str, request: Request):
    async def event_generator():
        last_ts = None
        add_log("INFO", "admin_server", f"SSE client connected ({car_id})")
        try:
            while True:
                if await request.is_disconnected():
                    add_log("INFO", "admin_server", f"SSE client disconnected ({car_id})")
                    break
                record = get_latest_status_record(car_id)
                if record and record.get("timestamp_s") != last_ts:
                    last_ts = record["timestamp_s"]
                    yield f"data: {json.dumps(record)}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            add_log("DEBUG", "admin_server", f"SSE task cancelled ({car_id})")
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ===========================
# HDFS ENDPOINTS
# ===========================

@app.get("/api/hdfs/history/{car_id}")
def get_hdfs_history(car_id: str, metric: str = "soc_pct", limit: int = 1000):
    """Read the latest CSV from HDFS for a given car and return time-series data for charting."""
    try:
        from hdfs import InsecureClient
    except ImportError:
        raise HTTPException(status_code=500, detail="hdfs package not installed")

    try:
        client = InsecureClient(HDFS_URL, user=HDFS_USER_VAR, timeout=30)

        # Try per-car subdirectory first (e.g. /raw_data/.../EV_101/), then flat listing
        car_dir = f"{HDFS_RAW_DIR}/{car_id}"
        try:
            files = client.list(car_dir)
            base_dir = car_dir
        except Exception:
            all_items = client.list(HDFS_RAW_DIR)
            files = [f for f in all_items if car_id in f and f.endswith(".csv")]
            base_dir = HDFS_RAW_DIR

        csv_files = sorted([f for f in files if f.endswith(".csv")])
        if not csv_files:
            return {"timestamps": [], "values": [], "car_id": car_id, "metric": metric,
                    "error": f"No CSV files found for {car_id} on HDFS"}

        # Use the latest file
        latest_file = csv_files[-1]
        hdfs_path = f"{base_dir}/{latest_file}"

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            client.download(hdfs_path, tmp_path, overwrite=True)
            df = pd.read_csv(tmp_path)
        finally:
            os.unlink(tmp_path)

        if metric not in df.columns:
            return {"timestamps": [], "values": [], "car_id": car_id, "metric": metric,
                    "error": f"Column '{metric}' not found in file (available: {list(df.columns)[:10]})"}

        if "timestamp_s" in df.columns:
            df = df.sort_values("timestamp_s")

        # Downsample to requested limit
        if len(df) > limit:
            step = max(1, len(df) // limit)
            df = df.iloc[::step].reset_index(drop=True)

        timestamps = df["timestamp_s"].tolist() if "timestamp_s" in df.columns else list(range(len(df)))
        values = df[metric].fillna(0).tolist()

        add_log("INFO", "admin_server", f"HDFS history loaded for {car_id}: {len(df)} rows from {latest_file}")
        return {
            "timestamps": timestamps,
            "values": values,
            "car_id": car_id,
            "metric": metric,
            "file": latest_file,
            "rows": len(df),
        }
    except HTTPException:
        raise
    except Exception as e:
        add_log("ERROR", "admin_server", f"HDFS history error for {car_id}: {e}")
        raise HTTPException(status_code=500, detail=f"HDFS error: {str(e)}")


# ===========================
# SHUTDOWN
# ===========================
@app.on_event("shutdown")
def shutdown():
    add_log("INFO", "admin_server", "Shutting down admin server...")
    consumer_stop_event.set()
