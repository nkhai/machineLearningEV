"""
Airflow DAG that calls AIAPI REST endpoints for training and prediction.

Usage:
  export AIAPI_BASE_URL=http://localhost:8000
  airflow dags trigger aiapi_train_and_predict
"""
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import requests

AIAPI_BASE_URL = os.getenv("AIAPI_BASE_URL", "http://localhost:8000")
HDFS_URL = "http://hc1-c-0003u.hc.apac.bosch.com:9870"
PREDICT_CAR_IDS = ["EV_104", "EV_105", "EV_109", "EV_110"]
PREDICT_DATE = "latest"
POLL_INTERVAL = 30  # seconds
POLL_MAX_RETRIES = 120  # ~1 hour max wait


def poll_job(job_id, dag_id, task_id, **context):
    """Poll AIAPI until job completes or fails."""
    for attempt in range(POLL_MAX_RETRIES):
        try:
            resp = requests.get(f"{AIAPI_BASE_URL}/api/v1/jobs/{job_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            progress = data.get("progress", "")
            print(f"[{dag_id}/{task_id}] attempt={attempt} status={status} progress={progress}")
            if status in ("completed", "failed"):
                return data
        except Exception as e:
            print(f"Poll error: {e}")
        context["ti"].xcom_push(key="poll_attempt", value=attempt)
        import time
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"Job {job_id} timed out after {POLL_MAX_RETRIES * POLL_INTERVAL}s")


def submit_train(**context):
    """Submit training job to AIAPI."""
    print(f"Submitting training job to {AIAPI_BASE_URL}...")
    resp = requests.post(
        f"{AIAPI_BASE_URL}/api/v1/train",
        json={"HDFS_URL": HDFS_URL, "user_id": "airflow"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    job_id = data["job_id"]
    print(f"Training job submitted: {job_id}")
    result = poll_job(job_id, "train", "run_train", **context)
    if result.get("status") == "failed":
        raise RuntimeError(f"Training failed: {result.get('error', 'unknown')}")
    print(f"Training completed. Result: {result.get('result')}")
    context["ti"].xcom_push(key="job_id", value=job_id)


def submit_predict(**context):
    """Submit prediction job to AIAPI."""
    print(f"Submitting prediction job to {AIAPI_BASE_URL}...")
    print(f"  car_ids={PREDICT_CAR_IDS}, date={PREDICT_DATE}")
    resp = requests.post(
        f"{AIAPI_BASE_URL}/api/v1/predict",
        json={
            "HDFS_URL": HDFS_URL,
            "car_ids": PREDICT_CAR_IDS,
            "predict_date": PREDICT_DATE,
            "user_id": "airflow",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    job_id = data["job_id"]
    print(f"Prediction job submitted: {job_id}")
    result = poll_job(job_id, "predict", "run_predict", **context)
    if result.get("status") == "failed":
        raise RuntimeError(f"Prediction failed: {result.get('error', 'unknown')}")
    predictions = result.get("result", {}).get("predictions", [])
    for p in predictions:
        print(
            f"  {p['car_id']}: pred={p['final_ensemble_pred']} "
            f"gt={p['gt_capacity']} method={p['prediction_method']}"
        )
    context["ti"].xcom_push(key="job_id", value=job_id)
    context["ti"].xcom_push(key="predictions", value=predictions)


with DAG(
    "aiapi_train_and_predict",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args={
        "owner": "airflow",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["train", "predict", "aiapi"],
) as dag:
    train = PythonOperator(task_id="run_train", python_callable=submit_train)
    predict = PythonOperator(task_id="run_predict", python_callable=submit_predict)
    train >> predict
