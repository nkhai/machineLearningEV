import os
import io
import numpy as np
import xgboost as xgb
import torch
import torch.nn as nn
import torch.optim as optim
from collections import defaultdict
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import StandardScaler 
from hdfs import InsecureClient

# Import module nội bộ
from ml_airflow.config.config import HDFS_URL, HDFS_USER
from ml_airflow.data_processing.data_utils import get_hdfs_files_filtered, load_data_universal, filter_by_modality, save_artifacts_to_hdfs
from ml_airflow.data_processing.split_and_extract import split_train_test_by_car, extract_features_2d 
from ml_airflow.visualize.plot_curve import plot_learning_curve
from ml_airflow.models.nn import EnsembleNN # Import mô hình NN

RAW_DATA_DIR = "/raw_data/battery_telemetry_v2" 
HDFS_MODEL_DIR = "/models/battery_health_ensemble" 
HDFS_IMAGE_DIR = "/models/learning_curve"

def run_train_pipeline():
    client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=60)

    print("\n===== STEP 1: LOADING & SPLITTING DATA =====")
    all_train_files = get_hdfs_files_filtered(client, RAW_DATA_DIR)
    
    # BỘ LỌC TEST NHANH: Chỉ lấy EV_012, EV_013, EV_014
    target_train_evs = ['EV_012', 'EV_013', 'EV_014']
    train_files = [f for f in all_train_files if any(ev in f for ev in target_train_evs)]
    
    if not train_files: raise ValueError("No training files found for target EVs.")
    print(f"Loading {len(train_files)} files for training cars: {target_train_evs}")
    
    train_raw = load_data_universal(client, train_files, mode='train')
    train_set, val_set = split_train_test_by_car(train_raw)
    
    train_chg = filter_by_modality(train_set, is_charge=True)
    train_drv = filter_by_modality(train_set, is_charge=False)
    val_chg = filter_by_modality(val_set, is_charge=True)
    val_drv = filter_by_modality(val_set, is_charge=False)

    print("\n===== STEP 2A: TRAINING XGBOOST (Charging) =====")
    X_train_chg, y_train_chg = extract_features_2d(train_chg)
    X_val_chg, y_val_chg = extract_features_2d(val_chg)
    
    xgb_model_chg = None
    scaler_chg = None
    evals_result_chg = {} 
    X_val_chg_scaled = None # Khởi tạo biến để dùng cho Step 2C

    if len(X_train_chg) > 0:
        scaler_chg = StandardScaler()
        X_train_chg_scaled = scaler_chg.fit_transform(X_train_chg)
        
        dtrain_chg = xgb.DMatrix(X_train_chg_scaled, label=y_train_chg)
        xgb_params = {'booster': 'gbtree', 'learning_rate': 0.0001, 'objective': 'reg:squarederror', 'seed': 168, 'nthread': -1}
        
        evals = [(dtrain_chg, 'train')]
        if len(X_val_chg) > 0:
            X_val_chg_scaled = scaler_chg.transform(X_val_chg)
            dval_chg = xgb.DMatrix(X_val_chg_scaled, label=y_val_chg)
            evals.append((dval_chg, 'val'))
            
        xgb_model_chg = xgb.train(xgb_params, dtrain_chg, num_boost_round=300, evals=evals, 
                                  evals_result=evals_result_chg,
                                  early_stopping_rounds=50, verbose_eval=50)
        
        chg_hdfs_path=f"{HDFS_IMAGE_DIR}/learning_curve_chg.png"
        plot_learning_curve(client, evals_result_chg, "Charging Model", chg_hdfs_path)

    print("\n===== STEP 2B: TRAINING XGBOOST (Driving) =====")
    X_train_drv, y_train_drv = extract_features_2d(train_drv)
    X_val_drv, y_val_drv = extract_features_2d(val_drv)
    
    xgb_model_drv = None
    scaler_drv = None
    evals_result_drv = {} 
    X_val_drv_scaled = None # Khởi tạo biến để dùng cho Step 2C

    if len(X_train_drv) > 0:
        scaler_drv = StandardScaler()
        X_train_drv_scaled = scaler_drv.fit_transform(X_train_drv)
        
        dtrain_drv = xgb.DMatrix(X_train_drv_scaled, label=y_train_drv)
        xgb_params_drv = {'booster': 'gbtree','learning_rate': 0.0001, 'objective': 'reg:squarederror', 'seed': 168, 'nthread': -1}
        
        evals_drv = [(dtrain_drv, 'train')]
        if len(X_val_drv) > 0:
            X_val_drv_scaled = scaler_drv.transform(X_val_drv)
            dval_drv = xgb.DMatrix(X_val_drv_scaled, label=y_val_drv)
            evals_drv.append((dval_drv, 'val'))
            
        xgb_model_drv = xgb.train(xgb_params_drv, dtrain_drv, num_boost_round=300, evals=evals_drv, 
                                  evals_result=evals_result_drv, 
                                  early_stopping_rounds=50, verbose_eval=50)
        
        drv_hdfs_path=f"{HDFS_IMAGE_DIR}/learning_curve_drv.png"
        plot_learning_curve(client, evals_result_drv, "Driving Model", drv_hdfs_path)

    print("\n===== STEP 2C: TRAINING META-LEARNER (Ensemble NN) =====")
    val_preds_chg = defaultdict(list)
    val_preds_drv = defaultdict(list)
    val_true_cap = {}
    nn_model = None

    # Lấy dự đoán từ XGBoost trên tập Validation
    if xgb_model_chg is not None and X_val_chg_scaled is not None:
        preds_chg = xgb_model_chg.predict(xgb.DMatrix(X_val_chg_scaled))
        for p, (_, meta) in zip(preds_chg, val_chg):
            val_preds_chg[meta["car_id"]].append(p)
            val_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)

    if xgb_model_drv is not None and X_val_drv_scaled is not None:
        preds_drv = xgb_model_drv.predict(xgb.DMatrix(X_val_drv_scaled))
        for p, (_, meta) in zip(preds_drv, val_drv):
            val_preds_drv[meta["car_id"]].append(p)
            val_true_cap[meta["car_id"]] = meta.get("actual_max_capacity_Ah", -1)

    # Chuẩn bị Data Level Xe (Car-level)
    meta_X_chg = []
    meta_X_drv = []
    meta_y = []

    all_val_cars = set(list(val_preds_chg.keys()) + list(val_preds_drv.keys()))
    for car_id in all_val_cars:
        gt = val_true_cap.get(car_id, -1)
        if gt <= 0: continue
        
        p_chg = np.mean(val_preds_chg[car_id]) if car_id in val_preds_chg else None
        p_drv = np.mean(val_preds_drv[car_id]) if car_id in val_preds_drv else None
        
        # Mạng NN yêu cầu có đủ cả 2 input
        if p_chg is not None and p_drv is not None:
            meta_X_chg.append([p_chg])
            meta_X_drv.append([p_drv])
            meta_y.append([gt])

    if len(meta_y) > 0:
        print(f"Training EnsembleNN on {len(meta_y)} validation cars...")
        t_chg = torch.tensor(meta_X_chg, dtype=torch.float32)
        t_drv = torch.tensor(meta_X_drv, dtype=torch.float32)
        t_y = torch.tensor(meta_y, dtype=torch.float32)

        nn_model = EnsembleNN()
        criterion = nn.MSELoss()
        optimizer = optim.Adam(nn_model.parameters(), lr=0.01)

        epochs = 300
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = nn_model(t_chg, t_drv)
            loss = criterion(outputs, t_y)
            loss.backward()
            optimizer.step()
            
            if (epoch+1) % 50 == 0:
                print(f"  Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}")
        print("✓ Meta-Learner training completed.")
    else:
        print("Warning: Not enough validation cars with BOTH charging and driving data to train NN.")

    print("\n===== STEP 3: SAVING MODELS TO HDFS =====")
    # Tạo thư mục nếu chưa có
    try: client.status(HDFS_MODEL_DIR)
    except: client.makedirs(HDFS_MODEL_DIR)

    # Lưu Base Models (XGBoost + Scaler)
    if xgb_model_chg is not None:
        save_artifacts_to_hdfs(client, HDFS_MODEL_DIR, "chg", xgb_model_chg, scaler=scaler_chg)
        print("✓ Saved XGBoost Charging Model")
    if xgb_model_drv is not None:
        save_artifacts_to_hdfs(client, HDFS_MODEL_DIR, "drv", xgb_model_drv, scaler=scaler_drv)
        print("✓ Saved XGBoost Driving Model")
        
    # Lưu Meta-Learner (PyTorch weights .pth)
    if nn_model is not None:
        buffer = io.BytesIO()
        torch.save(nn_model.state_dict(), buffer)
        buffer.seek(0)
        pth_path = f"{HDFS_MODEL_DIR}/ensemble_nn.pth"
        client.write(pth_path, buffer, overwrite=True)
        print(f"✓ Saved Meta-Learner NN to {pth_path}")

if __name__ == "__main__":
    run_train_pipeline()