"""
Thread-safe in-memory state management for telemetry and vehicle status.

Provides shared state that producers, consumers, and APIs all operate on.
All access is thread-safe via threading.Lock.

Usage:
    from core.state import set_latest_record, get_latest_record, add_log
"""

import threading
from collections import defaultdict
from datetime import datetime
from typing import Optional


# ================================================================
# GLOBAL STATE
# ================================================================

# Telemetry state (ev.battery.telemetry topic)
_latest_record: dict = {}
_history: defaultdict = defaultdict(list)

# Status state (ev.vehicle.status topic)
_latest_status_record: dict = {}
_status_history: defaultdict = defaultdict(list)

# Control state (running/label per vehicle)
_ev_control_state: dict = {}

# Thread safety
_lock = threading.Lock()


# ================================================================
# LOGGING
# ================================================================

def add_log(level: str, source: str, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] [{source}] {message}")


# ================================================================
# TELEMETRY STATE OPERATIONS
# ================================================================

def set_latest_record(car_id: str, record: dict):
    """Replace the latest record for a vehicle."""
    with _lock:
        _latest_record[car_id] = record


def get_latest_record(car_id: str) -> Optional[dict]:
    """Get a copy of the latest record for a vehicle (thread-safe)."""
    with _lock:
        return dict(_latest_record.get(car_id, {}))


def append_history(car_id: str, record: dict):
    with _lock:
        _history[car_id].append(record)


def get_history(car_id: str) -> list:
    """Get a copy of the full history for a vehicle."""
    with _lock:
        return list(_history.get(car_id, []))


# ================================================================
# STATUS STATE OPERATIONS
# ================================================================

def set_latest_status_record(car_id: str, record: dict):
    with _lock:
        _latest_status_record[car_id] = record


def get_latest_status_record(car_id: str) -> Optional[dict]:
    with _lock:
        return dict(_latest_status_record.get(car_id, {}))


def append_status_history(car_id: str, record: dict):
    with _lock:
        _status_history[car_id].append(record)


def get_status_history(car_id: str) -> list:
    with _lock:
        return list(_status_history.get(car_id, []))


# ================================================================
# EV CONTROL STATE OPERATIONS
# ================================================================

def is_ev_running(car_id: str) -> bool:
    with _lock:
        return _ev_control_state.get(car_id, {}).get("running", False)


def set_ev_running(car_id: str, running: bool):
    with _lock:
        _ev_control_state.setdefault(car_id, {})["running"] = running
        add_log("INFO", "state", f"EV {car_id} running set to {running}")


def get_ev_label(car_id: str) -> str:
    with _lock:
        if "label" not in _ev_control_state.get(car_id, {}):
            _ev_control_state.setdefault(car_id, {})["label"] = "00"
        return _ev_control_state[car_id]["label"]


def set_ev_label(car_id: str, label: str):
    with _lock:
        _ev_control_state.setdefault(car_id, {})["label"] = label
        add_log("INFO", "state", f"EV {car_id} label set to {label}")
