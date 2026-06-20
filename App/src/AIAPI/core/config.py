import logging
import torch

# ==================== LOGGING CONFIG ====================
logging.getLogger("hdfs").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# ==================== HDFS CONFIG ====================
HDFS_URL = "http://hc1-c-0003u.hc.apac.bosch.com:9870"
HDFS_USER = "hdfs"
HDFS_OUTPUT_DIR = "/output_data"

# ==================== DATA PATHS ====================
RAW_DATA_DIR = "/raw_sample_data/training"
INFERENCE_BASE_DIR = "/raw_data/battery_telemetry/"

# ==================== MODEL CONFIG ====================
WINDOW_SIZE = 128
FEATURE_COLS = [
    "volt_V", "current_A", "soc_pct", "max_single_volt_V",
    "min_single_volt_V", "max_temp_C", "min_temp_C" #, "mileage_km"
]

FEATURE_COLS_CHG = [
    "volt_V", "current_A", "soc_pct", "max_single_volt_V",
    "min_single_volt_V", "max_temp_C", "min_temp_C" #, "mileage_km"
]

FEATURE_COLS_DRV = [
    "volt_V", "current_A", "soc_pct", "max_single_volt_V",
    "min_single_volt_V", "max_temp_C", "min_temp_C" #, "mileage_km"
]

NUM_FILES_LIMIT = None

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEQ_LEN = 128
