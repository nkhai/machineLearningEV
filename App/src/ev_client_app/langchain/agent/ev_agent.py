"""
Autonomous EV Agent that generates continuous telemetry data.

Each agent represents one real vehicle. The agent:
- Maintains its own state (SOC, mileage, battery health, session info)
- Has tools it can call (driving, charging)
- Has a decision engine that determines when to switch between tools
- Generates continuous, realistic telemetry data autonomously
- Persists state between runs for session continuity
- Models battery degradation across charge cycles

Usage:
    from agent.ev_agent import EVAgent
    agent = EVAgent(car_id="EV_101", car_model="VF8-1")
    for record in agent:
        print(record.soc_pct)
"""

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Generator

from agent.tools.base import BaseTool

from langchain_openai import ChatOpenAI

from core.constants import (
    RECORDS_PER_SEGMENT,
    MAX_SEGMENT,
    CHARGE_MIN,
    CHARGE_MAX,
    DRIVE_MIN,
    DRIVE_MAX,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_API_URL,
    LLM_TEMPERATURE,
    LLM_MAX_RETRIES,
    LLM_TIMEOUT,
    FLOAT_FIELDS,
    AgentState,
)
from core.models import EVBatteryTelemetry
from agent.decision import EVAgentDecisionEngine
from agent.tools.urban_driving import DrivingTool

from agent.tools.fast_charging import FastChargingTool

from agent.tools.highway_driving import HighwayTool
from agent.tools.home_charging import HomeChargingTool


# Re-export AgentState for backward compatibility
__all__ = ["EVAgent", "EVAgentState", "AgentState"]


# ================================================================
# EV AGENT STATE
# ================================================================

@dataclass
class EVAgentState:
    """
    Complete agent state - the agent's internal memory and environment.
    """

    # Identity
    car_id: str
    car_model: str = "VF8-1"
    payload_kg: float = 50.0

    # Battery core
    soc_pct: float = 95.0
    nominal_capacity_Ah: float = 100.0
    actual_max_capacity_Ah: float = 98.5
    cycle_count: int = 0
    mileage_km: float = 0.0

    # Session
    session_id: str = ""
    segment_index: int = 1
    timestamp_s: int = -10

    # Decision thresholds
    target_soc_for_driving: float = 85.0
    target_soc_for_charging: float = 30.0
    records_in_current_segment: int = 0

    # Current state
    current_state: AgentState = AgentState.DRIVING

    # Context history
    last_records: list = field(default_factory=list)

    # External control
    label: str = "00"


# ================================================================
# EV AGENT
# ================================================================

