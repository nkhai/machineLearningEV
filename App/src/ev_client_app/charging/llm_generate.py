import json
import os
import random
import time
import requests

from prompt import EV_BATTERY_AC_CHARGING_PROMPT
from state import ev_state_lock, history

LLM_API_URL = "http://hc1-c-0003u.hc.apac.bosch.com:30000/v1/chat/completions"
LLM_API_KEY = os.getenv("LLM_API_KEY", "YOUR_LLM_API_KEY")
MODEL_ID = "/models/gemma-4-31B-it-FP8"

ENVIRONMENTS = ["ARCTIC", "TEMPERATE", "HOT_DESERT", "COLD_RAINY", "URBAN_SUMMER"]

session = requests.Session()

# =========================
# API
# =========================
def build_payload(prompt_text: str):
    return {
        "model": MODEL_ID,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": prompt_text}]}
        ],
        "chat_template_kwargs": {
            "enable_thinking": False
        }
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

# =========================
# STORAGE
# =========================
SAVE_FOLDER = "save_data_to_file"
os.makedirs(SAVE_FOLDER, exist_ok=True)

def get_temp_file_path(car_id: str) -> str:
    return os.path.join(SAVE_FOLDER, f"{car_id}.json")

def load_last_records_from_file(car_id: str):
    file_path = get_temp_file_path(car_id)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("last_records", []),
            data.get("nominal_capacity_Ah", None),
            data.get("cycle_count", 0)
        )
    return [], None, 0

def save_state(car_id: str, last_records: list, nominal_capacity: float, cycle_count: int):
    file_path = get_temp_file_path(car_id)

    records_to_save = last_records[-5:]

    data = {
        "nominal_capacity_Ah": nominal_capacity,
        "cycle_count": cycle_count,
        "last_records": records_to_save
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# =========================
# CAPACITY DEGRADATION
# =========================
def degrade_capacity(current_capacity: float) -> float:
    new_capacity = round(current_capacity - 0.02, 2)
    return max(new_capacity, 28.0)

# =========================
# GENERATOR
# =========================
def generate_ev_data(car_id: str, car_model: str, nominal_capacity: float, get_label_fn=None):

    REQUIRED_FIELDS = {
        "id","id_segment","volt_V","current_A","soc_pct",
        "max_single_volt_V","min_single_volt_V",
        "max_temp_C","min_temp_C","timestamp_s",
        "avg_speed_kmh","hvac_active","payload_kg",
        "regenerative_braking_Ah","motor_rpm","gear_position",
        "accelerator_pedal_pct","brake_pedal_pct",
        "charger_connected","label","car_id","car_model",
        "mileage_km","actual_max_capacity_Ah","nominal_capacity_Ah"
    }

    MAX_SEGMENT = 15

    (
        last_records,
        saved_capacity,
        cycle_count,
    ) = load_last_records_from_file(car_id)

    if last_records:
        id = last_records[-1]["id"]
        prefix, num = last_records[-1]["id_segment"].rsplit("_", 1)
        id_segment_index = int(num)
        timestamp_s = last_records[-1]["timestamp_s"]

        nominal_capacity = saved_capacity or last_records[-1]["nominal_capacity_Ah"]
        actual_max_capacity = last_records[-1]["actual_max_capacity_Ah"]
        mileage_km = last_records[-1]["mileage_km"]
        payload_kg = last_records[-1]["payload_kg"]
    else:
        # --- CHANGES FOR FIRST RUN SCENARIO ---
        # 1. Start with RC prefix and random number (e.g., RC847291)
        random_suffix = random.randint(100000, 999999)
        id = f"RC{random_suffix}"
        
        # 2. Segment starts at 1. Timestamp is -10 to accumulate to 0 in loop
        id_segment_index = 1
        timestamp_s = -10 
        
        # 3. Nominal capacity randomly chosen between 90 and 120
        nominal_capacity = random.randint(90, 120)
        
        # 4. Actual capacity slightly less than nominal (randomly multiplied by 95% -> 99%)
        actual_max_capacity = round(nominal_capacity * random.uniform(0.95, 0.99), 2)
        
        mileage_km = round(random.randint(10000, 999999), 2)
        
        # 5. Payload for charging vehicle (luggage) randomly between 0 to 100 kg
        payload_kg = round(random.uniform(0.0, 100.0), 2)

    while True:
        # --- LOGIC TĂNG TIẾN ---
        if timestamp_s >= 1270:
            timestamp_s = 0
            id_segment_index += 1
            if id_segment_index > MAX_SEGMENT:
                print(f"[STOP] Reached max segment {MAX_SEGMENT}")
                return
        else:
            timestamp_s += 10

        if get_label_fn:
            label = get_label_fn()
        else:
            label = "AC_CHARGING"

        context_records = last_records[-5:] if last_records else []
        context_json = json.dumps(context_records)

        prompt_text = EV_BATTERY_AC_CHARGING_PROMPT.format(
            context_records=context_json
        )

        payload = build_payload(prompt_text)

        print(f"\n===== LLM REQUEST | ID={id} | T={timestamp_s}s | SEG={id_segment_index} =====")

        try:
            content = call_llm_api(payload)
            record = parse_llm_output(content)

            # ===== CORE FIELDS =====
            record["id"] = id
            record["car_id"] = car_id
            record["car_model"] = car_model
            record["label"] = label

            # Assign timestamp and id_segment values calculated above
            record["timestamp_s"] = timestamp_s
            record["id_segment"] = f"{id}_{id_segment_index}"

            record["nominal_capacity_Ah"] = float(nominal_capacity)
            record["actual_max_capacity_Ah"] = float(actual_max_capacity)
            record["mileage_km"] = float(mileage_km)
            record["payload_kg"] = float(payload_kg)

            # ===== STATIC =====
            record["avg_speed_kmh"] = 0
            record["hvac_active"] = 0
            record["regenerative_braking_Ah"] = 0
            record["motor_rpm"] = 0
            record["gear_position"] = "P"
            record["accelerator_pedal_pct"] = 0
            record["brake_pedal_pct"] = 0
            record["charger_connected"] = 1

            # ===== VALIDATION =====
            missing = REQUIRED_FIELDS - record.keys()
            extra = record.keys() - REQUIRED_FIELDS

            if missing:
                raise ValueError(f"Missing fields: {missing}")

            for k in extra:
                del record[k]

            # ===== TYPE CAST =====
            float_fields = [
                "volt_V","current_A","soc_pct",
                "max_single_volt_V","min_single_volt_V",
                "max_temp_C","min_temp_C",
                "avg_speed_kmh","payload_kg",
                "regenerative_braking_Ah","motor_rpm",
                "accelerator_pedal_pct","brake_pedal_pct",
                "actual_max_capacity_Ah","nominal_capacity_Ah",
                "mileage_km"
            ]

            for k in float_fields:
                record[k] = float(record[k])

            record["payload_kg"] = round(record["payload_kg"], 2)
            record["mileage_km"] = round(record["mileage_km"], 2)
            record["soc_pct"] = round(float(record["soc_pct"]), 2)

            yield record

            # ===== UPDATE STATE =====
            last_records.append(record.copy())
            if len(last_records) > 5:
                last_records = last_records[-5:]

            save_state(car_id, last_records, nominal_capacity, cycle_count)

        except Exception as e:
            print(f"[LLM ERROR] car_id={car_id} | {e}")
            time.sleep(1)