"""
Legacy LangChain-powered LLM data generator with Dynamic State Machine.

DEPRECATED: This module is superseded by agent.ev_agent.EVAgent.
Kept for reference only.

Usage:
    from agent.llm_generator import EVDataGenerator  # legacy
"""

import json
import os
import random
import time
from typing import Generator

from langchain_openai import ChatOpenAI

from core.constants import DEFAULT_LLM_MODEL, DEFAULT_LLM_API_URL, FLOAT_FIELDS
from core.models import EVBatteryTelemetry
from prompts.loader import get_langchain_prompt

# ================================================================
# CONFIGURATION
# ================================================================

LLM_API_KEY = os.getenv("LLM_API_KEY", "YOUR_LLM_API_KEY")
MODEL_ID = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL)

SAVE_FOLDER = "data"
os.makedirs(SAVE_FOLDER, exist_ok=True)

REQUIRED_FIELDS = {
    "id", "id_segment", "volt_V", "current_A", "soc_pct",
    "max_single_volt_V", "min_single_volt_V",
    "max_temp_C", "min_temp_C", "timestamp_s",
    "avg_speed_kmh", "hvac_active", "payload_kg",
    "regenerative_braking_Ah", "motor_rpm", "gear_position",
    "accelerator_pedal_pct", "brake_pedal_pct",
    "charger_connected", "label", "car_id", "car_model",
    "mileage_km", "actual_max_capacity_Ah", "nominal_capacity_Ah"
}

MAX_SEGMENT = 15


# ================================================================
# STORAGE
# ================================================================

def _get_temp_file_path(car_id: str) -> str:
    return os.path.join(SAVE_FOLDER, f"{car_id}.json")

def _load_last_records_from_file(car_id: str):
    file_path = _get_temp_file_path(car_id)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("last_records", []),
            data.get("nominal_capacity_Ah", None),
            data.get("cycle_count", 0),
            data.get("scenario", "URBAN_CRUISE"),
            data.get("target_soc", 20.0)
        )
    return [], None, 0, "URBAN_CRUISE", 20.0

