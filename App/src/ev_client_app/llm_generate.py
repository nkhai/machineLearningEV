import pandas as pd
import requests
import json
import os
import random
import time
from prompt import EV_BATTERY_CHARGING_PROMPT
from state import ev_state_lock, history

LLM_API_URL = "http://hc1-c-0003u.hc.apac.bosch.com:30000/v1/chat/completions"
LLM_API_KEY = os.getenv("LLM_API_KEY", "YOUR_LLM_API_KEY")
MODEL_ID = "/models/Mistral-Small-3.2-24B-Instruct-2506-FP8"

MODES = ["CHARGING", "IDLE", "DRIVING"]
ENVIRONMENTS = ["ARCTIC", "TEMPERATE", "HOT_DESERT", "COLD_RAINY", "URBAN_SUMMER"]

session = requests.Session()

def build_payload(prompt_text: str):
    return {
        "model": MODEL_ID,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt_text}]}
        ],
    }

def call_llm_api(payload: dict) -> str:
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    response = session.post(LLM_API_URL, headers=headers, json=payload, timeout=600)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def parse_llm_output(content: str) -> dict:
    content = content.replace("nan", "0").replace("NaN", "0").replace("None", "0")
    try:
        record = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}")
    if not isinstance(record, dict):
        raise ValueError("LLM output must be a dict")
    return record

# --- File paths ---
SAVE_FOLDER = "save_data_to_file"
os.makedirs(SAVE_FOLDER, exist_ok=True)

def get_temp_file_path(car_id: str) -> str:
    return os.path.join(SAVE_FOLDER, f"{car_id}.json")

def load_last_records_from_file(car_id: str):
    file_path = get_temp_file_path(car_id)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_records", []), data.get("capacity", None), data.get("cycle_count", 0)
    return [], None, 0

def save_state(car_id: str, last_records: list, capacity: float, cycle_count: int):
    os.makedirs("save_data_to_file", exist_ok=True)
    file_path = os.path.join("save_data_to_file", f"{car_id}.json")

    records_to_save = last_records[-5:]  

    data = {
        "capacity": capacity,
        "cycle_count": cycle_count,
        "last_records": records_to_save
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def degrade_capacity(current_capacity: float) -> float:
    new_capacity = round(current_capacity - 0.01, 2)
    return max(new_capacity, 28.28)

# --- Generator ---
def generate_ev_data(car_id: str, label: str, capacity: float, mileage: float, get_label_fn=None):
    REQUIRED_FIELDS = {
        "volt","current","soc","max_single_volt","min_single_volt",
        "max_temp","min_temp","timestamp","label","car",
        "charge_segment","mileage","capacity"
    }

    last_records, saved_capacity, cycle_count = load_last_records_from_file(car_id)
    if saved_capacity is not None:
        capacity = saved_capacity

    last_soc = last_records[-1]["soc"] if last_records else round(random.uniform(0, 99), 2)
    relative_time = last_records[-1]["timestamp"] + 10 if last_records else 0
    charge_segment = last_records[-1]["charge_segment"] if last_records else random.randint(100, 999)
    mileage = last_records[-1]["mileage"] if last_records else round(random.uniform(10000, 50000), 2)

    while True:
        mode = random.choice(MODES)
        environment = random.choice(ENVIRONMENTS)
        if get_label_fn:
            label = get_label_fn()

        context_records = last_records[-5:] if last_records else []
        context_json = json.dumps(context_records)

        prompt_text = EV_BATTERY_CHARGING_PROMPT.format(
            car_id=car_id,
            label=label,
            mode=mode,
            environment=environment,
            mileage=mileage,
            capacity=capacity,
            last_soc=last_soc,
            context_records=context_json
        )
        payload = build_payload(prompt_text)

        try:
            content = call_llm_api(payload)
            record = parse_llm_output(content)

            record["timestamp"] = int(relative_time)
            record["charge_segment"] = int(charge_segment)
            record["label"] = label
            record["car"] = car_id

            missing = REQUIRED_FIELDS - record.keys()
            extra = record.keys() - REQUIRED_FIELDS
            if missing:
                raise ValueError(f"Missing fields: {missing}")
            if extra:
                for k in extra:
                    del record[k]

            for key in ["volt","current","soc","max_single_volt","min_single_volt",
                        "max_temp","min_temp","mileage","capacity"]:
                record[key] = float(record[key])

            record["mileage"] = round(record["mileage"], 2)
            record["capacity"] = round(min(max(record.get("capacity", capacity), 28.28), 46.23), 2)

            yield record

            last_records.append(record.copy())
            if len(last_records) > 5:
                last_records = last_records[-5:]
            save_state(car_id, last_records, capacity, cycle_count)

            if record["soc"] >= 100:
                time.sleep(90)
                last_soc = round(random.uniform(10, 90), 2)
                cycle_count += 1
                if cycle_count % 5 == 0:
                    capacity = degrade_capacity(capacity)
            else:
                last_soc = record["soc"]

            relative_time += 10
            if relative_time > 1270:
                relative_time = 0
                charge_segment += 1
                if charge_segment > 999:
                    charge_segment = 100

        except Exception as e:
            print(f"[LLM ERROR] car_id={car_id} | {e}")
