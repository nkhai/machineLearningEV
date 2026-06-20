"""
Admin FastAPI app using the LangChain pipeline.

Provides vehicle CRUD endpoints and admin status streaming.

Usage:
    uvicorn admin.main:app --host 0.0.0.0 --port 8050
"""

import asyncio
import json
import threading

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database.connection import get_db
from database import crud, schemas

from admin.consumer import start_admin_consumer
from core.state import (
    get_latest_status_record,
    get_status_history,
    add_log,
)

# ===========================
# CONFIG
# ===========================
consumer_stop_event = threading.Event()
status_thread = None

# ===========================
# FASTAPI INIT
# ===========================
app = FastAPI(title="Admin EV Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================
# STARTUP
# ===========================
@app.on_event("startup")
def startup():
    global status_thread

    add_log("INFO", "admin", "Admin backend starting...")

    consumer_stop_event, status_thread = start_admin_consumer()
    add_log("INFO", "admin", "Admin status consumer started")

# ===========================
# API ENDPOINTS
# ===========================

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
        add_log("INFO", "admin", f"SSE client connected (status, {car_id})")
        try:
            while True:
                if await request.is_disconnected():
                    add_log("INFO", "admin", f"SSE client disconnected (status, {car_id})")
                    break
                record = get_latest_status_record(car_id)
                if record and record.get("timestamp_s") != last_ts:
                    last_ts = record["timestamp_s"]
                    yield f"data: {json.dumps(record)}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            add_log("DEBUG", "admin", f"SSE status task cancelled ({car_id})")
            raise
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/ev")
def register_vehicle(vehicle: schemas.VehicleCreate, db: Session = Depends(get_db)):
    add_log("INFO", "admin", f"Register vehicle request: {vehicle.car_id}")

    existing = crud.get_vehicle(db, vehicle.car_id)

    if existing:
        updated = crud.update_vehicle(
            db=db,
            car_id=vehicle.car_id,
            car_name=vehicle.car_name,
            vin_number=vehicle.vin_number,
            license_plate=vehicle.license_plate,
            battery_serial=vehicle.battery_serial,
            motor_serial=vehicle.motor_serial,
            user_id=vehicle.user_id
        )
        add_log("INFO", "admin", f"Vehicle updated in PostgreSQL: {vehicle.car_id}")
        return {
            "message": "Vehicle updated",
            "car_id": updated.car_id,
            "car_name": updated.car_name,
            "vin_number": updated.vin_number,
            "license_plate": updated.license_plate,
            "battery_serial": updated.battery_serial,
            "motor_serial": updated.motor_serial,
            "user_id": updated.user_id
        }

    v = crud.create_vehicle(
        db=db,
        car_id=vehicle.car_id,
        car_name=vehicle.car_name,
        vin_number=vehicle.vin_number,
        license_plate=vehicle.license_plate,
        battery_serial=vehicle.battery_serial,
        motor_serial=vehicle.motor_serial,
        user_id=vehicle.user_id
    )

    add_log("INFO", "admin", f"Vehicle saved to PostgreSQL: {v.car_id}")

    return {
        "message": "Vehicle registered",
        "car_id": v.car_id,
        "car_name": v.car_name,
        "vin_number": v.vin_number,
        "license_plate": v.license_plate,
        "battery_serial": v.battery_serial,
        "motor_serial": v.motor_serial,
        "user_id": v.user_id
    }

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
        "user_id": v.user_id
    }

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    vehicles = crud.list_vehicles(db)
    return {
        "status": "ok",
        "vehicle_count": len(vehicles)
    }

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
            "user_id": v.user_id
        }
        for v in vehicles
    ]

# ===========================
# SHUTDOWN
# ===========================
@app.on_event("shutdown")
def shutdown():
    add_log("INFO", "admin", "Shutting down admin backend...")
    consumer_stop_event.set()
    add_log("INFO", "admin", "Stop signal sent to admin status consumer")
