"""
Quick data generation script for driving and charging phases.

Generates focused datasets for model training by forcing a single phase.
Completely ignores and bypasses local state persistence.
Data is saved as CSV in-memory and streamed DIRECTLY to HDFS.

Usage:
    # Single car, charging only (20% -> 85%)
    python quick_data_gen.py --mode charging --car-id EV_104 --car-model SimuProA-4 \
        --charge-start 20 --charge-end 85
"""

import argparse
import csv
import io
import os
import random
import time
from datetime import datetime
from hdfs import InsecureClient

# Suppress internal I/O warnings
os.environ["QUICK_GEN_MODE"] = "1"

from agent.ev_agent import EVAgent
from core.constants import AgentState

# HDFS configuration
HDFS_URL = os.getenv("HDFS_URL", "http://hc1-c-0003u.hc.apac.bosch.com:9870")
HDFS_USER = os.getenv("HDFS_USER", "hdfs")

try:
    hdfs_client = InsecureClient(HDFS_URL, user=HDFS_USER)
except Exception as e:
    print(f"[ERROR] Unable to initialize HDFS Client: {e}")
    hdfs_client = None

CAR_FLEET = [
    ("EV_101", "SimuProA-1"), ("EV_102", "SimuProA-2"),
    ("EV_103", "SimuProA-3"), ("EV_104", "SimuProA-4"),
    ("EV_105", "SimuProA-5"), ("EV_106", "SimuProB-1"),
    ("EV_107", "SimuProB-2"), ("EV_108", "SimuProB-3"),
    ("EV_109", "SimuProB-4"), ("EV_110", "SimuProB-5"),
]

CSV_HEADER = [
    "id", "id_segment", "volt_V", "current_A", "soc_pct",
    "max_single_volt_V", "min_single_volt_V",
    "max_temp_C", "min_temp_C", "timestamp_s",
    "avg_speed_kmh", "hvac_active", "payload_kg",
    "regenerative_braking_Ah", "motor_rpm", "gear_position",
    "accelerator_pedal_pct", "brake_pedal_pct",
    "charger_connected", "label", "car_id", "car_model",
    "mileage_km", "actual_max_capacity_Ah", "nominal_capacity_Ah"
]

def setup_agent_for_generation(agent: EVAgent, mode: str, start_soc: float, end_soc: float):
    """
    Set up parameters for pure data generation.
    Clear old context to prevent LLM hallucination.
    """
    agent.state.soc_pct = start_soc
    agent.state.last_records = [] # Clear short-term memory

    if mode == "driving":
        chosen_tool = random.choice(["urban_drive", "highway_drive"])
    else:
        chosen_tool = random.choice(["fast_charge", "home_charge"])

    agent._transition_state(chosen_tool)
    agent.decision_engine.decide = lambda: chosen_tool

    if mode == "driving":
        agent.state.target_soc_for_charging = max(0, end_soc - 10)
        agent.state.target_soc_for_driving = 99.0
    else:
        agent.state.target_soc_for_driving = max(end_soc + 5, 95)
        agent.state.target_soc_for_charging = max(0, end_soc - 20)

def generate_records(agent: EVAgent, mode: str, end_soc: float, max_records: int):
    """Generate records in the given mode and yield chunks of 64 records."""
    buffer = []
    generated_count = 0
    stop_generation = False

    while generated_count < max_records and not stop_generation:
        try:
            # Generate a batch of 3 records
            telemetry_objs = agent.generate_batch()
            
            # Sleep 5 seconds ONCE for the whole batch of 3 records
            time.sleep(5)
        except Exception as e:
            print(f"  [ERROR] Batch generation failed: {e}")
            break

        # Split each record in the batch for saving and stop condition check
        for telemetry_obj in telemetry_objs:
            if generated_count >= max_records: 
                break

            record = telemetry_obj.model_dump()
            buffer.append(record)
            generated_count += 1
            current_soc = record["soc_pct"]

            if generated_count % 30 == 0:
                print(f"  [{mode.upper():8s}] {generated_count}/{max_records} records | SOC={current_soc:6.2f}%")

            # Check SOC stop condition
            if mode == "driving" and current_soc <= end_soc:
                print(f"  [{mode.upper():8s}] Done at #{generated_count} | SOC={current_soc:.2f}% (target <={end_soc}%)")
                stop_generation = True
            elif mode == "charging" and current_soc >= end_soc:
                print(f"  [{mode.upper():8s}] Done at #{generated_count} | SOC={current_soc:.2f}% (target >={end_soc}%)")
                stop_generation = True

            # --- FLUSH LOGIC: Push out when 64 samples collected ---
            if len(buffer) >= 64:
                yield buffer
                buffer = []
            
            if stop_generation:
                break

    # Push remaining records (if any) at the end
    if buffer:
        yield buffer

