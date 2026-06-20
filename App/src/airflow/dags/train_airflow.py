from datetime import timedelta
import sys
import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator

# Thêm đường dẫn source code
DOCKER_SRC_PATH = '/opt/airflow/src'
if DOCKER_SRC_PATH not in sys.path:
    sys.path.append(DOCKER_SRC_PATH)

from ml_airflow.testing.train_xg_test import run_train_pipeline

# ==================== TASK WRAPPER ====================
def task_wrapper_for_training():
    print("[START] Executing PCA-XGBoost training pipeline...")
    run_train_pipeline()
    print("[SUCCESS] Training pipeline finished successfully & Models saved to HDFS.")

# ==================== DAG CONFIGURATION ====================
default_args = {
    'owner': 'ml_team',
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=0.1),
}

with DAG(
    'ev_battery_training_dag', 
    default_args=default_args,
    description='Training pipeline for EV Battery with PCA and XGBoost',
    # schedule='@weekly', # Chạy định kỳ hàng tuần (hoặc đổi thành None nếu chỉ muốn kích hoạt bằng tay)
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