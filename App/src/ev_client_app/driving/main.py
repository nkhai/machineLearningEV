import asyncio
import json
import os
import threading
from pydantic import BaseModel
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from producer import producer_loop
from client_consumer import telemetry_consumer_loop
from state import latest_record, history, add_log, ev_control_state, ev_state_lock, get_ev_label, set_ev_label, latest_status_record, status_history

from dotenv import load_dotenv
import os

load_dotenv()

# ===========================
# CONFIG
# ===========================

CAR_ID = os.getenv("EV_ID", "EV_UNKNOWN")
CAR_MODEL = os.getenv("CAR_MODEL", "VF8-1")

ev_thread = None
producer_stop_event = threading.Event()
consumer_stop_event = threading.Event()

telemetry_thread = None
status_thread = None

class LabelRequest(BaseModel):
    label: str

# ===========================
# FASTAPI INIT
# ===========================
app = FastAPI(title="EV Battery Telemetry API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================
# EV CONTROL FUNCTIONS
# ===========================
def start_ev():
    global ev_thread, producer_stop_event

    producer_stop_event.clear()

    with ev_state_lock:
        ev_control_state.setdefault(CAR_ID, {})["running"] = True

    if ev_thread is None or not ev_thread.is_alive():
        ev_thread = threading.Thread(
            target=producer_loop,
            args=(CAR_ID, CAR_MODEL, producer_stop_event, lambda: get_ev_label(CAR_ID)),
            daemon=True
        )
        ev_thread.start()

        add_log("INFO", "ev", f"EV {CAR_ID} thread started")

def stop_ev():
    producer_stop_event.set()

    with ev_state_lock:
        ev_control_state.setdefault(CAR_ID, {})["running"] = False

    add_log("INFO", "ev", f"EV {CAR_ID} stopped")

def get_ev_status():
    with ev_state_lock:
        return ev_control_state.get(CAR_ID, {})

# ===========================
# STARTUP
# ===========================
@app.on_event("startup")
def startup():
    global telemetry_thread

    add_log("INFO", "api", "Backend starting...")

    # Start Telemetry Consumer
    telemetry_thread = threading.Thread(
        target=telemetry_consumer_loop,
        args=(consumer_stop_event, CAR_ID),
        daemon=True
    )
    telemetry_thread.start()

    # Start Status Consumer
    # status_thread = threading.Thread(
    #     target=status_consumer_loop,
    #     args=(consumer_stop_event, CAR_ID),
    #     daemon=True
    # )
    # status_thread.start()

    add_log("INFO", "api", "Consumers started")
    start_ev()

# ===========================
# API ENDPOINTS
# ===========================
# record battery
@app.get("/api/latest")
def api_latest():
    return latest_record.get(CAR_ID, {})

@app.get("/api/history")
def api_history():
    return history.get(CAR_ID, [])

@app.get("/api/stream")
async def api_stream(request: Request):
    async def event_generator():
        last_ts = None
        add_log("INFO", "api", f"SSE client connected (EV {CAR_ID})")
        try:
            while True:
                if await request.is_disconnected():
                    add_log("INFO", "api", f"SSE client disconnected (EV {CAR_ID})")
                    break
                record = latest_record.get(CAR_ID)
                if record and record.get("timestamp_s") != last_ts:
                    last_ts = record["timestamp_s"]
                    yield f"data: {json.dumps(record)}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            add_log("DEBUG", "api", f"SSE task cancelled (EV {CAR_ID})")
            raise
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/health")
def api_health():
    return get_ev_status()

@app.post("/api/start")
def api_start():
    start_ev()
    return {"status": "started", "car_id": CAR_ID}

@app.post("/api/stop")
def api_stop():
    stop_ev()
    return {"status": "stopped", "car_id": CAR_ID}

@app.post("/api/set_label")
def api_set_label(req: LabelRequest):
    if req.label not in ["00", "10"]:
        return {"error": "Invalid label"}
    set_ev_label(CAR_ID, req.label)
    new_label = get_ev_label(CAR_ID)
    add_log("INFO", "api", f"EV {CAR_ID} label set to {new_label}")
    return {"status": "ok", "current_label": new_label}

# record status
@app.get("/api/status/latest")
def api_status_latest():
    return latest_status_record.get(CAR_ID, {})

@app.get("/api/status/history")
def api_status_history():
    return status_history.get(CAR_ID, [])

@app.get("/api/status/stream")
async def api_status_stream(request: Request):
    async def event_generator():
        last_ts = None
        add_log("INFO", "api", f"SSE client connected (status, EV {CAR_ID})")
        try:
            while True:
                if await request.is_disconnected():
                    add_log("INFO", "api", f"SSE client disconnected (status, EV {CAR_ID})")
                    break
                record = latest_status_record.get(CAR_ID)
                if record and record.get("timestamp_s") != last_ts:
                    last_ts = record["timestamp_s"]
                    yield f"data: {json.dumps(record)}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            add_log("DEBUG", "api", f"SSE status task cancelled (EV {CAR_ID})")
            raise
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.on_event("shutdown")
def shutdown():
    add_log("INFO", "api", "Shutting down backend...")

    consumer_stop_event.set()
    producer_stop_event.set()

    add_log("INFO", "api", "Stop signals sent")