class EVAgent:
    """
    Autonomous EV Agent that generates continuous telemetry data.

    Architecture:

    EVAgent
      |-- EVAgentState (memory)
      |-- DecisionEngine (SOC threshold logic)
      |    |-- ToolRegistry
      |         |-- DrivingTool (URBAN_CRUISE)
      |         |-- ChargingTool (AC_CHARGING)
      |-- generate_record() -> tool.execute()

    Usage:
        agent = EVAgent(car_id="EV_101", car_model="VF8-1")
        for record in agent:
            print(record.soc_pct)
    """

    def __init__(
        self,
        car_id: str,
        car_model: str = "VF8-1",
        nominal_capacity: float = 100.0,
        get_label_fn: Callable = None,
    ):
        self.car_id = car_id
        self.car_model = car_model
        self.get_label_fn = get_label_fn

        # Initialize LLM (shared across all tools)
        self._llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
            openai_api_key=os.getenv("LLM_API_KEY", "YOUR_LLM_API_KEY"),
            openai_api_base=os.getenv(
                "LLM_API_URL",
                DEFAULT_LLM_API_URL
            ).rstrip("/chat/completions"),
            temperature=LLM_TEMPERATURE,
            max_retries=LLM_MAX_RETRIES,
            timeout=LLM_TIMEOUT,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": False}
            }
        )

        # Initialize agent state
        self.state = EVAgentState(car_id=car_id, car_model=car_model)
        self._load_state()

        # Build tool registry (4 tools: 2 driving types + 2 charging types)
        self.tools: Dict[str, 'BaseTool'] = {
            "urban_drive": DrivingTool(self._llm),
            "highway_drive": HighwayTool(self._llm),
            "fast_charge": FastChargingTool(self._llm),
            "home_charge": HomeChargingTool(self._llm),
        }

        # Decision engine
        self.decision_engine = EVAgentDecisionEngine(self)

    @property
    def label(self) -> str:
        """Get current label, either from external function or internal state."""
        if self.get_label_fn:
            return self.get_label_fn()
        return self.state.label

    # ================================================================
    # STATE PERSISTENCE
    # ================================================================

    def _load_state(self):
        """Load persisted state from JSON file."""
        file_path = f"data/{self.car_id}.json"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)

            recs = data.get("last_records", [])
            if recs:
                last = recs[-1]
                self.state.soc_pct = last["soc_pct"]
                self.state.mileage_km = last["mileage_km"]
                self.state.nominal_capacity_Ah = data.get("nominal_capacity_Ah", 100.0)
                self.state.actual_max_capacity_Ah = last.get("actual_max_capacity_Ah", 98.5)
                self.state.cycle_count = data.get("cycle_count", 0)
                self.state.session_id = last.get("id", "")
                self.state.segment_index = int(last.get("id_segment", "").rsplit("_", 1)[1]) if last.get("id_segment") else 1
                self.state.timestamp_s = last.get("timestamp_s", -10)
                if self.state.timestamp_s >= 0:
                    self.state.records_in_current_segment = (self.state.timestamp_s // 10) + 1
                    # If at last record (1270s), reset to 0 to unlock tool for new segment
                    if self.state.records_in_current_segment >= RECORDS_PER_SEGMENT:
                        self.state.records_in_current_segment = 0
                else:
                    self.state.records_in_current_segment = 0
                    
                self.state.payload_kg = last.get("payload_kg", 50.0)
                self.state.last_records = recs

                # Infer current state from session ID
                if "RC" in self.state.session_id:
                    self.state.current_state = AgentState.CHARGING
                else:
                    self.state.current_state = AgentState.DRIVING

                # Restore thresholds from file
                self.state.target_soc_for_driving = data.get("target_soc_drive", 85.0)
                self.state.target_soc_for_charging = data.get("target_soc_charge", 20.0)

                if "current_tool_name" in data:
                    self._current_tool_name = data["current_tool_name"]
                else:
                    if self.state.current_state == AgentState.CHARGING:
                        self._current_tool_name = random.choice(["fast_charge", "home_charge"])
                    else:
                        self._current_tool_name = random.choice(["urban_drive", "highway_drive"])

                print(f"[Agent {self.car_id}] Resumed: SOC={self.state.soc_pct:.1f}% | {self.state.current_state.value} | Cycle #{self.state.cycle_count}")
            else:
                self._init_new_session()
        else:
            self._init_new_session()

    def _save_state(self):
        """Persist state to JSON file after each record."""
        if os.getenv("QUICK_GEN_MODE") == "1":
            return
        
        os.makedirs("data", exist_ok=True)
        data = {
            "nominal_capacity_Ah": round(self.state.nominal_capacity_Ah, 2),
            "cycle_count": self.state.cycle_count,
            "scenario": self.state.current_state.value,
            "target_soc_charge": self.state.target_soc_for_charging,
            "target_soc_drive": self.state.target_soc_for_driving,
            
            # --- ADD THIS LINE TO PERSIST TOOL SELECTION ---
            "current_tool_name": self._current_tool_name, 
            
            "last_records": self.state.last_records[-20:],
        }
        with open(f"data/{self.car_id}.json", "w") as f:
            json.dump(data, f, indent=2)

    # ================================================================
    # SESSION MANAGEMENT
    # ================================================================

    def _init_new_session(self):
        """Initialize a new session with randomized parameters."""
        self.state.soc_pct = random.uniform(85.0, 99.0)
        # Set battery capacity based on vehicle size class
        if "SimuProA" in self.car_model:
            self.state.nominal_capacity_Ah = 210.0
        elif "SimuProB" in self.car_model:
            self.state.nominal_capacity_Ah = 185.0
        else:
            self.state.nominal_capacity_Ah = 100.0 # Fallback value if car model name is invalid
            
        # 1. Initialize random ODO first
        self.state.mileage_km = random.randint(10000, 200000)
        
        # 2. Calculate battery degradation based on ODO (Assuming 6% degradation per 100,000 km)
        base_degradation = 0.06 / 100000.0
        
        # Add random noise (±1%) to create realistic differences between vehicles
        noise = random.uniform(-0.01, 0.01) 
        degradation_factor = 1.0 - (self.state.mileage_km * base_degradation) + noise
        
        # Ensure the factor never exceeds 100% (1.0)
        degradation_factor = min(1.0, degradation_factor)
        
        self.state.actual_max_capacity_Ah = round(self.state.nominal_capacity_Ah * degradation_factor, 2)
        self.state.payload_kg = round(random.uniform(0.0, 100.0), 2)
        self.state.cycle_count = 0
        self.state.timestamp_s = -10
        self.state.segment_index = 1
        self.state.records_in_current_segment = 0
        self.state.last_records = []
        self.state.current_state = AgentState.DRIVING
        self.state.target_soc_for_charging = random.uniform(CHARGE_MIN, CHARGE_MAX)
        self.state.target_soc_for_driving = random.uniform(DRIVE_MIN, DRIVE_MAX)
        self._current_tool_name = random.choice(["urban_drive", "highway_drive"])

        self.state.session_id = f"DR{random.randint(100000, 999999)}"
        print(f"[Agent {self.car_id}] New session: SOC={self.state.soc_pct:.1f}% | Drive target: {self.state.target_soc_for_driving:.1f}% | Charge target: {self.state.target_soc_for_charging:.1f}%")

    def _transition_state(self, new_tool_name: str):
        """
        Transition the agent to a new tool (state switch).

        Handles:
        - ID generation (DR vs RC prefix)
        - Segment reset
        - Session timestamp reset
        - Record counter reset
        - Threshold update
        - Degradation modeling (on charge->drive transition)
        """
        self._current_tool_name = new_tool_name
        self.state.records_in_current_segment = 0

        driving_tools = ("urban_drive", "highway_drive")
        charging_tools = ("fast_charge", "home_charge")
        is_charging = new_tool_name in charging_tools
        is_drive = new_tool_name in driving_tools

        if is_charging:
            prev = self.state.current_state.value
            self.state.current_state = AgentState.CHARGING
            self.state.session_id = f"RC{random.randint(100000, 999999)}"
            self.state.segment_index = 1
            self.state.timestamp_s = -10
            self.state.target_soc_for_driving = random.uniform(DRIVE_MIN, DRIVE_MAX)
            print(f"\n[STATE SWITCH] {self.car_id}: {prev} -> CHARGING | Driving target: {self.state.target_soc_for_driving:.1f}% | Charge target: {self.state.target_soc_for_charging:.1f}%")

        elif is_drive:
            prev = self.state.current_state.value
            self.state.current_state = AgentState.DRIVING
            self.state.cycle_count += 1
            
            # --- UPDATE BATTERY DEGRADATION BASED ON MILEAGE ---
            # Calculate theoretical capacity based on current km
            base_degradation = 0.06 / 100000.0
            expected_capacity = self.state.nominal_capacity_Ah * (1.0 - (self.state.mileage_km * base_degradation))
            
            # Battery can only degrade, never recover, so use min()
            self.state.actual_max_capacity_Ah = min(self.state.actual_max_capacity_Ah, round(expected_capacity, 2))
            # ------------------------------------------

            self.state.session_id = f"DR{random.randint(100000, 999999)}"
            self.state.segment_index = 1
            self.state.timestamp_s = -10
            self.state.target_soc_for_charging = random.uniform(CHARGE_MIN, CHARGE_MAX)
            print(f"\n[STATE SWITCH] {self.car_id}: {prev} -> DRIVING | Charge target: {self.state.target_soc_for_charging:.1f}% | Cycle #{self.state.cycle_count} | Capacity: {self.state.actual_max_capacity_Ah:.2f} Ah")
    # ================================================================
    # MAIN GENERATION LOOP
    # ================================================================

    def generate_batch(self) -> list[EVBatteryTelemetry]:
        """Call LLM to generate a batch of data (default 3 records) and process sequentially."""
        next_tool_name = self.decision_engine.decide()

        old_is_charging = self._current_tool_name in ("fast_charge", "home_charge")
        new_is_charging = next_tool_name in ("fast_charge", "home_charge")
        if old_is_charging != new_is_charging:
            self._transition_state(next_tool_name)
        else:
            self._current_tool_name = next_tool_name

        tool = self.tools[self._current_tool_name]
        telemetry_objs = tool.execute(self)  # Now returns a LIST

        final_objs = []
        for telemetry_obj in telemetry_objs:
            record = telemetry_obj.model_dump()

            # Step 5: Override core fields
            record["id"] = self.state.session_id
            record["car_id"] = self.car_id
            record["car_model"] = self.car_model
            record["label"] = self.label
            record["nominal_capacity_Ah"] = float(self.state.nominal_capacity_Ah)
            record["actual_max_capacity_Ah"] = float(self.state.actual_max_capacity_Ah)
            record["payload_kg"] = float(self.state.payload_kg)

            # Step 6 & 7: Time and Segment Management (calculate per record)
            if self.state.timestamp_s >= 1270:
                self.state.timestamp_s = 0
            else:
                self.state.timestamp_s += 10

            self.state.records_in_current_segment += 1
            record["timestamp_s"] = self.state.timestamp_s
            record["id_segment"] = f"{self.state.session_id}_{self.state.segment_index}"

            if self.state.records_in_current_segment >= RECORDS_PER_SEGMENT:
                self.state.records_in_current_segment = 0
                self.state.segment_index += 1
                print(f"\n[SEGMENT COMPLETE] {self.car_id}: Segment {self.state.segment_index - 1} ({RECORDS_PER_SEGMENT} records)")

            # Step 8: Noise & Physical Guardrails
            for k in FLOAT_FIELDS:
                if k in record:
                    record[k] = float(record[k])

            if len(self.state.last_records) > 0:
                last_soc = self.state.last_records[-1]["soc_pct"]
                # Inject SOC noise
                if self.state.current_state == AgentState.CHARGING:
                    noisy_soc = record["soc_pct"] + random.uniform(-0.005, 0.02)
                    record["soc_pct"] = max(last_soc + 0.001, noisy_soc)
                else:
                    noisy_soc = record["soc_pct"] + random.uniform(-0.02, 0.005)
                    record["soc_pct"] = min(last_soc - 0.001, noisy_soc)
                
                record["volt_V"] += random.uniform(-0.5, 0.5)
                if self.state.current_state == AgentState.CHARGING:
                    record["current_A"] += random.uniform(-3.0, 3.0) 

            # Clipping & Formatting
            record["volt_V"] = min(max(record["volt_V"], 300.0), 445.0)
            record["soc_pct"] = min(max(record["soc_pct"], 0.0), 100.0)
            
            if "motor_rpm" in record:
                record["motor_rpm"] = int(float(record["motor_rpm"]))

            record["payload_kg"] = round(record["payload_kg"], 2)
            record["mileage_km"] = round(record["mileage_km"], 2)
            self.state.mileage_km = record["mileage_km"] # Update ODO
            record["soc_pct"] = round(record["soc_pct"], 2)
            record["volt_V"] = round(record["volt_V"], 3)
            record["current_A"] = round(record["current_A"], 1)

            # Step 9: Push to State & Memory
            valid_obj = EVBatteryTelemetry(**record)
            final_objs.append(valid_obj)
            
            self.state.last_records.append(record.copy())
            if len(self.state.last_records) > 20:
                self.state.last_records = self.state.last_records[-20:]

            print(f"  >> {self._current_tool_name:7s} | {record['id_segment']} | T={record['timestamp_s']:4d}s | SOC={record['soc_pct']:6.2f}% | V={record['volt_V']:.3f}V | I={record['current_A']:.1f}A")

        self._save_state()
        return final_objs

    def __iter__(self) -> Generator[list[EVBatteryTelemetry], None, None]:
        return self

    def __next__(self) -> list[EVBatteryTelemetry]:
        try:
            return self.generate_batch()
        except Exception as e:
            print(f"[Agent {self.car_id} ERROR] {e}")
            time.sleep(5)
            raise e