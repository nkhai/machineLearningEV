"""
Pydantic models for EV battery telemetry.

Defines the 25-field telemetry record and degradation state used across
all pipelines (charging, driving, langchain_refactored).

Usage:
    from core.models import EVBatteryTelemetry, EVDegradationState
"""

from typing import Literal, Any
from pydantic import BaseModel, field_validator, model_validator

# ================================================================
# TELEMETRY RECORD (25 fields)
# ================================================================

class EVBatteryTelemetry(BaseModel):
    """25-field EV battery telemetry record matching the production schema."""

    # Core Identifiers
    id: str
    id_segment: str

    # Core measurements
    volt_V: float
    current_A: float
    soc_pct: float
    max_single_volt_V: float
    min_single_volt_V: float
    max_temp_C: float
    min_temp_C: float

    # Temporal
    timestamp_s: int

    # Vehicle dynamics (static during charging)
    avg_speed_kmh: float = 0.0
    hvac_active: int = 0
    payload_kg: float = 0.0
    regenerative_braking_Ah: float = 0.0
    motor_rpm: float = 0.0
    gear_position: Literal["P", "D"] = "P"
    accelerator_pedal_pct: float = 0.0
    brake_pedal_pct: float = 0.0
    charger_connected: int = 1

    # Identification
    label: str = "00"
    car_id: str = ""
    car_model: str = "Multi-Model" # Changed default name to match multi-vehicle simulation

    # Session state
    mileage_km: float = 0.0
    actual_max_capacity_Ah: float = 100.0 # Default initial value (AI/DB will overwrite later)
    nominal_capacity_Ah: float = 100.0

    # ---- AUTO-CLAMPING VALIDATORS ----
    # Auto-clamp values within safe practical limits
    @field_validator("id", "id_segment", mode="before")
    @classmethod
    def ensure_string_ids(cls, v: Any) -> str:
        # Prevents system crash if AI returns a number instead of a string like "DR_..."
        return str(v)

    @field_validator("volt_V")
    @classmethod
    def clamp_pack_voltage(cls, v):
        # Expanded voltage range:
        # Small size can go down to 90V-100V. Large size max around 480V.
        return max(80.0, min(v, 500.0))

    @field_validator("max_single_volt_V", "min_single_volt_V")
    @classmethod
    def clamp_cell_voltage(cls, v):
        # A single cell voltage (Li-ion / LFP) shares the same chemical characteristics
        return max(2.0, min(v, 4.45))

    @field_validator("soc_pct")
    @classmethod
    def clamp_soc(cls, v):
        # SOC is always within 0 - 100%
        return max(0.0, min(v, 100.0))

    @field_validator("max_temp_C", "min_temp_C")
    @classmethod
    def clamp_temp(cls, v):
        # Battery temperature: Cold winter can go down to -30°C, ultra-fast charging can heat up to 65°C
        return max(-30.0, min(v, 65.0))

    @field_validator("nominal_capacity_Ah", "actual_max_capacity_Ah")
    @classmethod
    def clamp_capacity(cls, v):
        # Expanded capacity range:
        # Small (~18kWh) around 40Ah-60Ah. Large (~123kWh) around 300Ah-320Ah.
        return max(30.0, min(v, 350.0))

    @model_validator(mode="after")
    def ensure_logical_constraints(self):
        # Ensure Max is always >= Min safely
        if getattr(self, "max_single_volt_V", 0) < getattr(self, "min_single_volt_V", 0):
            self.max_single_volt_V = self.min_single_volt_V
            
        if getattr(self, "max_temp_C", 0) < getattr(self, "min_temp_C", 0):
            self.max_temp_C = self.min_temp_C
            
        return self


# ================================================================
# DEGRADATION STATE
# ================================================================

class EVDegradationState(BaseModel):
    """Persistent vehicle state for cross-session continuity."""

    last_records: list = []
    nominal_capacity_Ah: float = 100.0 
    cycle_count: int = 0

    @property
    def last_soc(self) -> float:
        if not self.last_records:
            return 80.0 # Assume vehicle starts with 80% battery
        return self.last_records[-1].soc_pct

    @property
    def last_mileage(self) -> float:
        if not self.last_records:
            return round(15000.0, 2)
        return self.last_records[-1].mileage_km

    @property
    def last_charge_segment(self) -> int:
        if not self.last_records:
            return 1
        seg = self.last_records[-1].id_segment
        try:
            return int(seg.rsplit("_", 1)[1])
        except (IndexError, ValueError, AttributeError):
            return 1