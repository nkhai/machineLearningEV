import json
import threading
import traceback
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from state import (
    set_latest_record,
    append_history,
    set_latest_status_record,
    append_status_history,
    add_log
)

# ===========================
# CONFIG 
# ===========================
KAFKA_BROKERS = ["hc1-c-0003u.hc.apac.bosch.com:9092"]

TELEMETRY_TOPIC = "ev.battery.telemetry"
STATUS_TOPIC = "ev.vehicle.status"

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
        add_log("INFO", "consumer", f"Connected to Kafka topic: {topic}")
        return consumer
    except NoBrokersAvailable:
        add_log("ERROR", "consumer", "Cannot connect to Kafka broker")
        return None

def telemetry_consumer_loop(stop_event: threading.Event, car_id_filter: str):
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
                    f"[Telemetry] EV={car_id} ts={record.get('timestamp')}"
                )

            except Exception:
                add_log("ERROR", "consumer", traceback.format_exc())

    finally:
        consumer.close()
        add_log("INFO", "consumer", f"Telemetry consumer stopped for EV {car_id_filter}")

def status_consumer_loop(stop_event: threading.Event, car_id_filter: str):
    consumer = create_consumer(STATUS_TOPIC, f"status-group-{car_id_filter}")

    if not consumer:
        return

    add_log("INFO", "consumer", f"Status consumer started for EV {car_id_filter}")

    try:
        for message in consumer:
            if stop_event.is_set():
                break

            try:
                car_id = message.key
                if car_id != car_id_filter:
                    continue
                record = message.value

                set_latest_status_record(car_id, record)
                append_status_history(car_id, record)

                add_log(
                    "DEBUG",
                    "consumer",
                    f"[Status] EV={car_id}"
                )

            except Exception:
                add_log("ERROR", "consumer", traceback.format_exc())

    finally:
        consumer.close()
        add_log("INFO", "consumer", f"Status consumer stopped for EV {car_id_filter}")
