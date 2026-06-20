"""
Charging tool - generates AC charging telemetry.

Simulates battery behavior during AC charging, including:
- Grid instability effects on current
- Thermal dynamics during charge
- SOC progression (negative current convention)
- Voltage optimization

Usage:
    from agent.tools.fast_charging import ChargingTool
    tool = ChargingTool(llm)
    record = tool.execute(agent)
"""

import json

from langchain_openai import ChatOpenAI

from core.models import EVBatteryTelemetry
from agent.tools.base import BaseTool
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.ev_agent import EVAgent

class FastChargingTool(BaseTool):
    """
    Charging tool - generates AC charging telemetry.

    Simulates battery behavior during AC charging, including:
    - Grid instability effects on current
    - Thermal dynamics during charge
    - SOC progression (negative current convention)
    - Voltage optimization

    Tool call:
        from agent.tools.fast_charging import ChargingTool
        tool = ChargingTool(llm)
        record = tool.execute(agent)
    """

    name = "fast_charge"
    description = "Charge the vehicle battery via DC Fast Charging station"
    scenario = "FAST_CHARGING"

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
        """Apply charging-specific field overrides after LLM response."""
        record["avg_speed_kmh"] = 0.0
        record["motor_rpm"] = 0
        record["gear_position"] = "P"
        record["accelerator_pedal_pct"] = 0.0
        record["brake_pedal_pct"] = 0.0
        record["regenerative_braking_Ah"] = 0.0
        record["charger_connected"] = 1
        record["mileage_km"] = agent.state.mileage_km  # Constant during charging

        # Update agent state from LLM output
        agent.state.soc_pct = float(record["soc_pct"])
