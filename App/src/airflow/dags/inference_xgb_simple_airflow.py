from datetime import timedelta
import sys
import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add source code path
DOCKER_SRC_PATH = '/opt/airflow/src'
if DOCKER_SRC_PATH not in sys.path:
    sys.path.append(DOCKER_SRC_PATH)

from ml_airflow.testing.xgb_simple_infer_test import run_xgb_predict_pipeline


def task_wrapper_for_xgb_inference():
    print("[START] Executing daily XGBoost Simple Inference pipeline...")
    run_xgb_predict_pipeline()
    print("[SUCCESS] XGBoost Simple Inference pipeline finished successfully & Results saved.")


default_args = {
    'owner': 'ml_team',
    'depends_on_past': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'ev_xgb_simple_inference_dag',
    default_args=default_args,
    description='Daily simple XGBoost inference pipeline using single HDFS model',
    schedule='0 0 * * *',
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['ev', 'xgboost', 'inference', 'xgb-simple'],
) as dag:

    inference_task = PythonOperator(
        task_id='xgb_load_model_and_predict',
        python_callable=task_wrapper_for_xgb_inference,
        execution_timeout=timedelta(hours=4),
    )
