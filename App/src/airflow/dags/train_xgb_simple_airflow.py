from datetime import timedelta
import sys
import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Add source code path
DOCKER_SRC_PATH = '/opt/airflow/src'
if DOCKER_SRC_PATH not in sys.path:
    sys.path.append(DOCKER_SRC_PATH)

from ml_airflow.testing.xgb_simple_train_test import run_xgb_train_pipeline


def task_wrapper_for_xgb_training(**kwargs):
    if kwargs.get('conf'):
        hdfs_url = kwargs['conf'].get('hdfs_url')
        user_id = kwargs['conf'].get('user_id')
    elif kwargs.get('dag_run') and kwargs['dag_run'].conf:
        hdfs_url = kwargs['dag_run'].conf.get('hdfs_url')
        user_id = kwargs['dag_run'].conf.get('user_id')
    else:
        hdfs_url = None
        user_id = None
    print(f"[START] Executing XGBoost Simple Training pipeline... (hdfs_url={hdfs_url}, user_id={user_id})")
    run_xgb_train_pipeline(hdfs_url=hdfs_url, user_id=user_id)
    print("[SUCCESS] XGBoost Simple Training pipeline finished successfully & Model saved to HDFS.")


default_args = {
    'owner': 'ml_team',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    'ev_xgb_simple_training_dag',
    default_args=default_args,
    description='Manual simple XGBoost training pipeline (single model, no ensemble NN)',
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Ho_Chi_Minh"),
    catchup=False,
    tags=['ev', 'xgboost', 'training', 'xgb-simple'],
) as dag:

    train_task = PythonOperator(
        task_id='xgb_train_and_save_model',
        python_callable=task_wrapper_for_xgb_training,
        execution_timeout=timedelta(hours=6),
    )
