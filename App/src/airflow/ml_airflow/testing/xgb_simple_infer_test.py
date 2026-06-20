import os
import time
import json
import requests
from ml_airflow.config.config import AIAPI_URL, AIAPI_TIMEOUT

HDFS_URL = os.environ.get("HDFS_URL", "http://hc1-c-0003u.hc.apac.bosch.com:9870")
USER_ID = os.environ.get("AIRFLOW_USER_ID", "system_admin")


def submit_xgb_predict_job(hdfs_url: str, car_ids: list, predict_date: str, user_id: str = "system_admin"):
    """Submit a simple XGBoost prediction job to AIAPI."""
    resp = requests.post(
        f"{AIAPI_URL}/api/v1/xgb_predict",
        json={
            "HDFS_URL": hdfs_url,
            "car_ids": car_ids,
            "predict_date": predict_date,
            "user_id": user_id,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"XGBoost prediction job submitted: {data['job_id']}")
    return data["job_id"]


def poll_job_status(job_id: str, interval: int = 10, timeout: int = AIAPI_TIMEOUT):
    """Poll AIAPI for job status until completion or timeout."""
    start_time = time.time()
    last_progress = ""

    while time.time() - start_time < timeout:
        resp = requests.get(
            f"{AIAPI_URL}/api/v1/jobs/{job_id}",
            timeout=30,
        )
        resp.raise_for_status()
        job = resp.json()

        status = job["status"]
        progress = job.get("progress", "")
        if progress != last_progress:
            print(f"[{status}] {progress}")
            last_progress = progress

        if status in ("completed", "failed"):
            return job

        time.sleep(interval)

    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def run_xgb_predict_pipeline(car_ids=None, predict_date=None):
    if car_ids is None:
        car_ids = ['EV_104', 'EV_105', 'EV_109', 'EV_110']
    if predict_date is None:
        predict_date = 'latest'

    print("=== Submitting simple XGBoost prediction job to AIAPI ===")
    print(f"AIAPI_URL: {AIAPI_URL}")
    print(f"HDFS_URL: {HDFS_URL}")
    print(f"USER_ID: {USER_ID}")
    print(f"Car IDs: {car_ids}")
    print(f"Predict Date: {predict_date}")

    job_id = submit_xgb_predict_job(HDFS_URL, car_ids, predict_date, USER_ID)
    print(f"\n=== Polling job status (job_id={job_id}) ===\n")

    job = poll_job_status(job_id)

    print(f"\n=== Job Result ===")
    print(f"Status: {job['status']}")
    print(f"Message: {job['message']}")

    if job["status"] == "completed" and job.get("result"):
        result = job["result"]
        print(f"Cars predicted: {result.get('cars_predicted')}")
        print(f"Metrics: {json.dumps(result.get('metrics', {}), indent=2)}")
        print(f"Predictions: {json.dumps(result.get('predictions', []), indent=2)}")
        print(f"Result CSV: {result.get('result_csv_directory')}")
        print(f"Models loaded from: {result.get('models_loaded_from')}")
    elif job["status"] == "failed" and job.get("error"):
        print(f"Error: {job['error']}")

    return job


if __name__ == "__main__":
    run_xgb_predict_pipeline()
