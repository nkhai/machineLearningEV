"""
Generate EDA preview images for the fg-data-profiling setup guide.

Usage (from App/ directory):
    python src/AIAPI/docs/generate_eda_preview_images.py

What it does:
  1. Loads all CSVs under App/dataset/battery_telemetry_v4/{car_id}/
  2. Loads the latest inference_ensemble_result_*.csv from App/dataset/output/
  3. Produces 4 preview PNGs saved to src/AIAPI/docs/images/:
        eda_01_dataset_overview.png   — files & rows per car + session split
        eda_02_feature_distributions.png — key feature histograms (CHG vs DRV)
        eda_03_capacity_by_car.png    — ground-truth capacity / SoH per car
        eda_04_prediction_error.png   — model error per car (latest results)
  These images are embedded in fg_data_profiling_guide.md.
"""

import glob
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────
HERE        = Path(__file__).resolve().parent
IMAGES_DIR  = HERE / "images"
IMAGES_DIR.mkdir(exist_ok=True)

# Walk up to App/ then into dataset/
APP_ROOT    = HERE.parents[2]          # .../App
DATASET     = APP_ROOT / "dataset"
TELEMETRY   = DATASET / "battery_telemetry_v4"
OUTPUT_DIR  = DATASET / "output"

NOMINAL_AH  = 210.0

