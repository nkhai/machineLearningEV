import os
import csv
import io
import tempfile
import pandas as pd
import pendulum
from collections import defaultdict
from hdfs import InsecureClient
import joblib
import xgboost as xgb


from ml_airflow.config.config import HDFS_URL, HDFS_USER, HDFS_OUTPUT_DIR
from ml_airflow.data_processing.snippetbuffer import GlobalSnippetBuffer

def load_data_universal(client, file_paths, mode='train'):
    global_buffer = GlobalSnippetBuffer(mode=mode)
    all_collected_samples = []
    
    file_paths = sorted(file_paths)
    print(f"[{mode.upper()}] Processing {len(file_paths)} files...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, hdfs_path in enumerate(file_paths):
            file_name = os.path.basename(hdfs_path)
            local_path = os.path.join(tmp_dir, f"{mode}_{file_name}")
            
            try:
                client.download(hdfs_path, local_path, overwrite=True)
                chunk_iter = pd.read_csv(local_path, chunksize=200_000)
                
                for chunk in chunk_iter:
                    new_samples = global_buffer.add_chunk(chunk, file_path=hdfs_path)
                    if new_samples:
                        all_collected_samples.extend(new_samples)
                
                os.remove(local_path)
                
                if (i + 1) % 10 == 0:
                    print(f" -> Processed {i + 1}/{len(file_paths)} files. Collected: {len(all_collected_samples)} samples.")

            except Exception as e:
                print(f"Error processing {hdfs_path}: {e}")
                if os.path.exists(local_path):
                    os.remove(local_path)
                continue
    
    print(f"[{mode.upper()}] Final Total Snippets: {len(all_collected_samples)}")

    stuck_items = global_buffer.rows
    if stuck_items:
        print(f"\n[{mode.upper()}] --- WARNING: DATA REMAINING IN BUFFER ---")
        stuck_by_car = defaultdict(list)
        for (car, seg), df_stuck in stuck_items.items():
            stuck_by_car[car].append((seg, len(df_stuck)))
            
        for car in sorted(stuck_by_car.keys()):
            print(f"Car: {car}")
            for seg, count in sorted(stuck_by_car[car]):
                print(f"  -> Segment: {seg} | Remaining rows: {count}")
        print("-" * 70 + "\n")
    else:
        print(f"[{mode.upper()}] Great! No remaining data in buffer.")

    return all_collected_samples

def get_hdfs_files_filtered(client, directory, min_date_str=None, limit=None):
    try:
        # Get a list of all items in the root directory
        all_items = client.list(directory)
        csv_paths = []

        for item in all_items:
            item_path = f"{directory}/{item}"
            
            # Check if the item is a CSV file or a subdirectory
            status = client.status(item_path)
            
            if status['type'] == 'DIRECTORY':
                # If it's a subdirectory (e.g., EV_011), traverse into it
                sub_items = client.list(item_path)
                for f in sub_items:
                    if f.endswith(".csv"):
                        csv_paths.append(f"{item_path}/{f}")
            elif item.endswith(".csv"):
                # If the CSV file is right in the root directory
                csv_paths.append(item_path)

        # After collecting all csv_paths, filter by date (if applicable)
        filtered_paths = []
        for path in csv_paths:
            if min_date_str is None:
                filtered_paths.append(path)
            else:
                # Extract the filename from the path to check the date
                f_name = os.path.basename(path)
                parts = f_name.split("_")
                if len(parts) >= 3:
                    date_part = parts[2]
                    if date_part.isdigit() and int(date_part) >= int(min_date_str):
                        filtered_paths.append(path)

        # Truncate if it exceeds the limit
        if limit and len(filtered_paths) > limit:
            filtered_paths = filtered_paths[:limit]

        return sorted(filtered_paths)
        
    except Exception as e:
        print(f"Error listing dir {directory}: {e}")
        return []

def filter_by_modality(dataset, is_charge):
    return [sample for sample in dataset if sample[1].get("charger_connected") == is_charge]

def save_csv_hdfs(data_rows, header, filename_prefix):
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(header)
    writer.writerows(data_rows)
    
    vn_now = pendulum.now("Asia/Ho_Chi_Minh")
    timestamp_str = vn_now.format("YYYYMMDD_HHmmss")
    filename = f"{filename_prefix}_{timestamp_str}.csv"
    hdfs_path = f"{HDFS_OUTPUT_DIR.rstrip('/')}/{filename}"
    
    try:
        client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=30)
        try: client.status(HDFS_OUTPUT_DIR)
        except: client.makedirs(HDFS_OUTPUT_DIR)
            
        client.write(hdfs_path, data=csv_buffer.getvalue().encode('utf-8'), overwrite=True)
        print(f"✓ Saved to HDFS: {hdfs_path}")
    except Exception as e:
        print(f"Failed save HDFS: {e}")

