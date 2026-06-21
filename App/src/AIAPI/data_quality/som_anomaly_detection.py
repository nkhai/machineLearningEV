"""
SOM (Self-Organizing Map) anomaly detection for battery_telemetry_v4.

Concept (adapted from the credit-card-fraud SOM):
  In the fraud example, each customer is one row, scaled to [0,1], mapped onto a
  10x10 SOM. Neurons with a high Mean Inter-neuron Distance (MID) on the distance
  map are outliers — the "frauds".

  Here, each (car_id, id_segment) driving/charging session is summarised into one
  feature vector. Sessions that land on high-MID neurons are flagged as anomalies
  (possible sensor faults, degraded cells, or abnormal operation).

Usage (from repo root, with .venv active):
    python App/src/AIAPI/data_quality/som_anomaly_detection.py

Outputs:
  App/dataset/som_results/som_anomaly_ranking.csv     — segments sorted by score
  src/AIAPI/docs/images/som_01_distance_map.png       — U-matrix + winners
  src/AIAPI/docs/images/som_02_score_distribution.png — anomaly score histogram
  src/AIAPI/docs/images/som_03_top_cases.png          — top-15 anomaly cases
  src/AIAPI/docs/images/som_04_feature_compare.png    — anomaly vs normal features
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from minisom import MiniSom

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────
HERE       = Path(__file__).resolve().parent
APP_ROOT   = HERE.parents[2]                       # .../App
TELEMETRY  = APP_ROOT / "dataset" / "battery_telemetry_v4"
RESULT_DIR = APP_ROOT / "dataset" / "som_results"
IMAGES_DIR = APP_ROOT / "src" / "AIAPI" / "docs" / "images"
RESULT_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

# Telemetry signals summarised per segment
SIGNALS = [
    "volt_V", "current_A", "soc_pct", "avg_speed_kmh", "motor_rpm",
    "min_single_volt_V", "max_single_volt_V", "min_temp_C", "max_temp_C",
    "accelerator_pedal_pct", "brake_pedal_pct", "regenerative_braking_Ah",
    "actual_max_capacity_Ah",
]

SEED = 42
np.random.seed(SEED)


# ─────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    files = sorted(TELEMETRY.rglob("*.csv"))
    print(f"Loading {len(files)} telemetry CSVs ...")
    df = pd.concat([pd.read_csv(f, low_memory=False) for f in files],
                   ignore_index=True)
    print(f"Combined shape: {df.shape}")
    return df


def build_segment_features(df: pd.DataFrame) -> pd.DataFrame:
    """One feature vector per (car_id, id_segment): mean + std of each signal."""
    grp = df.groupby(["car_id", "id_segment"])
    agg = grp[SIGNALS].agg(["mean", "std"]).fillna(0.0)
    agg.columns = [f"{c}_{s}" for c, s in agg.columns]
    # context columns
    agg["charger_connected"] = grp["charger_connected"].first()
    agg["n_rows"] = grp.size()
    agg = agg.reset_index()
    print(f"Built {len(agg)} segment feature vectors ({len(SIGNALS)*2} signals)")
    return agg


def train_som(X: np.ndarray):
    n = X.shape[0]
    # rule of thumb: grid side ~ sqrt(5*sqrt(n))
    side = max(8, int(np.ceil(np.sqrt(5 * np.sqrt(n)))))
    som = MiniSom(x=side, y=side, input_len=X.shape[1],
                  sigma=1.0, learning_rate=0.5, random_seed=SEED)
    som.random_weights_init(X)
    som.train_random(data=X, num_iteration=2000)
    print(f"Trained SOM {side}x{side} on {n} samples, {X.shape[1]} features")
    return som, side


# ─────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────
def chart_distance_map(som, X, labels, side, out):
    dmap = som.distance_map().T
    fig, ax = plt.subplots(figsize=(9, 8))
    pc = ax.pcolor(dmap, cmap="bone_r")
    fig.colorbar(pc, ax=ax, label="Mean Inter-neuron Distance (MID)")

    markers = ["o", "s"]      # o = driving, s = charging
    colors = ["#1f77b4", "#ff7f0e"]
    for i, x in enumerate(X):
        w = som.winner(x)
        m = int(labels[i])
        ax.plot(w[0] + 0.5, w[1] + 0.5, markers[m],
                markeredgecolor=colors[m], markerfacecolor="None",
                markersize=7, markeredgewidth=1.2, alpha=0.6)
    ax.set_title("SOM U-Matrix — bright = anomalous neurons\n"
                 "(o = driving, s = charging session)", fontweight="bold")
    ax.set_xlim(0, side); ax.set_ylim(0, side)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print("saved", out.name)


def chart_score_distribution(scores, threshold, out):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(scores, bins=50, color="#1f77b4", alpha=0.8)
    ax.axvline(threshold, color="#d62728", linestyle="--", linewidth=2,
               label=f"anomaly threshold (p95 = {threshold:.3f})")
    n_anom = int((scores >= threshold).sum())
    ax.set_xlabel("Anomaly score (MID of winning neuron)")
    ax.set_ylabel("Number of segments")
    ax.set_title(f"Anomaly Score Distribution — {n_anom} flagged of {len(scores)}",
                 fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print("saved", out.name)


def chart_top_cases(ranking, out, top=15):
    top_df = ranking.head(top).iloc[::-1]
    labels = top_df["car_id"] + " · " + top_df["id_segment"].astype(str)
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = ["#d62728" if s >= ranking["anomaly_score"].quantile(0.99)
              else "#ff7f0e" for s in top_df["anomaly_score"]]
    ax.barh(range(len(top_df)), top_df["anomaly_score"], color=colors)
    ax.set_yticks(range(len(top_df)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Anomaly score (MID)")
    ax.set_title(f"Top {top} Anomaly Cases (sorted)", fontweight="bold")
    for i, s in enumerate(top_df["anomaly_score"]):
        ax.text(s, i, f" {s:.3f}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print("saved", out.name)


def chart_feature_compare(ranking, feat_cols, out):
    anom = ranking[ranking["is_anomaly"]]
    norm = ranking[~ranking["is_anomaly"]]
    means_a = anom[feat_cols].mean()
    means_n = norm[feat_cols].mean()
    # normalise each feature to its overall mean for comparison
    base = ranking[feat_cols].mean().replace(0, 1)
    ra = (means_a / base)
    rn = (means_n / base)
    short = [c.replace("_mean", "") for c in feat_cols]
    y = np.arange(len(feat_cols))
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(y - 0.2, rn, height=0.4, color="#1f77b4", label="normal")
    ax.barh(y + 0.2, ra, height=0.4, color="#d62728", label="anomaly")
    ax.axvline(1.0, color="grey", linestyle="--")
    ax.set_yticks(y); ax.set_yticklabels(short, fontsize=9)
    ax.set_xlabel("Mean value relative to dataset average (1.0 = average)")
    ax.set_title("Anomaly vs Normal — feature profile", fontweight="bold")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)
    print("saved", out.name)


# ─────────────────────────────────────────────────────────────
def main():
    df = load_data()
    seg = build_segment_features(df)

    feat_cols = [c for c in seg.columns
                 if c not in ("car_id", "id_segment", "charger_connected", "n_rows")]
    X_raw = seg[feat_cols].values
    sc = MinMaxScaler()
    X = sc.fit_transform(X_raw)

    som, side = train_som(X)

    # anomaly score = MID of each sample's winning neuron
    dmap = som.distance_map()
    scores = np.array([dmap[som.winner(x)] for x in X])
    threshold = np.quantile(scores, 0.95)

    seg["anomaly_score"] = scores
    seg["is_anomaly"] = seg["anomaly_score"] >= threshold
    seg["quantization_error"] = np.array([np.linalg.norm(x - som.quantization([x])[0])
                                          for x in X])

    ranking = seg.sort_values("anomaly_score", ascending=False).reset_index(drop=True)
    ranking["rank"] = ranking.index + 1

    # save ranking CSV (readable feature means only)
    mean_cols = [c for c in feat_cols if c.endswith("_mean")]
    out_cols = (["rank", "car_id", "id_segment", "charger_connected", "n_rows",
                 "anomaly_score", "quantization_error", "is_anomaly"] + mean_cols)
    csv_path = RESULT_DIR / "som_anomaly_ranking.csv"
    ranking[out_cols].to_csv(csv_path, index=False)
    print(f"\nRanking saved → {csv_path}")

    n_anom = int(ranking["is_anomaly"].sum())
    print(f"Flagged {n_anom} anomalous segments (top 5%) of {len(ranking)}")
    print("\nTop 10 anomaly cases:")
    print(ranking[["rank", "car_id", "id_segment", "charger_connected",
                   "anomaly_score"]].head(10).to_string(index=False))

    # charts
    print("\nRendering charts ...")
    labels = seg["charger_connected"].values
    chart_distance_map(som, X, labels, side, IMAGES_DIR / "som_01_distance_map.png")
    chart_score_distribution(scores, threshold, IMAGES_DIR / "som_02_score_distribution.png")
    chart_top_cases(ranking, IMAGES_DIR / "som_03_top_cases.png")
    chart_feature_compare(ranking, mean_cols, IMAGES_DIR / "som_04_feature_compare.png")
    print("\nDone.")


if __name__ == "__main__":
    main()
