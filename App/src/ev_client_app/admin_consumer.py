import threading
import json
import os
import traceback
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from database.cache import registered_cars

from state import latest_status_record, set_latest_status_record, add_log
from dotenv import load_dotenv
load_dotenv()

# ===========================
# CONFIG
# ===========================
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS").split(",")
STATUS_TOPIC = os.getenv("STATUS_TOPIC")

# ===========================
# CREATE CONSUMER
# ===========================
def create_consumer(topic: str, group_id: str):
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=KAFKA_BROKERS,
            auto_offset_reset="latest",  
            enable_auto_commit=True,
            group_id=group_id,
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            key_deserializer=lambda x: x.decode("utf-8") if x else None,
        )
        add_log("INFO", "admin_consumer", f"Connected to Kafka topic: {topic}")
        return consumer
    except NoBrokersAvailable:
        add_log("ERROR", "admin_consumer", "Cannot connect to Kafka broker")
        return None

# ===========================
# CONSUMER LOOP
# ===========================
def admin_status_consumer_loop(stop_event: threading.Event):
    consumer = create_consumer(STATUS_TOPIC, group_id="admin-status-group")
    if not consumer:
        return

    add_log("INFO", "admin_consumer", f"Admin Status consumer started")

    try:
        for message in consumer:
            if stop_event.is_set():
                break

            try:
                car_id = message.key
                record = message.value

                if car_id not in registered_cars:
                    add_log(
                        "DEBUG",
                        "admin_consumer",
                        f"[Admin Status] Ignore EV={car_id} (not registered)"
                    )
                    continue

                set_latest_status_record(car_id, record)

                add_log(
                    "DEBUG",
                    "admin_consumer",
                    f"[Admin Status] EV={car_id} ts={record.get('timestamp')}"
                )

            except Exception:
                add_log("ERROR", "admin_consumer", traceback.format_exc())

    finally:
        consumer.close()
        add_log("INFO", "admin_consumer", "Admin Status consumer stopped")

# ===========================
# START CONSUMER THREAD
# ===========================
def start_admin_consumer():
    stop_event = threading.Event()
    thread = threading.Thread(
        target=admin_status_consumer_loop,
        args=(stop_event,),
        daemon=True
    )
    thread.start()
    add_log("INFO", "admin_consumer", "Admin consumer thread started")
    return stop_event, thread