def save_to_hdfs(records: list[dict], hdfs_filepath: str):
    """Save data directly to HDFS via memory buffer (Always creates new file)."""
    if not hdfs_client:
        print("[ERROR] HDFS Client not connected. Skipping file save.")
        return

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=CSV_HEADER)
    
    # Always write Header since each chunk is an independent file
    writer.writeheader()
        
    for rec in records:
        writer.writerow({k: rec.get(k, "") for k in CSV_HEADER})
    
    try:
        hdfs_client.makedirs(os.path.dirname(hdfs_filepath))
        
        # Overwrite/Create new file, DO NOT use append
        with hdfs_client.write(hdfs_filepath, encoding='utf-8', overwrite=True) as writer_hdfs:
            writer_hdfs.write(csv_buffer.getvalue())
            
        file_name = os.path.basename(hdfs_filepath)
        print(f"  -> Saved {len(records)} records to new file: {file_name}")
    except Exception as e:
        print(f"  [ERROR] Error writing to HDFS: {e}")


def run_for_car(
    car_id: str,
    car_model: str,
    mode: str,
    hdfs_dir: str,
    max_records: int,
    drive_start: float = None,
    drive_end: float = None,
    charge_start: float = None,
    charge_end: float = None,
):
    print(f"\n{'='*60}")
    print(f"  {car_id} ({car_model}) | mode={mode}")
    print(f"{'='*60}")

    # 1. Initialize Agent
    agent = EVAgent(
        car_id=car_id,
        car_model=car_model,
        nominal_capacity=210.0 if "SimuProA" in car_model else 185.0,
    )

    # 2. Do not read or write JSON file
    agent._save_state = lambda: None

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_records = 0
    driving_end_soc = None
    car_hdfs_dir = f"{hdfs_dir.rstrip('/')}/{car_id}"

    # --- Driving phase ---
    if mode in ("driving", "both"):
        start = drive_start if drive_start is not None else random.uniform(88, 96)
        end = drive_end if drive_end is not None else random.uniform(12, 22)
        print(f"\n  [DRIVING GENERATION] SOC {start:.1f}% -> {end:.1f}%")
        
        setup_agent_for_generation(agent, "driving", start, end)
        
        chunk_idx = 1
        # Receive each batch of 64 lines from Generator
        for chunk in generate_records(agent, "driving", end, max_records):
            # Create independent filename for each batch: e.g. EV_104_driving_20260515_part001.csv
            hdfs_path = f"{car_hdfs_dir}/{car_id}_{ts_str}_part{chunk_idx:03d}.csv"
            
            save_to_hdfs(chunk, hdfs_path)
            
            chunk_idx += 1
            total_records += len(chunk)
            driving_end_soc = chunk[-1]["soc_pct"]

    # --- Charging phase ---
    if mode in ("charging", "both"):
        if mode == "both" and driving_end_soc is not None:
            cs = driving_end_soc
        else:
            cs = charge_start if charge_start is not None else random.uniform(5, 18)
        ce = charge_end if charge_end is not None else random.uniform(85, 96)
        print(f"\n  [CHARGING GENERATION] SOC {cs:.1f}% -> {ce:.1f}%")
        
        setup_agent_for_generation(agent, "charging", cs, ce)
        
        chunk_idx = 1
        # Receive each batch of 64 lines from Generator
        for chunk in generate_records(agent, "charging", ce, max_records):
            # Create independent filename for each batch
            hdfs_path = f"{car_hdfs_dir}/{car_id}_{ts_str}_part{chunk_idx:03d}.csv"
            
            save_to_hdfs(chunk, hdfs_path)
            
            chunk_idx += 1
            total_records += len(chunk)

    print(f"\n  Summary: {total_records} raw records generated & pushed to HDFS for {car_id}")

def main():
    parser = argparse.ArgumentParser(description="Quick EV data generation -> HDFS")
    parser.add_argument("--mode", choices=["driving", "charging", "both"], default="both")
    parser.add_argument("--car-id", default=None)
    parser.add_argument("--car-model", default=None)
    parser.add_argument("--all-cars", action="store_true")
    parser.add_argument("--drive-start", type=float, default=None)
    parser.add_argument("--drive-end", type=float, default=None)
    parser.add_argument("--charge-start", type=float, default=None)
    parser.add_argument("--charge-end", type=float, default=None)
    parser.add_argument("--hdfs-dir", default="/raw_data/battery_telemetry_v4")
    parser.add_argument("--max-records", type=int, default=2048)
    args = parser.parse_args()

    if args.all_cars:
        cars = CAR_FLEET
    elif args.car_id and args.car_model:
        cars = [(args.car_id, args.car_model)]
    else:
        parser.error("Provide --all-cars or both --car-id and --car-model")

    for car_id, car_model in cars:
        run_for_car(
            car_id=car_id, car_model=car_model, mode=args.mode,
            hdfs_dir=args.hdfs_dir, max_records=args.max_records,
            drive_start=args.drive_start, drive_end=args.drive_end,
            charge_start=args.charge_start, charge_end=args.charge_end,
        )

if __name__ == "__main__":
    main()