import numpy as np
import pandas as pd
from core.config import WINDOW_SIZE, FEATURE_COLS_CHG, FEATURE_COLS_DRV


class GlobalSnippetBuffer:
    def __init__(self, mode='train', pad_short_windows=False):
        self.rows = {}
        self.metas = {}
        self.mode = mode
        self.pad_short_windows = pad_short_windows

    def _emit_window(self, window_df, current_feature_cols, key):
        for col in current_feature_cols:
            if col not in window_df.columns:
                window_df[col] = 0.0

        window_sorted = window_df.sort_values("step_idx").reset_index(drop=True)
        values = window_sorted[current_feature_cols].fillna(0).values.astype(np.float32)
        meta_copy = self.metas[key].copy()
        meta_copy["file_paths"] = set(self.metas[key]["file_paths"])
        return (values, meta_copy, window_sorted)

    def add_chunk(self, df_chunk, file_path=""):
        finished_samples = []
        df_chunk = df_chunk.copy()

        if "id_segment" not in df_chunk.columns:
            return []

        if "soc_pct" in df_chunk.columns:
            df_chunk["soc_pct"] = df_chunk["soc_pct"].clip(lower=0.0, upper=100.0)

        if "timestamp_s" in df_chunk.columns:
            df_chunk["step_idx"] = (df_chunk["timestamp_s"] // 10).astype(int)
        else:
            return []

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
                    "car_model": str(first_row.get("car_model", "")),
                    "nominal_capacity_Ah": float(first_row.get("nominal_capacity_Ah", 0.0)),
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
                    finished_samples.append(self._emit_window(window_df.copy(), current_feature_cols, key))

            remainder = total_rows % WINDOW_SIZE
            if remainder > 0:
                self.rows[key] = combined_df.iloc[-remainder:]
            else:
                if key in self.rows:
                    del self.rows[key]

        return finished_samples

    def flush_remainder(self):
        """Flush remaining segments by padding to WINDOW_SIZE.

        Only pads when pad_short_windows=True (inference mode fallback).
        Returns list of (values, meta, window_sorted) for padded segments.
        """
        if not self.pad_short_windows or not self.rows:
            return []

        flushed = []
        for key, remain_df in list(self.rows.items()):
            meta = self.metas.get(key)
            if meta is None:
                continue

            is_charging = meta["charger_connected"] == 1
            current_feature_cols = FEATURE_COLS_CHG if is_charging else FEATURE_COLS_DRV

            remain_sorted = remain_df.sort_values("step_idx").reset_index(drop=True)
            actual_len = len(remain_sorted)
            pad_len = max(0, WINDOW_SIZE - actual_len)

            if pad_len > 0:
                pad_df = pd.DataFrame(
                    np.zeros((pad_len, len(current_feature_cols)), dtype=np.float32),
                    columns=current_feature_cols,
                )
                min_step = remain_sorted["step_idx"].min() if actual_len > 0 else 0
                pad_df["step_idx"] = min_step + actual_len + pd.RangeIndex(pad_len)
                pad_df["car_id"] = meta["car_id"]
                pad_df["id_segment"] = meta["id_segment"]
                remain_sorted = pd.concat([remain_sorted, pad_df], ignore_index=True)

            sample = self._emit_window(remain_sorted, current_feature_cols, key)
            sample[1]["_padded"] = pad_len
            flushed.append(sample)

        self.rows.clear()
        return flushed

    def flush_remainder(self):
        """Flush remaining segments by padding to WINDOW_SIZE.

        In inference mode, a segment with 50-127 rows can still be useful —
        just pad with zeros to reach WINDOW_SIZE.  Returns a list of
        (values, meta, window_sorted) samples from whatever is left in the
        buffer.
        """
        if self.mode != 'inference':
            return []

        flushed = []
        for key, remain_df in list(self.rows.items()):
            meta = self.metas.get(key)
            if meta is None:
                continue

            is_charging = meta["charger_connected"] == 1
            current_feature_cols = FEATURE_COLS_CHG if is_charging else FEATURE_COLS_DRV

            # Ensure feature columns exist
            for col in current_feature_cols:
                if col not in remain_df.columns:
                    remain_df[col] = 0.0

            remain_sorted = remain_df.sort_values("step_idx").reset_index(drop=True)
            actual_len = len(remain_sorted)

            # Pad with zeros to reach WINDOW_SIZE
            pad_len = max(0, WINDOW_SIZE - actual_len)
            if pad_len > 0:
                pad_df = pd.DataFrame(
                    np.zeros((pad_len, len(current_feature_cols)), dtype=np.float32),
                    columns=current_feature_cols,
                )
                # Fill step_idx so the padded rows get sequential step indices
                min_step = remain_sorted["step_idx"].min() if actual_len > 0 else 0
                pad_df["step_idx"] = min_step + actual_len + pd.RangeIndex(pad_len)
                # Carry over car_id / id_segment for the window_df to be consistent
                pad_df["car_id"] = meta["car_id"]
                pad_df["id_segment"] = meta["id_segment"]
                remain_sorted = pd.concat([remain_sorted, pad_df], ignore_index=True)

            # Extract feature matrix from the padded window
            values = remain_sorted[current_feature_cols].fillna(0).values.astype(np.float32)

            meta_copy = meta.copy()
            meta_copy["file_paths"] = set(meta["file_paths"])
            meta_copy["padded"] = pad_len  # caller can log this
            flushed.append((values, meta_copy, remain_sorted))

        self.rows.clear()
        return flushed
