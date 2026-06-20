import json
import os
import time
import requests
import re
import random

from prompt import EV_BATTERY_URBAN_CRUISE_PROMPT

LLM_API_URL = "http://hc1-c-0003u.hc.apac.bosch.com:30000/v1/chat/completions"
LLM_API_KEY = os.getenv("LLM_API_KEY", "YOUR_LLM_API_KEY")
MODEL_ID = "/models/gemma-4-31B-it-FP8"

session = requests.Session()

# =========================
# API & HELPER
# =========================
def build_payload(prompt_text: str):
    return {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}],
        "chat_template_kwargs": {"enable_thinking": False}
    }

def call_llm_api(payload: dict) -> str:
    headers = {"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"}
    response = session.post(LLM_API_URL, headers=headers, json=payload, timeout=600)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def parse_llm_output(content: str) -> dict:
    content = content.replace("nan", "0").replace("NaN", "0").replace("None", "0")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}")

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
    data = {
        "nominal_capacity_Ah": nominal_capacity,
        "cycle_count": cycle_count,
        "last_records": last_records[-5:] # Only keep last 5 records as context
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

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

    MAX_SEGMENT = 18
    TIME_STEP = 10

    # Load historical data from context
    (last_records, saved_nominal, cycle_count) = load_last_records_from_file(car_id)

    # --- RESUME LOGIC (CONTINUATION INITIALIZATION) ---
    if last_records:
        last_rec = last_records[-1]
        last_id = last_rec.get("id", "")
        
        # 1. Case: switching from Charging to Driving
        if "RC" in last_id:
            current_id = last_id.replace("RC", "DR")
            id_segment_index = 1
            timestamp_s = 0
            print(f"[*] Transition RC->DR: Starting new sequence at 0s, Segment 1")

            payload_kg = random.randint(50, 400)
        
        # 2. Case: continuing Driving journey
        else:
            current_id = last_id
            last_ts = last_rec.get("timestamp_s", 0)
            try:
                # Extract last segment index from string "DRxxx_15"
                last_seg_idx = int(last_rec["id_segment"].rsplit("_", 1)[1])
            except:
                last_seg_idx = 1

            if last_ts >= 1270:
                timestamp_s = 0
                id_segment_index = last_seg_idx + 1
                print(f"[*] Resume: Last record was 1270s. Resetting to 0s, Segment {id_segment_index}")
            else:
                timestamp_s = last_ts + TIME_STEP
                id_segment_index = last_seg_idx
                print(f"[*] Resume: Continuing at {timestamp_s}s, Segment {id_segment_index}")

        # Inherit Mileage and other parameters
        mileage_km = last_rec.get("mileage_km", 0.0)
        actual_max_capacity = last_rec.get("actual_max_capacity_Ah", nominal_capacity)
        nominal_capacity = saved_nominal or last_rec.get("nominal_capacity_Ah", nominal_capacity)
        if "RC" not in last_id:
            payload_kg = last_rec.get("payload_kg", 500.0)
    else:
        # 3. Case: first run with no history
        current_id = car_id.replace("RC", "DR") if "RC" in car_id else f"DR{car_id}"
        id_segment_index = 1
        timestamp_s = 0
        mileage_km = 0.0
        actual_max_capacity = nominal_capacity
        payload_kg = 500.0

    while True:
        # Check stop condition
        if id_segment_index > MAX_SEGMENT:
            print(f"[STOP] {current_id} reached max segment {MAX_SEGMENT}")
            return

        label = get_label_fn() if get_label_fn else "URBAN_CRUISE"
        context_json = json.dumps(last_records[-5:])
        prompt_text = EV_BATTERY_URBAN_CRUISE_PROMPT.format(context_records=context_json)

        try:
            content = call_llm_api(build_payload(prompt_text))
            record = parse_llm_output(content)

            # Assign identification values
            record["id"] = current_id
            record["id_segment"] = f"{current_id}_{id_segment_index}"
            record["timestamp_s"] = timestamp_s
            record["car_id"] = car_id
            record["car_model"] = car_model
            record["label"] = label

            # Update mileage
            current_speed = float(record.get("avg_speed_kmh", 0))
            distance_step = (current_speed / 3600.0) * TIME_STEP
            mileage_km += distance_step
            record["mileage_km"] = int(mileage_km)

            # Other fixed parameters
            record["nominal_capacity_Ah"] = float(nominal_capacity)
            record["actual_max_capacity_Ah"] = float(actual_max_capacity)
            record["payload_kg"] = float(payload_kg)

            # Hard Code Parameters
            record["charger_connected"] = 0
            record["regenerative_braking_Ah"] = 0
            record["gear_position"] = "D"
            record["brake_pedal_pct"] = 0

            # Clean data and type casting
            for field in REQUIRED_FIELDS:
                if field not in record: record[field] = 0
            keys_to_del = [k for k in record if k not in REQUIRED_FIELDS]
            for k in keys_to_del: del record[k]

            float_fields = [
                "volt_V","current_A","soc_pct","max_single_volt_V","min_single_volt_V",
                "max_temp_C","min_temp_C","avg_speed_kmh","payload_kg",
                "regenerative_braking_Ah","motor_rpm","accelerator_pedal_pct",
                "brake_pedal_pct","actual_max_capacity_Ah","nominal_capacity_Ah"
            ]
            for k in float_fields: record[k] = float(record[k])

            yield record

            # --- AFTER SUCCESSFUL YIELD: PREPARE FOR NEXT STEP ---
            last_records.append(record.copy())
            if len(last_records) > 5: last_records = last_records[-5:]
            save_state(car_id, last_records, nominal_capacity, cycle_count)

            # Increment time and segment logic for next iteration
            if timestamp_s >= 1270:
                timestamp_s = 0
                id_segment_index += 1
            else:
                timestamp_s += TIME_STEP

        except Exception as e:
            print(f"[LLM ERROR] car_id={car_id} | {e}")
            # Do not change timestamp_s so next iteration retries the same error timepoint
            time.sleep(1)