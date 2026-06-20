import os
import io
import numpy as np
import xgboost as xgb
import torch
import matplotlib.pyplot as plt # Thêm thư viện vẽ biểu đồ
from collections import defaultdict
from sklearn.metrics import mean_squared_error
from hdfs import InsecureClient

# Internal imports
from ml_airflow.config.config import HDFS_URL, HDFS_USER, NUM_FILES_LIMIT
from ml_airflow.data_processing.data_utils import get_hdfs_files_filtered, load_data_universal, filter_by_modality, save_csv_hdfs, load_artifacts_from_hdfs
from ml_airflow.data_processing.split_and_extract import extract_features_2d 
from ml_airflow.models.nn import EnsembleNN # Import mô hình NN

INFERENCE_BASE_DIR = "/raw_data/battery_telemetry_v2"
HDFS_MODEL_DIR = "/models/battery_health_ensemble" 
HDFS_IMAGE_DIR = "/models/learning_curve" # Thư mục lưu biểu đồ trên HDFS

def run_inference_pipeline_nn():
    client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=60)

    print("\n===== STEP 1: LOADING MODELS & SCALERS FROM HDFS =====")
    xgb_model_chg, scaler_chg = load_artifacts_from_hdfs(client, HDFS_MODEL_DIR, "chg")
    xgb_model_drv, scaler_drv = load_artifacts_from_hdfs(client, HDFS_MODEL_DIR, "drv")

    # Tải mô hình Meta-Learner (EnsembleNN)
    nn_model = EnsembleNN()
    try:
        # 1. Đọc stream dữ liệu từ HDFS và chuyển thành bytes
        with client.read(f"{HDFS_MODEL_DIR}/ensemble_nn.pth") as reader:
            model_bytes = reader.read()
            
        # 2. Đưa bytes vào io.BytesIO để giả lập file cho PyTorch
        buffer = io.BytesIO(model_bytes)
        
        # 3. Load weights
        nn_model.load_state_dict(torch.load(buffer, map_location=torch.device('cpu'), weights_only=True))
        nn_model.eval() # Chuyển sang chế độ inference
        print("✓ Successfully loaded Meta-Learner NN from HDFS.")
        
    except Exception as e:
        print(f"Warning: Could not load Meta-Learner NN. Will fallback to Simple Average. Error: {e}")
        nn_model = None
        
    print("\n===== STEP 2: LOADING INFERENCE DATA =====")
    try:
        # Lấy danh sách tất cả các file
        all_inf_files = get_hdfs_files_filtered(client, INFERENCE_BASE_DIR, limit=NUM_FILES_LIMIT)
        
        # BỘ LỌC TEST NHANH: Chỉ lấy EV_015 và EV_016
        target_inf_evs = ['EV_015', 'EV_016']
        inf_files = [f for f in all_inf_files if any(ev in f for ev in target_inf_evs)]
        
        print(f"Found {len(inf_files)} files for {target_inf_evs} out of {len(all_inf_files)} total files.")
    except Exception as e:
        print(f"Error reading inference directory: {e}")
        inf_files = []

    if not inf_files:
        print("No inference data found for target EVs. Exiting.")
        return

    inf_raw = load_data_universal(client, inf_files, mode='inference')
    
    inf_chg = filter_by_modality(inf_raw, is_charge=True)
    inf_drv = filter_by_modality(inf_raw, is_charge=False)
    
    inf_preds_chg = defaultdict(list)
    inf_preds_drv = defaultdict(list)
    inf_true_cap = {}
    inf_mileage = {}

    print("\n===== STEP 3: PREDICTING =====")

    if inf_chg and xgb_model_chg is not None:
        X_inf_chg, _ = extract_features_2d(inf_chg)
        if scaler_chg is not None:
            X_inf_chg = scaler_chg.transform(X_inf_chg)
            
        preds_chg = xgb_model_chg.predict(xgb.DMatrix(X_inf_chg))
        
        for p, (_, meta) in zip(preds_chg, inf_chg):
            inf_preds_chg[meta["car_id"]].append(p)
            inf_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)
            inf_mileage[meta["car_id"]] = max(inf_mileage.get(meta["car_id"], 0), meta.get("mileage_km", 0))

    if inf_drv and xgb_model_drv is not None:
        X_inf_drv, _ = extract_features_2d(inf_drv)
        if scaler_drv is not None:
            X_inf_drv = scaler_drv.transform(X_inf_drv)
            
        preds_drv = xgb_model_drv.predict(xgb.DMatrix(X_inf_drv))
        
        for p, (_, meta) in zip(preds_drv, inf_drv):
            inf_preds_drv[meta["car_id"]].append(p)
            inf_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)
            inf_mileage[meta["car_id"]] = max(inf_mileage.get(meta["car_id"], 0), meta.get("mileage_km", 0))

    print("\n===== STEP 4: ENSEMBLE & SAVING RESULTS =====")
    final_results = []
    all_inf_cars = set(list(inf_preds_chg.keys()) + list(inf_preds_drv.keys()))
    has_ground_truth = False
    
    for car_id in all_inf_cars:
        gt = inf_true_cap.get(car_id, -1)
        if gt > 0: has_ground_truth = True
        
        p_chg = np.mean(inf_preds_chg[car_id]) if car_id in inf_preds_chg else None
        p_drv = np.mean(inf_preds_drv[car_id]) if car_id in inf_preds_drv else None
        
        if p_chg is not None and p_drv is not None:
            # SỬ DỤNG NEURAL NETWORK CHO ENSEMBLE
            if nn_model is not None:
                # Chuyển thẳng 2 dự đoán thành Tensor (không cần Scaler, không cần diff/ratio)
                t_chg = torch.tensor([[p_chg]], dtype=torch.float32)
                t_drv = torch.tensor([[p_drv]], dtype=torch.float32)
                
                with torch.no_grad():
                    # Đưa 2 Tensor vào mô hình
                    final_pred = nn_model(t_chg, t_drv).item()
                method = "Ensemble (Neural Network)"
            else:
                final_pred = (p_chg + p_drv) / 2.0
                method = "Ensemble (Simple Avg Fallback)"
                
        elif p_chg is not None:
            final_pred = p_chg
            method = "XGB (Charging Only)"
        elif p_drv is not None:
            final_pred = p_drv
            method = "XGB (Driving Only)"
        else:
            continue
            
        err = float(final_pred - gt) if gt > 0 else 0.0
        
        final_results.append([
            car_id, inf_mileage.get(car_id, 0), method,
            float(gt) if gt > 0 else -1.0, 
            float(p_chg) if p_chg else -1.0,
            float(p_drv) if p_drv else -1.0,
            float(final_pred), err
        ])

    if has_ground_truth:
        # Lấy ra những xe CÓ CẢ 3 DỮ LIỆU: Ground Truth, Dự đoán Sạc, Dự đoán Chạy
        # Để so sánh công bằng (Fair Comparison)
        fair_comp_results = [r for r in final_results if r[3] > 0 and r[4] > 0 and r[5] > 0]
        
        if len(fair_comp_results) > 0:
            true_vals = [r[3] for r in fair_comp_results]
            pred_chg_vals = [r[4] for r in fair_comp_results]
            pred_drv_vals = [r[5] for r in fair_comp_results]
            pred_ens_vals = [r[6] for r in fair_comp_results]
            
            rmse_chg = np.sqrt(mean_squared_error(true_vals, pred_chg_vals))
            rmse_drv = np.sqrt(mean_squared_error(true_vals, pred_drv_vals))
            rmse_ens = np.sqrt(mean_squared_error(true_vals, pred_ens_vals))
            
            print(f">>> FAIR COMPARISON ON {len(fair_comp_results)} CARS:")
            print(f"    - Charging Only RMSE : {rmse_chg:.4f}")
            print(f"    - Driving Only RMSE  : {rmse_drv:.4f}")
            print(f"    - Ensemble RMSE      : {rmse_ens:.4f}\n")
            
            # --- VẼ BIỂU ĐỒ SO SÁNH RMSE ---
            plt.figure(figsize=(9, 6))
            labels = ['Charging Only', 'Driving Only', 'NN Ensemble']
            rmse_values = [rmse_chg, rmse_drv, rmse_ens]
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c'] # Xanh, Cam, Xanh lá
            
            bars = plt.bar(labels, rmse_values, color=colors, width=0.5)
            plt.ylabel('RMSE (Thấp hơn là tốt hơn)')
            plt.title('So sánh RMSE: XGBoost Đơn lẻ vs Neural Network Ensemble')
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            
            # Hiển thị text giá trị trên đầu mỗi cột
            for bar in bars:
                yval = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2, yval + (yval * 0.01), 
                         f'{yval:.4f}', ha='center', va='bottom', fontweight='bold')
            
            # Lưu biểu đồ vào RAM rồi ghi lên HDFS
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close()
            
            # Đảm bảo thư mục HDFS tồn tại
            try: 
                client.status(HDFS_IMAGE_DIR)
            except: 
                client.makedirs(HDFS_IMAGE_DIR)
                
            chart_hdfs_path = f"{HDFS_IMAGE_DIR}/inference_rmse_comparison.png"
            client.write(chart_hdfs_path, buf, overwrite=True)
            print(f"✓ Đã lưu biểu đồ so sánh RMSE lên HDFS tại: {chart_hdfs_path}")

        # Tính toán thêm RMSE tổng thể (bao gồm cả những xe chỉ có sạc hoặc chỉ có chạy)
        all_valid_results = [r for r in final_results if r[3] > 0]
        if len(all_valid_results) > 0:
            true_all = [r[3] for r in all_valid_results]
            pred_all = [r[6] for r in all_valid_results]
            rmse_all = np.sqrt(mean_squared_error(true_all, pred_all))
            print(f">>> OVERALL INFERENCE RMSE (All valid cars): {rmse_all:.4f}\n")
        
    header = ["car_id", "max_mileage_km", "prediction_method", "gt_capacity", "pred_xgboost_chg", "pred_xgboost_drv", "final_ensemble_pred", "error"]
    save_csv_hdfs(final_results, header, "inference_ensemble_result")
    print("Inference completed and saved!")

if __name__ == "__main__":
    run_inference_pipeline_nn()