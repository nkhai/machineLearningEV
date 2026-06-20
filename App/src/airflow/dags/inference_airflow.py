from datetime import timedelta
import sys
import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add source code path
DOCKER_SRC_PATH = '/opt/airflow/src'
if DOCKER_SRC_PATH not in sys.path:
    sys.path.append(DOCKER_SRC_PATH)

from ml_airflow.testing.infer_nn_test import run_inference_pipeline_nn


def task_wrapper_for_inference():
    print("[START] Executing daily Inference pipeline...")
    run_inference_pipeline_nn()
    print("[SUCCESS] Inference pipeline finished successfully & Results saved.")


default_args = {
    'owner': 'ml_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'ev_battery_inference_dag',
    default_args=default_args,
    description='Daily inference pipeline using saved HDFS models',
    schedule='0 0 * * *',
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['ev', 'xgboost', 'inference'],
) as dag:

    inference_task = PythonOperator(
        task_id='load_model_and_predict',
        python_callable=task_wrapper_for_inference,
        execution_timeout=timedelta(hours=4),
    )