def save_artifacts_to_hdfs(client, hdfs_dir, suffix, model, scaler=None):
    """Save model and scaler directly from memory to HDFS (no local tmp files)"""
    
    # Kiểm tra và tạo thư mục trên HDFS nếu chưa tồn tại
    try: 
        client.status(hdfs_dir)
    except: 
        client.makedirs(hdfs_dir)

    # 1. XGBoost Model (Lưu trực tiếp từ RAM)
    if model is not None:
        # save_raw() xuất thẳng mô hình ra dạng byte, hỗ trợ định dạng json hoặc ubj
        model_bytes = model.save_raw(raw_format='json') 
        
        client.write(f"{hdfs_dir}/xgb_model_{suffix}.json", data=model_bytes, overwrite=True)
        print(f"✓ Successfully saved Model ({suffix}) to HDFS.")

    # 2. StandardScaler (Lưu qua bộ nhớ đệm BytesIO)
    if scaler is not None:
        scaler_buf = io.BytesIO()
        joblib.dump(scaler, scaler_buf) # Dump thẳng vào bộ nhớ đệm RAM
        scaler_buf.seek(0) # Kéo con trỏ về đầu luồng dữ liệu trước khi đọc
        
        client.write(f"{hdfs_dir}/scaler_{suffix}.joblib", data=scaler_buf, overwrite=True)
        print(f"✓ Successfully saved Scaler ({suffix}) to HDFS.")

    print(f"Completed saving artifacts for '{suffix}' to: {hdfs_dir}")

def print_dataset_logs(dataset, name="DATASET"):
    print(f"\n--- DATASET DETAILS: {name.upper()} ---")
    info_map = defaultdict(lambda: defaultdict(set))
    for _, meta in dataset:
        info_map[meta["car_id"]][meta["id_segment"]].update(meta["file_paths"])
        
    for car in sorted(info_map.keys()):
        print(f"Car: {car}")
        for seg in sorted(info_map[car].keys()):
            paths = ", ".join(sorted(info_map[car][seg]))
            print(f"  -> Segment: {seg} | Files: {paths}")
    print("-" * 50)

def load_artifacts_from_hdfs(client, hdfs_dir, suffix):
    """Download model and scaler from HDFS to local tmp and load into memory"""
    local_tmp_dir = "/tmp/battery_models_inference"
    os.makedirs(local_tmp_dir, exist_ok=True)
    
    model = None
    scaler = None
    
    # 1. Load XGBoost Model
    model_hdfs_path = f"{hdfs_dir}/xgb_model_{suffix}.json"
    model_local_path = os.path.join(local_tmp_dir, f"xgb_model_{suffix}.json")
    
    try:
        # Kiểm tra file model có tồn tại không
        if client.status(model_hdfs_path, strict=False):
            client.download(model_hdfs_path, model_local_path, overwrite=True)
            model = xgb.Booster()
            model.load_model(model_local_path)
            print(f"Successfully loaded Model ({suffix}) from HDFS.")
        else:
            print(f"No Model found for '{suffix}' on HDFS. Skipping model load.")
    except Exception as e:
        print(f"Error loading Model for '{suffix}': {e}")
        
    # 2. Load StandardScaler
    scaler_hdfs_path = f"{hdfs_dir}/scaler_{suffix}.joblib"
    scaler_local_path = os.path.join(local_tmp_dir, f"scaler_{suffix}.joblib")
    
    try:
        # Kiểm tra file scaler có tồn tại không
        if client.status(scaler_hdfs_path, strict=False):
            client.download(scaler_hdfs_path, scaler_local_path, overwrite=True)
            scaler = joblib.load(scaler_local_path)
            print(f"Successfully loaded Scaler ({suffix}) from HDFS.")
        else:
            print(f"No Scaler found for '{suffix}' on HDFS. Skipping scaler load.")
    except Exception as e:
        print(f"Error loading Scaler for '{suffix}': {e}")

    return model, scaler