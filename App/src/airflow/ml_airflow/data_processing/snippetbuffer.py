import numpy as np
import pandas as pd
from ml_airflow.config.config import WINDOW_SIZE, FEATURE_COLS_CHG, FEATURE_COLS_DRV

class GlobalSnippetBuffer:
    def __init__(self, mode='train'):
        self.rows = {} 
        self.metas = {}
        self.mode = mode 

    def add_chunk(self, df_chunk, file_path=""):
        finished_samples = []
        df_chunk = df_chunk.copy()

        # 1. TIỀN XỬ LÝ
        if "id_segment" not in df_chunk.columns:
            return []

        if "soc_pct" in df_chunk.columns:
            df_chunk["soc_pct"] = df_chunk["soc_pct"].clip(lower=0.0, upper=100.0)

        if "timestamp_s" in df_chunk.columns:
            df_chunk["step_idx"] = (df_chunk["timestamp_s"] // 10).astype(int)
        else:
            return []

        # Xử lý Capacity (Sử dụng actual_max_capacity_Ah)
        if "actual_max_capacity_Ah" not in df_chunk.columns:
            if self.mode == 'train':
                return [] 
            else:
                df_chunk["actual_max_capacity_Ah"] = -1.0
        else:
            if self.mode == 'train':
                df_chunk["actual_max_capacity_Ah"] = pd.to_numeric(df_chunk["actual_max_capacity_Ah"], errors='coerce')
                valid_mask = df_chunk["actual_max_capacity_Ah"].notna() & (df_chunk["actual_max_capacity_Ah"] != 0)
                df_chunk = df_chunk[valid_mask].copy()
            else:
                df_chunk["actual_max_capacity_Ah"] = pd.to_numeric(df_chunk["actual_max_capacity_Ah"], errors='coerce').fillna(-1.0)

        if df_chunk.empty:
            return []

        # 2. NHÓM DỮ LIỆU
        for key, group in df_chunk.groupby(["car_id", "id_segment"]):
            if key not in self.metas:
                first_row = group.iloc[0]
                self.metas[key] = {
                    "car_id": first_row["car_id"],
                    "id_segment": first_row["id_segment"],
                    "label": int(first_row.get("label", -1)),
                    "actual_max_capacity_Ah": float(first_row["actual_max_capacity_Ah"]),
                    "mileage_km": float(first_row.get("mileage_km", 0.0)),
                    "charger_connected": int(first_row.get("charger_connected", 1)),
                    "file_paths": {file_path} if file_path else set() 
                }
            else:
                if file_path:
                    self.metas[key]["file_paths"].add(file_path)

            if key in self.rows:
                combined_df = pd.concat([self.rows[key], group], ignore_index=True)
            else:
                combined_df = group

            total_rows = len(combined_df)
            num_windows = total_rows // WINDOW_SIZE
            
            # ---> XÁC ĐỊNH FEATURE_COLS DỰA VÀO TRẠNG THÁI SẠC <---
            is_charging = self.metas[key]["charger_connected"] == 1
            current_feature_cols = FEATURE_COLS_CHG if is_charging else FEATURE_COLS_DRV
            
            for w in range(num_windows):
                start_idx = w * WINDOW_SIZE
                end_idx = start_idx + WINDOW_SIZE
                window_df = combined_df.iloc[start_idx:end_idx]
                
                min_step = window_df["step_idx"].min()
                max_step = window_df["step_idx"].max()
                unique_steps = window_df["step_idx"].nunique()

                if (max_step - min_step == 127) and (unique_steps == 128):
                    # Trích xuất dữ liệu dựa trên danh sách cột đã chọn
                    # Cần đảm bảo các cột tồn tại trong DataFrame, nếu thiếu điền 0
                    for col in current_feature_cols:
                        if col not in window_df.columns:
                            window_df[col] = 0.0
                            
                    values = window_df.sort_values("step_idx")[current_feature_cols].fillna(0).values.astype(np.float32)
                    meta_copy = self.metas[key].copy()
                    meta_copy["file_paths"] = set(self.metas[key]["file_paths"]) 
                    finished_samples.append((values, meta_copy))
                        
            remainder = total_rows % WINDOW_SIZE
            if remainder > 0:
                self.rows[key] = combined_df.iloc[-remainder:]
            else:
                if key in self.rows:
                    del self.rows[key]

        return finished_samples