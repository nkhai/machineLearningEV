"""
Driving tool - generates urban cruise telemetry.

Simulates battery behavior during normal urban driving at 40-60 km/h.
Handles speed fluctuations, traffic patterns, energy consumption, and mileage.

Usage:
    from agent.tools.urban_driving import DrivingTool
    tool = DrivingTool(llm)
    record = tool.execute(agent)
"""

import json
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

from core.models import EVBatteryTelemetry
from agent.tools.base import BaseTool

if TYPE_CHECKING:
    from agent.ev_agent import EVAgent


class DrivingTool(BaseTool):
    """
    Driving tool - generates urban cruise telemetry.

    Simulates battery behavior during normal urban driving at 40-60 km/h.
    Handles speed fluctuations, traffic patterns, energy consumption, and mileage.

    Tool call:
        from agent.tools.urban_driving import DrivingTool
        tool = DrivingTool(llm)
        record = tool.execute(agent)
    """

    name = "drive"
    description = "Drive the vehicle in urban environment (40-60 km/h cruising)"
    scenario = "URBAN_CRUISE"

    def execute(self, agent: 'EVAgent') -> list[EVBatteryTelemetry]:
        # Build context (keep initial section)
        context = {
            "car_id": agent.state.car_id,
            "car_model": agent.car_model, 
            "label": agent.state.label,
            "mileage": agent.state.mileage_km,
            "capacity": agent.state.nominal_capacity_Ah,
            "last_soc": agent.state.soc_pct,
            "context_records": json.dumps(agent.state.last_records[-5:]),
        }

        # Call LLM
        ai_msg = self._chain.invoke(context)
        content = self.parse_response(ai_msg.content)
        records = json.loads(content)

        # Safe fallback if LLM stubbornly returns 1 dict instead of array
        if isinstance(records, dict):
            records = [records]

        # Get last record in Python as initial fallback reference
        last_known = agent.state.last_records[-1] if agent.state.last_records else {}
        
        results = []
        for record in records:
            # ========================================================
            # AUTO-FALLBACK: Prevent Missing Fields from LLM
            # ========================================================
            for key, value in last_known.items():
                if key not in record:
                    record[key] = value

            # Apply specific overrides (this function is defined below)
            self._apply_overrides(agent, record)

            # Force cast to int
            for int_field in ["timestamp_s", "hvac_active", "charger_connected"]:
                if int_field in record:
                    try:
                        record[int_field] = int(float(record[int_field]))
                    except (ValueError, TypeError):
                        record[int_field] = 0
            
            results.append(EVBatteryTelemetry(**record))
            
            # Update fallback reference for next record IN THE SAME BATCH
            last_known = record 

        return results

    def _apply_overrides(self, agent: 'EVAgent', record: dict):
        """Apply driving-specific field overrides after LLM response."""
        record["charger_connected"] = 0
        record["gear_position"] = "D"

        if "motor_rpm" in record:
            record["motor_rpm"] = int(float(record["motor_rpm"]))

        # Update mileage based on speed
        speed = float(record.get("avg_speed_kmh", 0))
        distance_step = (speed / 3600.0) * 10.0  # 10s per step
        agent.state.mileage_km += distance_step
        record["mileage_km"] = agent.state.mileage_km

        # Update agent state from LLM output
        agent.state.soc_pct = float(record["soc_pct"])