def _save_state(car_id: str, last_records: list, nominal_capacity: float, cycle_count: int, scenario: str, target_soc: float):
    file_path = _get_temp_file_path(car_id)
    data = {
        "nominal_capacity_Ah": nominal_capacity,
        "cycle_count": cycle_count,
        "scenario": scenario,
        "target_soc": target_soc,
        "last_records": last_records[-5:]
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ================================================================
# GENERATOR WITH STATE MACHINE (DEPRECATED - use EVAgent instead)
# ================================================================

class EVDataGenerator:
    """Generates EV battery telemetry records using LangChain and a Dynamic State Machine.

    DEPRECATED: Use agent.ev_agent.EVAgent instead.
    """

    def __init__(
        self,
        car_id: str,
        car_model: str = "VF8-1",
        nominal_capacity: float = 100.0,
        get_label_fn=None,
    ):
        self.car_id = car_id
        self.car_model = car_model
        self.get_label_fn = get_label_fn

        self._llm = ChatOpenAI(
            model=MODEL_ID,
            openai_api_key=LLM_API_KEY,
            openai_api_base=os.getenv(
                "LLM_API_URL",
                DEFAULT_LLM_API_URL
            ).rstrip("/chat/completions"),
            temperature=0.85,
            max_retries=2,
            timeout=600,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False
                }
            }
        )

        (
            self.last_records_data,
            saved_capacity,
            self.cycle_count,
            self.scenario,
            self.target_soc_for_switch
        ) = _load_last_records_from_file(car_id)

        self.nominal_capacity = saved_capacity or nominal_capacity
        self._reload_chain()

        if self.last_records_data:
            self._id = self.last_records_data[-1]["id"]
            prefix, num = self.last_records_data[-1]["id_segment"].rsplit("_", 1)
            self._id_segment_index = int(num)
            self._timestamp_s = self.last_records_data[-1]["timestamp_s"]
            self._actual_max_capacity = self.last_records_data[-1]["actual_max_capacity_Ah"]
            self._mileage_km = self.last_records_data[-1]["mileage_km"]
            self._payload_kg = self.last_records_data[-1]["payload_kg"]
        else:
            self._initialize_new_session("URBAN_CRUISE", 95.0)
            self.nominal_capacity = random.randint(90, 120)
            self._actual_max_capacity = round(self.nominal_capacity * random.uniform(0.95, 0.99), 2)
            self._mileage_km = round(random.randint(10000, 999999), 2)
            self._payload_kg = round(random.uniform(0.0, 100.0), 2)

    def _reload_chain(self):
        """Update Prompt Template based on current scenario."""
        prompt_template = get_langchain_prompt(self.scenario)
        self._chain = prompt_template | self._llm

    def _initialize_new_session(self, new_scenario: str, current_soc: float):
        """Reset IDs and set targets for a new session."""
        self.scenario = new_scenario
        self._id_segment_index = 1
        self._timestamp_s = -10

        if "CHARGING" in self.scenario:
            self._id = f"RC{random.randint(100000, 999999)}"
            self.target_soc_for_switch = min(100.0, current_soc + random.uniform(20.0, 60.0))
            print(f"\n[STATE SWITCH] Charging started. Target SOC: {self.target_soc_for_switch:.1f}%")
        else:
            self._id = f"DR{random.randint(100000, 999999)}"
            self.target_soc_for_switch = max(10.0, current_soc - random.uniform(20.0, 40.0))
            print(f"\n[STATE SWITCH] Driving started. Target SOC: {self.target_soc_for_switch:.1f}%")

        self._reload_chain()

    def _evaluate_state_transition(self):
        """Check if vehicle needs to switch between driving and charging."""
        if not self.last_records_data:
            return

        current_soc = self.last_records_data[-1]["soc_pct"]

        if self.scenario == "URBAN_CRUISE":
            if current_soc <= self.target_soc_for_switch:
                self._initialize_new_session("AC_CHARGING", current_soc)

        elif "CHARGING" in self.scenario:
            if current_soc >= self.target_soc_for_switch:
                self.cycle_count += 1
                degradation_factor = random.uniform(0.9995, 1.0)
                self._actual_max_capacity = round(self._actual_max_capacity * degradation_factor, 2)
                self._initialize_new_session("URBAN_CRUISE", current_soc)

    @property
    def label(self) -> str:
        if self.get_label_fn:
            return self.get_label_fn()
        return "00"

    def __iter__(self) -> Generator[EVBatteryTelemetry, None, None]:
        return self

    def __next__(self) -> EVBatteryTelemetry:
        self._evaluate_state_transition()

        if self._timestamp_s >= 1270:
            self._timestamp_s = 0
            self._id_segment_index += 1
            if self._id_segment_index > MAX_SEGMENT:
                print(f"[INFO] Reached max segment {MAX_SEGMENT}. Resetting to segment 1 for endless loop.")
                self._id_segment_index = 1
        else:
            self._timestamp_s += 10

        context_records = self.last_records_data[-5:] if self.last_records_data else []
        context_json = json.dumps(context_records)

        prompt_vars = {
            "car_id": self.car_id,
            "label": self.label,
            "mileage": self._mileage_km,
            "capacity": self.nominal_capacity,
            "last_soc": context_records[-1]["soc_pct"] if context_records else 95.0,
            "context_records": context_json,
        }

        print(f"\n===== LLM REQUEST | {self.scenario} | ID={self._id} | T={self._timestamp_s}s | SOC_TARGET={self.target_soc_for_switch:.1f}% =====")

        try:
            ai_msg = self._chain.invoke(prompt_vars)
            content = ai_msg.content

            content = content.replace("nan", "0").replace("NaN", "0").replace("None", "0")
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            record = json.loads(content)

            record["id"] = self._id
            record["car_id"] = self.car_id
            record["car_model"] = self.car_model
            record["label"] = self.label
            record["timestamp_s"] = self._timestamp_s
            record["id_segment"] = f"{self._id}_{self._id_segment_index}"
            record["nominal_capacity_Ah"] = float(self.nominal_capacity)
            record["actual_max_capacity_Ah"] = float(self._actual_max_capacity)
            record["payload_kg"] = float(self._payload_kg)

            if "CHARGING" in self.scenario or self.scenario in ["SLEEP_MODE", "STANDBY_MODE"]:
                record["avg_speed_kmh"] = 0.0
                record["motor_rpm"] = 0
                record["gear_position"] = "P"
                record["accelerator_pedal_pct"] = 0.0
                record["brake_pedal_pct"] = 0.0
                record["regenerative_braking_Ah"] = 0.0
                record["charger_connected"] = 1
                record["mileage_km"] = float(self._mileage_km)
            else:
                record["charger_connected"] = 0
                record["gear_position"] = "D"

                if "motor_rpm" in record:
                    record["motor_rpm"] = int(float(record["motor_rpm"]))

                if "avg_speed_kmh" in record:
                    distance_traveled = (float(record["avg_speed_kmh"]) / 3600.0) * 10.0
                    self._mileage_km += distance_traveled
                record["mileage_km"] = float(self._mileage_km)

            for k in FLOAT_FIELDS:
                if k in record:
                    record[k] = float(record[k])

            record["payload_kg"] = round(record["payload_kg"], 2)
            record["mileage_km"] = round(record["mileage_km"], 2)
            record["soc_pct"] = round(float(record["soc_pct"]), 2)

            telemetry_obj = EVBatteryTelemetry(**record)

            self.last_records_data.append(record.copy())
            if len(self.last_records_data) > 5:
                self.last_records_data = self.last_records_data[-5:]

            _save_state(
                self.car_id,
                self.last_records_data,
                self.nominal_capacity,
                self.cycle_count,
                self.scenario,
                self.target_soc_for_switch
            )

            return telemetry_obj

        except Exception as e:
            print(f"[LLM ERROR/VALIDATION FAILED] car_id={self.car_id} | {e}")
            time.sleep(1)
            raise e