plt.rcParams.update({
    "figure.dpi": 110,
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

BOSCH_RED   = "#E20015"
BLUE        = "#1f77b4"
GREEN       = "#2ca02c"
ORANGE      = "#ff7f0e"


# ─────────────────────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────────────────────
def load_all_telemetry() -> pd.DataFrame:
    frames = []
    files = sorted(TELEMETRY.rglob("*.csv"))
    print(f"Loading {len(files)} telemetry CSVs ...")
    for f in files:
        try:
            df = pd.read_csv(f, low_memory=False)
            df["source_file"] = f.name
            frames.append(df)
        except Exception as e:
            print(f"  [skip] {f.name}: {e}")
    out = pd.concat(frames, ignore_index=True)
    print(f"Combined telemetry shape: {out.shape}")
    return out


def load_latest_predictions() -> pd.DataFrame:
    files = sorted(OUTPUT_DIR.glob("inference_ensemble_result_*.csv"))
    if not files:
        return pd.DataFrame()
    latest = files[-1]
    print(f"Latest prediction file: {latest.name}")
    return pd.read_csv(latest)


# ─────────────────────────────────────────────────────────────
# CHART 1 — dataset overview
# ─────────────────────────────────────────────────────────────
def chart_overview(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # files + rows per car
    rows_per_car = df.groupby("car_id").size().sort_index()
    files_per_car = df.groupby("car_id")["source_file"].nunique().sort_index()

    cars = rows_per_car.index.tolist()
    x = np.arange(len(cars))

    ax = axes[0]
    ax.bar(x, rows_per_car.values, color=BLUE, label="rows")
    ax.set_xticks(x)
    ax.set_xticklabels(cars, rotation=45, ha="right")
    ax.set_ylabel("Telemetry rows", color=BLUE)
    ax.set_title("Rows & files per car")
    ax2 = ax.twinx()
    ax2.plot(x, files_per_car.values, color=BOSCH_RED, marker="o", label="files")
    ax2.set_ylabel("CSV files", color=BOSCH_RED)
    ax2.grid(False)

    # session split (charging vs driving)
    ax = axes[1]
    split = df.groupby(["car_id", "charger_connected"]).size().unstack(fill_value=0)
    split = split.rename(columns={0: "driving", 1: "charging"})
    drv = split.get("driving", pd.Series(0, index=split.index))
    chg = split.get("charging", pd.Series(0, index=split.index))
    ax.bar(x, drv.values, color=GREEN, label="driving")
    ax.bar(x, chg.values, bottom=drv.values, color=ORANGE, label="charging")
    ax.set_xticks(x)
    ax.set_xticklabels(cars, rotation=45, ha="right")
    ax.set_ylabel("Rows")
    ax.set_title("Session type split per car")
    ax.legend()

    fig.suptitle("Dataset Overview — battery_telemetry_v4", fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = IMAGES_DIR / "eda_01_dataset_overview.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out.name}")


# ─────────────────────────────────────────────────────────────
# CHART 2 — feature distributions CHG vs DRV
# ─────────────────────────────────────────────────────────────
def chart_distributions(df: pd.DataFrame):
    feats = ["volt_V", "current_A", "soc_pct", "max_temp_C",
             "avg_speed_kmh", "motor_rpm"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))

    chg = df[df["charger_connected"] == 1]
    drv = df[df["charger_connected"] == 0]

    for ax, col in zip(axes.ravel(), feats):
        if col not in df.columns:
            ax.set_visible(False)
            continue
        ax.hist(drv[col].dropna(), bins=40, alpha=0.6, color=GREEN, label="driving", density=True)
        ax.hist(chg[col].dropna(), bins=40, alpha=0.6, color=ORANGE, label="charging", density=True)
        ax.set_title(col)
        ax.legend(fontsize=8)

    fig.suptitle("Feature Distributions — Charging vs Driving", fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = IMAGES_DIR / "eda_02_feature_distributions.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out.name}")


# ─────────────────────────────────────────────────────────────
# CHART 3 — capacity / SoH per car
# ─────────────────────────────────────────────────────────────
def chart_capacity(df: pd.DataFrame):
    cap = df.groupby("car_id")["actual_max_capacity_Ah"].mean().sort_values()
    soh = cap / NOMINAL_AH * 100.0
    cars = cap.index.tolist()
    x = np.arange(len(cars))

    fig, ax = plt.subplots(figsize=(12, 5.5))
    colors = [BOSCH_RED if v < 85 else (ORANGE if v < 92 else GREEN) for v in soh.values]
    bars = ax.bar(x, cap.values, color=colors)
    ax.axhline(NOMINAL_AH, color="gray", linestyle="--", label=f"nominal {NOMINAL_AH:.0f} Ah")
    ax.set_xticks(x)
    ax.set_xticklabels(cars, rotation=45, ha="right")
    ax.set_ylabel("Mean actual_max_capacity (Ah)")
    ax.set_title("Battery Capacity & State-of-Health per Car", fontweight="bold")

    for xi, (c, s) in enumerate(zip(cap.values, soh.values)):
        ax.text(xi, c + 1, f"{s:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.legend()
    ax.set_ylim(0, NOMINAL_AH * 1.08)

    fig.tight_layout()
    out = IMAGES_DIR / "eda_03_capacity_by_car.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out.name}")


# ─────────────────────────────────────────────────────────────
# CHART 4 — prediction error per car
# ─────────────────────────────────────────────────────────────
def chart_prediction_error(pred: pd.DataFrame):
    if pred.empty:
        print("  [skip] no prediction file found")
        return
    pred = pred.sort_values("car_id")
    cars = pred["car_id"].tolist()
    x = np.arange(len(cars))
    width = 0.2

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    ax = axes[0]
    ax.bar(x - 1.5 * width, pred["gt_capacity"],          width, label="GT",        color="black")
    ax.bar(x - 0.5 * width, pred["pred_xgboost_chg"],      width, label="XGB chg",   color=ORANGE)
    ax.bar(x + 0.5 * width, pred["pred_xgboost_drv"],      width, label="XGB drv",   color=GREEN)
    ax.bar(x + 1.5 * width, pred["final_ensemble_pred"],   width, label="Ensemble",  color=BLUE)
    ax.set_xticks(x)
    ax.set_xticklabels(cars, rotation=45, ha="right")
    ax.set_ylabel("Capacity (Ah)")
    ax.set_title("Predicted vs Ground-Truth Capacity")
    ax.legend(fontsize=8)

    ax = axes[1]
    err = pred["error"].values
    colors = [GREEN if abs(e) < 5 else (ORANGE if abs(e) < 15 else BOSCH_RED) for e in err]
    ax.bar(x, err, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(cars, rotation=45, ha="right")
    ax.set_ylabel("Error (pred − GT, Ah)")
    ax.set_title("Ensemble Prediction Error per Car")
    for xi, e in enumerate(err):
        ax.text(xi, e + (0.5 if e >= 0 else -0.5), f"{e:.1f}",
                ha="center", va="bottom" if e >= 0 else "top", fontsize=8)

    fig.suptitle("Model Prediction Diagnostics (latest result)", fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = IMAGES_DIR / "eda_04_prediction_error.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {out.name}")


# ─────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Generating EDA preview images")
    print("=" * 60)
    df = load_all_telemetry()
    pred = load_latest_predictions()

    print("\nRendering charts ...")
    chart_overview(df)
    chart_distributions(df)
    chart_capacity(df)
    chart_prediction_error(pred)
    print("\nDone. Images in:", IMAGES_DIR)


if __name__ == "__main__":
    main()
