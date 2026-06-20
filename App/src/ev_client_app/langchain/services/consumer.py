"""
EV telemetry Kafka consumer.

Usage:
    from services.consumer import telemetry_consumer_loop
"""

import threading
import traceback

from core.constants import TELEMETRY_TOPIC
from core.state import (
    set_latest_record,
    append_history,
    add_log,
)
from services.kafka import create_consumer


def telemetry_consumer_loop(stop_event: threading.Event, car_id_filter: str):
    """Consume telemetry records from Kafka and update in-memory state."""
    consumer = create_consumer(TELEMETRY_TOPIC, f"telemetry-group-{car_id_filter}")

    if not consumer:
        return

    add_log("INFO", "consumer", f"Telemetry consumer started for EV {car_id_filter}")

    try:
        for message in consumer:
            if stop_event.is_set():
                break

            try:
                car_id = message.key
                if car_id != car_id_filter:
                    continue
                record = message.value

                set_latest_record(car_id, record)
                append_history(car_id, record)

                add_log(
                    "DEBUG",
                    "consumer",
                    f"[Telemetry] EV={car_id} ts={record.get('timestamp_s')}"
                )

            except Exception:
                add_log("ERROR", "consumer", traceback.format_exc())

    finally:
        consumer.close()
        add_log("INFO", "consumer", f"Telemetry consumer stopped for EV {car_id_filter}")
