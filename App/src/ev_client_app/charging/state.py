import threading
from collections import defaultdict
from datetime import datetime

# ===========================
# GLOBAL STATE - TELEMETRY
# ===========================
latest_record = {}           
history = defaultdict(list)  

# ===========================
# GLOBAL STATE - VEHICLE STATUS
# ===========================
latest_status_record = {}           
status_history = defaultdict(list)  

# ===========================
# EV CONTROL STATE
# ===========================
ev_control_state = {}
ev_state_lock = threading.Lock()  

# ===========================
# LOGGING
# ===========================
def add_log(level: str, source: str, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] [{source}] {message}")

# ===========================
# EV CONTROL FUNCTIONS
# ===========================

def is_ev_running(car_id: str) -> bool:
    with ev_state_lock:
        return ev_control_state.get(car_id, {}).get("running", False)


def set_ev_running(car_id: str, running: bool):
    with ev_state_lock:
        ev_control_state.setdefault(car_id, {})["running"] = running
        add_log("INFO", "state", f"EV {car_id} running set to {running}")


def get_ev_label(car_id: str) -> str:
    with ev_state_lock:
        if "label" not in ev_control_state.get(car_id, {}):
            ev_control_state.setdefault(car_id, {})["label"] = "00"
        return ev_control_state[car_id]["label"]


def set_ev_label(car_id: str, label: str):
    with ev_state_lock:
        ev_control_state.setdefault(car_id, {})["label"] = label
        add_log("INFO", "state", f"EV {car_id} label set to {label}")

# ======================================================
# TELEMETRY STATE FUNCTIONS (Topic: ev.battery.telemetry)
# ======================================================

def append_history(car_id: str, record: dict):
    with ev_state_lock:
        history[car_id].append(record)


def get_latest_record(car_id: str) -> dict:
    with ev_state_lock:
        return dict(latest_record.get(car_id, {}))


def set_latest_record(car_id: str, record: dict):
    with ev_state_lock:
        latest_record[car_id] = record


def get_history(car_id: str):
    with ev_state_lock:
        return history.get(car_id, [])

# ======================================================
# VEHICLE STATUS STATE FUNCTIONS (Topic: ev.vehicle.status)
# ======================================================

def append_status_history(car_id: str, record: dict):
    with ev_state_lock:
        status_history[car_id].append(record)


def get_latest_status_record(car_id: str) -> dict:
    with ev_state_lock:
        return latest_status_record.get(car_id, {})


def set_latest_status_record(car_id: str, record: dict):
    with ev_state_lock:
        latest_status_record[car_id] = record


def get_status_history(car_id: str):
    with ev_state_lock:
        return status_history.get(car_id, [])
