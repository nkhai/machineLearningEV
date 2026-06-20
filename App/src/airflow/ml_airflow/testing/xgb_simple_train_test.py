import os
import time
import json
import requests
from ml_airflow.config.config import AIAPI_URL, AIAPI_TIMEOUT

HDFS_URL = os.environ.get("HDFS_URL", "http://hc1-c-0003u.hc.apac.bosch.com:9870")
USER_ID = os.environ.get("AIRFLOW_USER_ID", "system_admin")


def submit_xgb_train_job(hdfs_url: str, user_id: str = "system_admin"):
    """Submit a simple XGBoost training job to AIAPI."""
    resp = requests.post(
        f"{AIAPI_URL}/api/v1/xgb_train",
        json={
            "HDFS_URL": hdfs_url,
            "user_id": user_id,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"XGBoost training job submitted: {data['job_id']}")
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


def run_xgb_train_pipeline(hdfs_url=None, user_id=None):
    if hdfs_url is None:
        hdfs_url = HDFS_URL
    if user_id is None:
        user_id = USER_ID

    print("=== Submitting simple XGBoost training job to AIAPI ===")
    print(f"AIAPI_URL: {AIAPI_URL}")
    print(f"HDFS_URL: {hdfs_url}")
    print(f"USER_ID: {user_id}")

    job_id = submit_xgb_train_job(hdfs_url, user_id)
    print(f"\n=== Polling job status (job_id={job_id}) ===\n")

    job = poll_job_status(job_id)

    print(f"\n=== Job Result ===")
    print(f"Status: {job['status']}")
    print(f"Message: {job['message']}")

    if job["status"] == "completed" and job.get("result"):
        result = job["result"]
        print(f"Model version: {result.get('version')}")
        print(f"Model directory: {result.get('model_directory')}")
        print(f"Training cars: {result.get('train_cars')}")
        print(f"Saved files: {result.get('saved_files')}")
    elif job["status"] == "failed" and job.get("error"):
        print(f"Error: {job['error']}")

    return job


if __name__ == "__main__":
    run_xgb_train_pipeline()
