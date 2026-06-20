"""
EV telemetry Kafka producer using the EV Agent architecture.

Each EV is an independent agent with tools (driving, charging) that it calls
autonomously based on SOC thresholds and decision logic.

Usage:
    from services.producer import producer_loop
    producer_loop(car_id="EV_101", stop_event=..., get_label_fn=...)
"""

import json
import threading
import time
import traceback

from agent.ev_agent import EVAgent
from core.constants import TELEMETRY_TOPIC, RECORD_INTERVAL_SECONDS
from core.state import add_log
from services.kafka import create_producer, create_topic_if_not_exists


def producer_loop(car_id: str, car_model: str, stop_event: threading.Event, get_label_fn):
    """Main producer loop that generates records via EVAgent and sends to Kafka."""
    add_log("INFO", "producer", f"EV {car_id} agent producer starting")

    producer = create_producer()
    if producer:
        create_topic_if_not_exists(TELEMETRY_TOPIC)

    # Create the agent - it encapsulates LLM, tools, state, and decision engine
    agent = EVAgent(
        car_id=car_id,
        car_model=car_model,
        get_label_fn=get_label_fn,
    )

    try:
        while not stop_event.is_set():
            try:
                # Update: Use the batch generation method
                telemetry_objs = agent.generate_batch()
                
                # Iterate through the generated batch of records
                for telemetry_obj in telemetry_objs:
                    if stop_event.is_set():
                        break
                        
                    record = telemetry_obj.model_dump()

                    # Type sanitization (Keeping your existing logic)
                    for k, v in list(record.items()):
                        if isinstance(v, (int, float, bool)):
                            continue
                        try:
                            record[k] = float(v)
                        except Exception:
                            pass

                    # Send to Kafka
                    if producer:
                        try:
                            producer.send(
                                TELEMETRY_TOPIC,
                                key=str(car_id).encode("utf-8"),
                                value=record
                            )
                        except Exception as e:
                            add_log("ERROR", "kafka", f"EV {car_id} send error: {e}")

                    # Logging
                    add_log(
                        "INFO", "producer",
                        f"EV={car_id} ts={record.get('timestamp_s')} "
                        f"soc={record.get('soc_pct')} "
                        f"segment={record.get('id_segment')}"
                    )
                    
                    # Optional: small sleep between individual records within the batch
                    # to simulate a steady stream rather than a burst of 3.
                    time.sleep(1)

            except Exception as e:
                add_log("ERROR", "producer", f"EV {car_id} generation error: {e}")
                time.sleep(1)
                continue

            # Sleep between batches.
            # E.g., if LLM takes time, adjust RECORD_INTERVAL_SECONDS accordingly.
            time.sleep(RECORD_INTERVAL_SECONDS)

    except Exception:
        add_log("ERROR", "producer", f"EV {car_id} agent crashed:\n{traceback.format_exc()}")

    finally:
        if producer:
            producer.flush()
            producer.close()
        add_log("INFO", "producer", f"EV {car_id} agent producer stopped")