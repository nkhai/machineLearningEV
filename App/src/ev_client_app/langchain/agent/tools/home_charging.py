"""
Home slow charging tool - generates residential AC charging telemetry.

Simulates battery behavior during overnight slow charging at Vietnamese residential locations.
Handles:
- 220V single-phase grid (2-7 kW, much slower than public stations)
- Realistic CC-CV charging curve (not linear)
- Grid instability (voltage fluctuations cause current dips)
- Possible interruptions (power outage, unplugging for emergency)
- Garage ambient temperature affects thermal dynamics

Usage:
    from agent.tools.home_charging import HomeChargingTool
    tool = HomeChargingTool(llm)
    record = tool.execute(agent)
"""

import json
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI

from core.models import EVBatteryTelemetry
from agent.tools.base import BaseTool

if TYPE_CHECKING:
    from agent.ev_agent import EVAgent


class HomeChargingTool(BaseTool):
    """
    Home slow charging tool - generates residential AC charging telemetry.

    Simulates battery behavior during overnight charging at home:
    - 220V grid, low power (2-7 kW)
    - CC-CV charging curve with realistic tapering
    - Vietnamese grid instability (current fluctuations, interruptions)
    - Garage temperature effects on thermal management

    Tool call:
        tool = HomeChargingTool(llm)
        record = tool.execute(agent)
    """

    name = "home_charge"
    description = "Charge the vehicle at home via 220V residential outlet (2-7 kW slow charging)"
    scenario = "HOME_CHARGING"

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
        """Apply home charging-specific field overrides after LLM response."""
        record["avg_speed_kmh"] = 0.0
        record["motor_rpm"] = 0
        record["gear_position"] = "P"
        record["accelerator_pedal_pct"] = 0.0
        record["brake_pedal_pct"] = 0.0
        record["regenerative_braking_Ah"] = 0.0
        record["charger_connected"] = record.get("charger_connected", 1)
        record["mileage_km"] = agent.state.mileage_km  # Constant during charging

        # Update agent state from LLM output
        agent.state.soc_pct = float(record["soc_pct"])
