from datetime import timedelta
import sys
import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add source code path
DOCKER_SRC_PATH = '/opt/airflow/src'
if DOCKER_SRC_PATH not in sys.path:
    sys.path.append(DOCKER_SRC_PATH)

from ml_airflow.testing.train_xg_test import run_train_pipeline


def task_wrapper_for_training(**kwargs):
    if kwargs.get('conf'):
        hdfs_url = kwargs['conf'].get('hdfs_url')
        user_id = kwargs['conf'].get('user_id')
    elif kwargs.get('dag_run') and kwargs['dag_run'].conf:
        hdfs_url = kwargs['dag_run'].conf.get('hdfs_url')
        user_id = kwargs['dag_run'].conf.get('user_id')
    else:
        hdfs_url = None
        user_id = None
    print(f"[START] Executing Training pipeline... (hdfs_url={hdfs_url}, user_id={user_id})")
    run_train_pipeline(hdfs_url=hdfs_url, user_id=user_id)
    print("[SUCCESS] Training pipeline finished successfully & Models saved to HDFS.")


default_args = {
    'owner': 'ml_team',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'ev_battery_training_dag',
    default_args=default_args,
    description='Manual training pipeline for EV Battery with XGBoost',
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['ev', 'xgboost', 'training'],
) as dag:

    train_task = PythonOperator(
        task_id='train_and_save_model',
        python_callable=task_wrapper_for_training,
        execution_timeout=timedelta(hours=6),
    )
