"""
Constants used across the EV agent, producer, consumer, and models.

Defines thresholds, segment sizes, Kafka config, and field definitions.
"""

import os
from enum import Enum
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AgentState(str, Enum):
    """Current operational state of the EV agent."""
    DRIVING = "DRIVING"
    CHARGING = "CHARGING"


# Segment constraints
RECORDS_PER_SEGMENT = 128  # Each segment produces exactly 128 records
MAX_SEGMENT = 15           # Segment index wraps at 15

# Decision thresholds
CHARGE_MIN = 0.0   # Minimum random threshold for switching to charging
CHARGE_MAX = 40.0  # Maximum random threshold for switching to charging
DRIVE_MIN = 70.0   # Minimum random threshold for switching to driving
DRIVE_MAX = 100.0  # Maximum random threshold for switching to driving

# Kafka config (Loaded flexibly from .env file)
_brokers_env = os.getenv("KAFKA_BROKERS", "hc1-c-0003u.hc.apac.bosch.com:9092")
KAFKA_BROKERS = _brokers_env.split(",") if "," in _brokers_env else [_brokers_env]

TELEMETRY_TOPIC = os.getenv("TELEMETRY_TOPIC", "ev.battery.telemetry_v4")
RECORD_INTERVAL_SECONDS = int(os.getenv("RECORD_INTERVAL_SECONDS", 3))

# LLM config defaults (Loaded flexibly from .env file)
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "/models/gemma-4-31B-it-FP8")
DEFAULT_LLM_API_URL = os.getenv("LLM_API_URL", "http://hc1-c-0003u.hc.apac.bosch.com:30000/v1")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.85))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", 2))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", 600))

# Kafka schema fields (25 fields)
KAFKA_SCHEMA_FIELDS = [
    "id", "id_segment", "volt_V", "current_A", "soc_pct",
    "max_single_volt_V", "min_single_volt_V",
    "max_temp_C", "min_temp_C", "timestamp_s",
    "avg_speed_kmh", "hvac_active", "payload_kg",
    "regenerative_braking_Ah", "motor_rpm", "gear_position",
    "accelerator_pedal_pct", "brake_pedal_pct",
    "charger_connected", "label", "car_id", "car_model",
    "mileage_km", "actual_max_capacity_Ah", "nominal_capacity_Ah"
]

# Float fields that need type casting
FLOAT_FIELDS = [
    "volt_V", "current_A", "soc_pct",
    "max_single_volt_V", "min_single_volt_V",
    "max_temp_C", "min_temp_C",
    "avg_speed_kmh", "payload_kg",
    "regenerative_braking_Ah", "motor_rpm",
    "accelerator_pedal_pct", "brake_pedal_pct",
    "actual_max_capacity_Ah", "nominal_capacity_Ah",
    "mileage_km"
]