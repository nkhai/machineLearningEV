"""
Admin status consumer.

Consumes ev.battery.telemetry_v3 and updates state for registered cars only.
Unlike the telemetry consumer which filters by car_id, the admin consumer
subscribes to ALL messages and checks against the registered_cars cache.

Usage:
    from admin.consumer import start_admin_consumer
"""

import os
import threading
from dotenv import load_dotenv

from core.state import add_log

load_dotenv()

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "hc1-c-0003u.hc.apac.bosch.com:9092").split(",")
ADMIN_GROUP_ID = "admin-status-group"

# TOPIC CHANGED TO: ev.battery.telemetry_v4
STATUS_TOPIC_NAME = os.getenv("STATUS_TOPIC", "ev.battery.telemetry_v4")


class AdminStatusConsumer:
    """Consumes telemetry topic and updates status state for registered cars."""

    def __init__(self, topic: str, brokers: list):
        self.topic = topic
        self.brokers = brokers
        self.consumer = None

    def create_consumer(self):
        """Create a Kafka consumer for the admin status topic."""
        import json
        from kafka import KafkaConsumer
        from kafka.errors import NoBrokersAvailable

        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.brokers,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                group_id=ADMIN_GROUP_ID,
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
                key_deserializer=lambda x: x.decode("utf-8") if x else None,
            )
            add_log("INFO", "admin_consumer", f"Connected to Kafka topic: {self.topic}")
            return self.consumer
        except NoBrokersAvailable:
            add_log("ERROR", "admin_consumer", "Cannot connect to Kafka broker")
            return None


def start_admin_consumer() -> tuple[threading.Event, threading.Thread]:
    """Start the admin consumer and return (stop_event, thread)."""
    stop_event = threading.Event()

    consumer = AdminStatusConsumer(
        topic=STATUS_TOPIC_NAME,
        brokers=KAFKA_BROKERS,
    )

    def admin_loop():
        from core.state import set_latest_status_record
        consumer.consumer = consumer.create_consumer()
        if not consumer.consumer:
            return

        add_log("INFO", "admin_consumer", "Admin Status consumer started")

        try:
            for message in consumer.consumer:
                if stop_event.is_set():
                    break
                try:
                    record = message.value
                    
                    # Extract car_id from Kafka key. If not available (None), pull from the record
                    car_id = message.key
                    if not car_id and isinstance(record, dict):
                        car_id = record.get("car_id")
                    
                    # Skip if the packet has no vehicle identifier at all
                    if not car_id:
                        continue

                    set_latest_status_record(car_id, record)

                    add_log(
                        "DEBUG",
                        "admin_consumer",
                        f"[Admin Status] EV={car_id} ts={record.get('timestamp_s')}"
                    )
                except Exception:
                    import traceback
                    add_log("ERROR", "admin_consumer", traceback.format_exc())
        finally:
            consumer.consumer.close()
            add_log("INFO", "admin_consumer", "Admin Status consumer stopped")

    thread = threading.Thread(target=admin_loop, daemon=True)
    thread.start()
    add_log("INFO", "admin_consumer", "Admin consumer thread started")

    return stop_event, thread


if __name__ == "__main__":
    # Standalone mode for testing
    stop_event, thread = start_admin_consumer()
    try:
        while True:
            stop_event.wait(1)
    except KeyboardInterrupt:
        stop_event.set()
        print("Admin consumer stopped.")