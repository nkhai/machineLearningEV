"""
Standalone EV Agent Demo.

Demonstrates how each EV is an autonomous agent that:
1. Maintains its own state (SOC, mileage, battery health)
2. Has tools (driving, charging) it can call
3. Makes autonomous decisions based on SOC thresholds
4. Continuously generates realistic telemetry data

Usage:
    python demo.py
    python demo.py --car_id EV_201 --count 10
"""

import argparse
import time

from agent.ev_agent import EVAgent, AgentState


def main():
    parser = argparse.ArgumentParser(description="EV Agent Telemetry Demo")
    parser.add_argument("--car_id", default="EV_201", help="Car ID")
    parser.add_argument("--car_model", default="VF8-1", help="Car model")
    parser.add_argument("--count", type=int, default=30, help="Number of records to generate")
    parser.add_argument("--label", default="00", choices=["00", "10"], help="Label mode (00=normal, 10=fault)")
    args = parser.parse_args()

    print(f"""
{'='*70}
  EV AGENT TELEMETRY DEMO
{'='*70}
  Car ID:       {args.car_id}
  Car Model:    {args.car_model}
  Records:      {args.count}
  Label Mode:   {args.label}
{'='*70}
  Each agent is autonomous:
    - Maintains its own memory (SOC, mileage, battery health)
    - Has tools: [driving], [charging]
    - Decides: low SOC -> charge, high SOC -> drive
    - Models: battery degradation across cycles
{'='*70}
""")

    def get_label():
        return args.label

    agent = EVAgent(
        car_id=args.car_id,
        car_model=args.car_model,
        get_label_fn=get_label,
    )

    print(f"\n[Agent Created] Initial state:")
    print(f"  SOC:        {agent.state.soc_pct:.2f}%")
    print(f"  State:      {agent.state.current_state.value}")
    print(f"  Session:    {agent.state.session_id}")
    print(f"  Mileage:    {agent.state.mileage_km:.0f} km")
    print(f"  Capacity:   {agent.state.nominal_capacity_Ah:.2f} Ah (actual: {agent.state.actual_max_capacity_Ah:.2f} Ah)")
    print(f"  Target charge:    {agent.state.target_soc_for_charging:.1f}%")
    print(f"  Target drive:     {agent.state.target_soc_for_driving:.1f}%")
    print(f"\nStarting telemetry generation...\n")

    for i in range(args.count):
        try:
            record = agent.generate_record()

            state_icon = "[DRIVING]" if agent.state.current_state == AgentState.DRIVING else "[CHARGING]"

            print(f"\n  [{i+1:3d}] {state_icon:10s} | "
                  f"SOC: {record.soc_pct:6.2f}% | "
                  f"V: {record.volt_V:.3f}V | "
                  f"I: {record.current_A:+6.1f}A | "
                  f"T: {record.timestamp_s:4d}s")

        except Exception as e:
            print(f"\n  [{i+1:3d}] ERROR: {e}")
            time.sleep(1)
            continue

    print(f"\n{'='*70}")
    print(f"[Demo Complete] Generated {args.count} records")
    print(f"Final state:")
    print(f"  SOC:        {agent.state.soc_pct:.2f}%")
    print(f"  State:      {agent.state.current_state.value}")
    print(f"  Session:    {agent.state.session_id}")
    print(f"  Mileage:    {agent.state.mileage_km:.0f} km")
    print(f"  Cycles:     {agent.state.cycle_count}")
    print(f"  Actual Cap: {agent.state.actual_max_capacity_Ah:.2f} Ah")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
