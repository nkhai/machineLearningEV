import asyncio
import json
import os
import sys
import threading
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load .env from project root/infra/
_current_dir = os.path.dirname(os.path.abspath(__file__))
for _candidate in [
    os.path.join(_current_dir, "..", "..", "infra", ".env"),
    os.path.join(_current_dir, "..", ".env"),
    os.path.join(_current_dir, ".env"),
]:
    if os.path.isfile(_candidate):
        load_dotenv(_candidate, override=True)
        break

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=9001)
parser.add_argument("--car_id", type=str, default="EV_101")
parser.add_argument("--car_name", type=str, default="Unknown Model")
parser.add_argument("--vin", type=str, default="N/A")
args = parser.parse_args()

CAR_ID = args.car_id
CAR_NAME = args.car_name
VIN = args.vin
PORT = args.port

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "hc1-c-0003u.hc.apac.bosch.com:9092").split(",")
STATUS_TOPIC = os.getenv("STATUS_TOPIC", "ev.battery.telemetry_v4")

# State
stop_event = threading.Event()
latest_record: dict = {}
current_label: int = 0
label_lock = threading.Lock()
trend_data: list = []
MAX_TREND_POINTS = 50

def set_record(record: dict):
    global latest_record
    latest_record = record

def get_record() -> dict:
    return latest_record

def set_label(label: int):
    global current_label
    with label_lock:
        current_label = label

def get_label() -> int:
    with label_lock:
        return current_label

def add_trend_point(value: float):
    global trend_data
    trend_data.append({"time": datetime.now().timestamp(), "volt": value})
    if len(trend_data) > MAX_TREND_POINTS:
        trend_data = trend_data[-MAX_TREND_POINTS:]

app = FastAPI(title=f"EV {CAR_ID} Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=_current_dir), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(_current_dir, "user.html"))

@app.get("/api/config")
def api_get_config():
    """Return static configuration info of the EV initialized from script."""
    return {
        "car_id": CAR_ID,
        "car_name": CAR_NAME,
        "vin": VIN
    }

@app.post("/api/set_label")
async def api_set_label(request: Request):
    body = await request.json()
    set_label(body.get("label", 0))
    return {"label": get_label()}

@app.get("/api/label")
def api_get_label():
    return {"label": get_label()}

@app.get("/api/trend")
def api_get_trend():
    return trend_data

@app.get("/api/status/stream")
async def api_status_stream(request: Request):
    async def event_generator():
        last_ts = None
        try:
            while True:
                if await request.is_disconnected():
                    break
                record = get_record()
                if record and record.get("timestamp_s") != last_ts:
                    last_ts = record["timestamp_s"]
                    yield f"data: {json.dumps(record)}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Kafka consumer
def start_consumer():
    try:
        from kafka import KafkaConsumer
        from kafka.errors import NoBrokersAvailable
    except ImportError:
        print("[User] kafka-python not installed, skipping Kafka consumer")
        return

    def loop():
        consumer = None
        try:
            consumer = KafkaConsumer(
                STATUS_TOPIC,
                bootstrap_servers=KAFKA_BROKERS,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                group_id=f"user-{CAR_ID}-group",
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                key_deserializer=lambda x: x.decode("utf-8") if x else None,
            )
            print(f"[User] Connected to Kafka topic: {STATUS_TOPIC}")
            for msg in consumer:
                if stop_event.is_set():
                    break
                try:
                    rec = msg.value
                    cid = msg.key or rec.get("car_id")
                    if cid == CAR_ID:
                        set_record(rec)
                        volt = rec.get("volt_V", 0)
                        if isinstance(volt, (int, float)):
                            add_trend_point(volt)
                except Exception as e:
                    print(f"[User] Consumer error: {e}")
        except NoBrokersAvailable:
            print("[User] Cannot connect to Kafka broker")
        finally:
            if consumer:
                consumer.close()

    threading.Thread(target=loop, daemon=True).start()

@app.on_event("startup")
def startup():
    start_consumer()

@app.on_event("shutdown")
def shutdown():
    stop_event.set()

if __name__ == "__main__":
    print(f"Starting EV {CAR_ID} dashboard on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
