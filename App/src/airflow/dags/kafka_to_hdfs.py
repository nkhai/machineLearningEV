from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from kafka import KafkaConsumer
from hdfs import InsecureClient
import json, csv
import pandas as pd
import os
from collections import defaultdict
from itertools import chain
from airflow.hooks.base import BaseHook
from airflow.models import Variable
kafka_conn = BaseHook.get_connection("kafka_default")
KAFKA_BROKER = f"{kafka_conn.host}:{kafka_conn.port}"
TOPIC = Variable.get("KAFKA_TOPIC")
GROUP_ID = Variable.get("KAFKA_GROUP_ID")
OUTPUT_DIR = "/opt/airflow/data"

hdfs_conn = BaseHook.get_connection("hdfs_default")
HDFS_URL = f"{hdfs_conn.host}:{hdfs_conn.port}"
HDFS_USER = Variable.get("HDFS_USER")
HDFS_DIR = Variable.get("HDFS_DIR")
def read_kafka_and_save_csv(**context):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=GROUP_ID,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        consumer_timeout_ms = 60000  
    )
    records = defaultdict(list)

    for msg in consumer:
        if msg.value is None or msg.key is None:
            continue
        row = msg.value  
        row["vehicle_name"] = msg.key
        records[msg.key].append(row)

    consumer.close()
    if not records:
        print("No data from Kafka")
    else:
        csv_files = []
        for vehicle, record in records.items():
                fieldnames = set()
                for r in record:
                        fieldnames.update(r.keys())
                file_name = f"{vehicle}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                file_path = os.path.join(OUTPUT_DIR, file_name)
                with open(file_path, "w", newline="") as f:
                        writer = csv.DictWriter(
                                f,
                                fieldnames=fieldnames,
                                extrasaction="ignore"
                        )
                        writer.writeheader()
                        writer.writerows(record)
                csv_files.append(file_path)
                print(f"Created CSV for {vehicle}: {file_path}")
        context["ti"].xcom_push(key="csv_files", value=csv_files)
def upload_csv_to_hdfs(**context):
    # Get the CSV path from previous task
    ti = context['ti']
    csv_files = ti.xcom_pull(
        key="csv_files",
        task_ids="read_kafka_save_csv"
    )
    if not csv_files:
        print("CSV file not found, skipping HDFS upload")
        return

    client = InsecureClient(HDFS_URL, user=HDFS_USER)

 
    # Upload CSV
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"File missing, skip: {csv_file}")
            continue
        vehicle_name = os.path.basename(csv_file).split("_")[0]
        vehicle_hdfs_dir = f"{HDFS_DIR}/{vehicle_name}"
        client.makedirs(vehicle_hdfs_dir)
        hdfs_path = f"{vehicle_hdfs_dir}/{os.path.basename(csv_file)}"
        client.upload(hdfs_path, csv_file, overwrite=True)
        print(f"Uploaded to HDFS: {hdfs_path}")
default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="kafka_to_hdfs",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=timedelta(minutes=15),
    catchup=False,
) as dag:

    kafka_to_csv = PythonOperator(
        task_id="read_kafka_save_csv",
        python_callable=read_kafka_and_save_csv,
    )
    csv_to_hdfs = PythonOperator(
        task_id="upload_csv_to_hdfs",
        python_callable=upload_csv_to_hdfs,
    )
    kafka_to_csv >> csv_to_hdfs

