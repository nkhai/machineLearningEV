from typing import TYPE_CHECKING
import random
from core.constants import AgentState

if TYPE_CHECKING:
    from agent.ev_agent import EVAgent

DRIVE_TOOL_PROBS = {
    "urban_drive": 0.6,
    "highway_drive": 0.4,
}

CHARGE_TOOL_PROBS = {
    "fast_charge": 0.6,
    "home_charge": 0.4,
}

class EVAgentDecisionEngine:
    # Default probability to switch from Charging -> Driving (When battery is full)
    CHARGE_TO_DRIVE_PROBABILITY = 0.6

    def __init__(self, agent: 'EVAgent'):
        self.agent = agent

    def _get_drive_to_charge_probability(self, soc_pct: float) -> float:
        """
        Simulates 'Range Anxiety' (Fear of running out of battery):
        Calculates the probability of deciding to find a charging station based on remaining SOC %.
        """
        if soc_pct > 40.0:
            return 0.0    # SOC > 40%: No charging, continue driving 100%
        elif 30.0 < soc_pct <= 40.0:
            return 0.60   # 30-40%: 60% charging, 40% driving
        elif 20.0 < soc_pct <= 30.0:
            return 0.70   # 20-30%: 70% charging, 30% driving
        elif 10.0 < soc_pct <= 20.0:
            return 0.80   # 10-20%: 80% charging, 20% driving
        else:
            return 0.95   # 0-10%: 95% charging, 5% reckless driving

    def decide(self) -> str:
        state = self.agent.state

        # ========================================================
        # MISSING LOCK GATE: LOCK STATE BY SEGMENT (128 RECORDS)
        # ========================================================
        # If in the middle of a segment (records_in_current_segment > 0),
        # MUST keep the current driving/charging type. No randomization allowed.
        if state.records_in_current_segment > 0:
            return self.agent._current_tool_name


        # ========================================================
        # 1. CHECK SOC THRESHOLDS FOR STATE TRANSITION
        # ========================================================
        state_changed = False

        if state.current_state == AgentState.DRIVING:
            # Range Anxiety: probabilistic switch to charging based on SOC
            charge_prob = self._get_drive_to_charge_probability(state.soc_pct)
            if charge_prob > 0.0 and random.random() < charge_prob:
                state.current_state = AgentState.CHARGING
                state_changed = True
                print(f"\n[SOC SWITCH] {state.car_id}: Driving -> Charging (SOC={state.soc_pct:.1f}%, Range Anxiety Prob={charge_prob*100:.0f}%)")

        elif state.current_state == AgentState.CHARGING:
            # High SOC: probabilistic switch back to driving
            if state.soc_pct >= state.target_soc_for_driving:
                if random.random() < self.CHARGE_TO_DRIVE_PROBABILITY:
                    state.current_state = AgentState.DRIVING
                    state_changed = True
                    print(f"\n[SOC SWITCH] {state.car_id}: Charging -> Driving (SOC={state.soc_pct:.1f}%)")

        # ========================================================
        # 2. SELECT TOOL WITHIN CURRENT STATE
        # ========================================================
        if state.current_state == AgentState.DRIVING:
            return random.choices(
                list(DRIVE_TOOL_PROBS.keys()),
                weights=list(DRIVE_TOOL_PROBS.values()),
                k=1
            )[0]

        elif state.current_state == AgentState.CHARGING:
            if not state_changed and self.agent._current_tool_name in CHARGE_TOOL_PROBS:
                return self.agent._current_tool_name
            return random.choices(
                list(CHARGE_TOOL_PROBS.keys()),
                weights=list(CHARGE_TOOL_PROBS.values()),
                k=1
            )[0]

        return "urban_drive"