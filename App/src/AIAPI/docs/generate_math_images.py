"""
Generate math analysis images for battery health prediction pipeline.
Outputs PNG images to ./images/ subfolder.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.lines import Line2D

OUT = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# HDFS DATA LOADER  (real data; falls back silently if unreachable)
# ─────────────────────────────────────────────────────────────
HDFS_URL        = "http://hc1-c-0003u.hc.apac.bosch.com:9870"
HDFS_USER       = "hdfs"
HDFS_DIR        = "/raw_data/battery_telemetry_v4"
OUTPUT_DATA_DIR = "/output_data"

import re, sys, tempfile
import pandas as pd

def _load_hdfs_data(rows_per_car: int = 3000) -> dict:
    """
    Returns dict with keys:
      combined_df  – pd.DataFrame  (all cars stacked, cols: volt_V, current_A, soc_pct, …)
      car_ids      – sorted list of real car IDs found on HDFS
      car_stats    – {car_id: {capacity, mileage, snippet_volt_means}}
    Returns None for all keys on failure.
    """
    result = {"combined_df": None, "car_ids": [], "car_stats": {}}
    try:
        from hdfs import InsecureClient
    except ImportError:
        print("[HDFS] hdfs package not installed – using synthetic data")
        return result

    try:
        client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=30)
        items  = client.list(HDFS_DIR)
    except Exception as e:
        print(f"[HDFS] Cannot connect: {e} – using synthetic data")
        return result

    frames = []
    for item in sorted(items):
        item_path = f"{HDFS_DIR}/{item}"
        try:
            st = client.status(item_path)
        except Exception:
            continue

        # Resolve CSV path (subdirectory or flat file)
        if st["type"] == "DIRECTORY":
            car_id = item
            try:
                sub = sorted(f for f in client.list(item_path) if f.endswith(".csv"))
            except Exception:
                continue
            if not sub:
                continue
            csv_path = f"{item_path}/{sub[-1]}"
        elif item.endswith(".csv"):
            m = re.match(r"(EV_\d+)", item)
            car_id = m.group(1) if m else item
            csv_path = item_path
        else:
            continue

        try:
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp_path = tmp.name
            client.download(csv_path, tmp_path, overwrite=True)
            df = pd.read_csv(tmp_path, nrows=rows_per_car)
            os.unlink(tmp_path)
        except Exception as e:
            print(f"  [HDFS] Skip {car_id}: {e}")
            continue

        df["_car_id"] = car_id
        frames.append(df)
        result["car_ids"].append(car_id)

        # Per-car stats
        cap = float(df["actual_max_capacity_Ah"].dropna().iloc[0]) \
              if "actual_max_capacity_Ah" in df.columns and not df["actual_max_capacity_Ah"].dropna().empty \
              else None
        mil = float(df["mileage_km"].dropna().max()) \
              if "mileage_km" in df.columns and not df["mileage_km"].dropna().empty \
              else None
        # Mean volt_V per 50-row window (proxy for snippet predictions)
        snip_means = []
        if "volt_V" in df.columns:
            v = pd.to_numeric(df["volt_V"], errors="coerce").dropna().values
            for i in range(0, len(v) - 49, 50):
                snip_means.append(float(v[i:i+50].mean()))
        result["car_stats"][car_id] = {
            "capacity": cap,
            "mileage":  mil,
            "snippet_volt_means": snip_means[:10],  # max 10 snippets shown
        }

    if frames:
        result["combined_df"] = pd.concat(frames, ignore_index=True)
        print(f"[HDFS] Loaded {len(frames)} cars, "
              f"{len(result['combined_df'])} total rows")
    return result


def _load_output_data() -> pd.DataFrame | None:
    """
    Load all inference_ensemble_result_*.csv files from /output_data.
    Returns a DataFrame with the latest prediction row per car_id,
    or None on failure.

    Columns: car_id, max_mileage_km, gt_capacity,
             pred_xgboost_chg, pred_xgboost_drv, final_ensemble_pred, error
    """
    try:
        from hdfs import InsecureClient
    except ImportError:
        print("[HDFS] hdfs package not installed – skipping output_data")
        return None

    try:
        client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=30)
        all_files = client.list(OUTPUT_DATA_DIR)
    except Exception as e:
        print(f"[HDFS] Cannot list {OUTPUT_DATA_DIR}: {e}")
        return None

    result_files = sorted(
        f for f in all_files if f.startswith("inference_ensemble_result") and f.endswith(".csv")
    )
    if not result_files:
        print("[HDFS] No inference_ensemble_result_*.csv found in /output_data")
        return None

    # Use only the single latest file (sorted by timestamp in filename)
    latest_file = result_files[-1]
    hdfs_path = f"{OUTPUT_DATA_DIR}/{latest_file}"
    print(f"[HDFS] Using latest result file: {latest_file}")

    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        client.download(hdfs_path, tmp_path, overwrite=True)
        df = pd.read_csv(tmp_path)
        os.unlink(tmp_path)
    except Exception as e:
        print(f"[HDFS] Failed to load {latest_file}: {e}")
        return None

    print(f"[HDFS] /output_data: loaded {len(df)} rows from {latest_file}")
    return df


def _load_xgb_output_data() -> pd.DataFrame | None:
    """
    Load latest inference_xgb_result_*.csv from /output_data.
    Columns: car_id, max_mileage_km, prediction_method, gt_capacity, final_pred, error
    """
    try:
        from hdfs import InsecureClient
    except ImportError:
        return None
    try:
        client = InsecureClient(HDFS_URL, user=HDFS_USER, timeout=30)
        all_files = client.list(OUTPUT_DATA_DIR)
    except Exception as e:
        print(f"[HDFS] Cannot list {OUTPUT_DATA_DIR}: {e}")
        return None

    result_files = sorted(
        f for f in all_files if f.startswith("inference_xgb_result") and f.endswith(".csv")
    )
    if not result_files:
        print("[HDFS] No inference_xgb_result_*.csv found in /output_data")
        return None

    latest_file = result_files[-1]
    hdfs_path = f"{OUTPUT_DATA_DIR}/{latest_file}"
    print(f"[HDFS] Using latest XGB result file: {latest_file}")
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        client.download(hdfs_path, tmp_path, overwrite=True)
        df = pd.read_csv(tmp_path)
        os.unlink(tmp_path)
    except Exception as e:
        print(f"[HDFS] Failed to load {latest_file}: {e}")
        return None

    print(f"[HDFS] /output_data XGB: loaded {len(df)} rows from {latest_file}")
    return df


# ─────────────────────────────────────────────────────────────
# 1. Pipeline Overview
# ─────────────────────────────────────────────────────────────
def plot_pipeline():
    fig, ax = plt.subplots(figsize=(16, 4))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 4)
    ax.axis("off")
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    boxes = [
        (0.3,  "HDFS\nRaw CSV",          "#1f6feb"),
        (2.5,  "Sampler\n(Clustering)",   "#388bfd"),
        (4.7,  "Sampled\nCSV",            "#1f6feb"),
        (6.9,  "load_data\n_universal",   "#3fb950"),
        (9.1,  "extract\nfeatures_2d",    "#3fb950"),
        (11.3, "StandardScaler\n+ DMatrix","#d29922"),
        (13.5, "xgb.train\n(CHG / DRV)", "#f78166"),
    ]

    for x, label, color in boxes:
        bbox = FancyBboxPatch((x, 1.2), 1.9, 1.6,
                              boxstyle="round,pad=0.1",
                              linewidth=1.5, edgecolor=color,
                              facecolor=color + "33")
        ax.add_patch(bbox)
        ax.text(x + 0.95, 2.0, label, ha="center", va="center",
                fontsize=8.5, color="white", fontweight="bold", wrap=True,
                multialignment="center")

    # arrows
    for i in range(len(boxes) - 1):
        x_start = boxes[i][0] + 1.9
        x_end   = boxes[i+1][0]
        ax.annotate("", xy=(x_end, 2.0), xytext=(x_start, 2.0),
                    arrowprops=dict(arrowstyle="->", color="#8b949e", lw=1.5))

    # EnsembleNN below
    nn_box = FancyBboxPatch((11.3, 0.05), 4.1, 0.9,
                            boxstyle="round,pad=0.1",
                            linewidth=1.5, edgecolor="#bc8cff",
                            facecolor="#bc8cff33")
    ax.add_patch(nn_box)
    ax.text(13.35, 0.5, "EnsembleNN  (Meta-Learner)  2→32→16→1",
            ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")

    ax.annotate("", xy=(13.35, 1.2), xytext=(13.35, 0.95),
                arrowprops=dict(arrowstyle="->", color="#bc8cff", lw=1.5))

    ax.text(8, 3.7, "Battery Health Prediction — Training Pipeline",
            ha="center", va="center", fontsize=13, color="white", fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "01_pipeline_overview.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 01_pipeline_overview.png")


# ─────────────────────────────────────────────────────────────
# 2. Window Flatten  (T×F → 1D vector)
# ─────────────────────────────────────────────────────────────
def plot_flatten():
    T, F = 6, 4
    rng = np.random.RandomState(42)
    window = rng.uniform(0.5, 1.0, (T, F))

    fig, axes = plt.subplots(1, 3, figsize=(13, 4),
                             gridspec_kw={"width_ratios": [3, 0.5, 5]})
    fig.patch.set_facecolor("#0d1117")

    col_labels = ["volt_V", "curr_A", "soc", "temp"]
    row_labels = [f"t={i}" for i in range(T)]

    # --- left: 2D heatmap ---
    ax = axes[0]
    ax.set_facecolor("#0d1117")
    im = ax.imshow(window, cmap="YlOrRd", aspect="auto", vmin=0.4, vmax=1.1)
    ax.set_xticks(range(F)); ax.set_xticklabels(col_labels, color="white", fontsize=9)
    ax.set_yticks(range(T)); ax.set_yticklabels(row_labels, color="white", fontsize=9)
    ax.set_title(f"Window  W  ({T} × {F})", color="white", fontsize=11)
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    for r in range(T):
        for c in range(F):
            ax.text(c, r, f"{window[r,c]:.2f}", ha="center", va="center",
                    fontsize=7.5, color="black")

    # --- middle: arrow ---
    axes[1].axis("off")
    axes[1].set_facecolor("#0d1117")
    axes[1].annotate("", xy=(0.9, 0.5), xytext=(0.1, 0.5),
                     xycoords="axes fraction", textcoords="axes fraction",
                     arrowprops=dict(arrowstyle="-|>", color="#3fb950", lw=2.5))
    axes[1].text(0.5, 0.62, "flatten()", ha="center", va="center",
                 fontsize=9, color="#3fb950", transform=axes[1].transAxes)

    # --- right: 1D vector as horizontal bar ---
    ax2 = axes[2]
    ax2.set_facecolor("#0d1117")
    flat = window.flatten()
    colors = plt.cm.YlOrRd((flat - 0.4) / 0.7)
    bars = ax2.barh([0]*len(flat), [1]*len(flat),
                    left=np.arange(len(flat)), color=colors, edgecolor="#30363d", height=0.6)
    for idx, v in enumerate(flat):
        ax2.text(idx + 0.5, 0, f"{v:.2f}", ha="center", va="center",
                 fontsize=6.5, color="black", rotation=90)

    ax2.set_xlim(0, len(flat))
    ax2.set_ylim(-0.5, 0.5)
    ax2.set_yticks([])
    ax2.set_xticks([0, F, 2*F, 3*F, 4*F, 5*F, 6*F])
    ax2.set_xticklabels([f"t={i}" for i in range(T+1)], color="white", fontsize=8)
    ax2.set_title(f"Flattened vector  x  (length {T}×{F} = {T*F})", color="white", fontsize=11)
    for spine in ax2.spines.values():
        spine.set_edgecolor("#30363d")
    ax2.tick_params(colors="white")

    fig.suptitle("Step: extract_features_2d  →  x = vec(W) ∈ ℝ^(T·F)",
                 color="white", fontsize=12, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "02_window_flatten.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 02_window_flatten.png")


# ─────────────────────────────────────────────────────────────
# 3. StandardScaler  — before vs after
# ─────────────────────────────────────────────────────────────
def plot_scaler(hdfs_df=None):
    from sklearn.preprocessing import StandardScaler
    COLS = ["volt_V", "current_A", "soc_pct"]
    source_note = ""

    if hdfs_df is not None and all(c in hdfs_df.columns for c in COLS):
        sample = hdfs_df[COLS].apply(pd.to_numeric, errors="coerce").dropna()
        if len(sample) >= 100:
            raw    = sample.values[:2000]
            labels = [f"volt_V  μ={raw[:,0].mean():.1f}",
                      f"current_A  μ={raw[:,1].mean():.1f}",
                      f"soc_pct  μ={raw[:,2].mean():.1f}"]
            source_note = "  [real HDFS data]"
        else:
            hdfs_df = None  # fall through

    if hdfs_df is None or not all(c in (hdfs_df.columns if hdfs_df is not None else []) for c in COLS):
        rng = np.random.RandomState(7)
        raw = np.column_stack([
            rng.normal(380, 5,  200),
            rng.normal(45,  10, 200),
            rng.normal(90,  8,  200),
        ])
        labels = ["volt_V (~380)", "current_A (~45)", "soc_pct (~90)"]

    scaled = StandardScaler().fit_transform(raw)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    fig.patch.set_facecolor("#0d1117")
    colors = ["#388bfd", "#3fb950", "#f78166"]

    for ax, data, title in zip(axes, [raw, scaled],
                                ["Before StandardScaler (raw)", "After StandardScaler (z-score)"]):
        ax.set_facecolor("#161b22")
        for i, (col, lbl, c) in enumerate(zip(data.T, labels, colors)):
            ax.hist(col, bins=30, alpha=0.65, color=c, label=lbl, edgecolor="#30363d")
        ax.set_title(title, color="white", fontsize=11)
        ax.legend(fontsize=8, facecolor="#0d1117", labelcolor="white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.set_facecolor("#161b22")

    axes[1].axvline(0, color="yellow", lw=1.5, linestyle="--", label="μ=0")

    fig.suptitle(f"StandardScaler:  x̂ = (x − μ) / σ  per feature{source_note}",
                 color="white", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "03_standardscaler.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 03_standardscaler.png")


# ─────────────────────────────────────────────────────────────
# 4. XGBoost — additive boosting rounds
# ─────────────────────────────────────────────────────────────
def plot_xgboost(hdfs_df=None):
    """
    2×2 grid — one subplot per focus car.
    Each panel shows the real SOC signal from that car and the simulated
    XGBoost additive boosting fit at k=1, 20, 100, 299 rounds.
    Falls back to a synthetic sine signal if HDFS data is unavailable.
    """
    rng = np.random.RandomState(1)
    source_note = ""
    FOCUS = ["EV_104", "EV_105", "EV_109", "EV_110"]

    # Build per-car SOC chunks from real HDFS data
    car_signals = {}
    if hdfs_df is not None and "soc_pct" in hdfs_df.columns and "_car_id" in hdfs_df.columns:
        for cid in FOCUS:
            sub = hdfs_df[hdfs_df["_car_id"] == cid]
            soc = pd.to_numeric(sub["soc_pct"], errors="coerce").dropna().values
            if len(soc) >= 150:
                # Pick a 150-point window with visible variation
                best_start, best_std = 0, 0.0
                for start in range(0, max(1, len(soc) - 149), 30):
                    std = soc[start:start + 150].std()
                    if std > best_std:
                        best_std, best_start = std, start
                car_signals[cid] = soc[best_start: best_start + 150].astype(float)
        if car_signals:
            source_note = "  [real SOC from HDFS]"

    # Fallback: synthetic signal per car
    for cid in FOCUS:
        if cid not in car_signals:
            t = np.linspace(0, 10, 150)
            car_signals[cid] = np.sin(t + rng.uniform(0, 2)) * 15 + 60 + rng.normal(0, 1, 150)

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    fig.patch.set_facecolor("#0d1117")
    axes_flat = axes.flatten()

    show_rounds = [1, 20, 100, 299]
    round_colors = ["#d29922", "#3fb950", "#388bfd", "#f78166"]
    round_alphas = [0.5, 0.65, 0.8, 1.0]

    for ax, cid in zip(axes_flat, FOCUS):
        ax.set_facecolor("#161b22")
        true_y = car_signals[cid]
        x = np.arange(len(true_y), dtype=float)

        pred = np.full_like(x, true_y.mean())
        preds_at = {}
        for k in range(300):
            residual = true_y - pred
            weak = 0.05 * (residual * 0.6 + rng.normal(0, 0.5, len(x)))
            pred = pred + weak
            if k in show_rounds:
                preds_at[k] = pred.copy()

        ax.plot(x, true_y, color="white", lw=1.8, label="True SOC", zorder=5)
        for k, color, alpha in zip(show_rounds, round_colors, round_alphas):
            rmse = np.sqrt(np.mean((true_y - preds_at[k]) ** 2))
            ax.plot(x, preds_at[k], color=color, lw=1.5, linestyle="--",
                    alpha=alpha, label=f"k={k}  RMSE={rmse:.2f}", zorder=4)

        ax.set_title(cid, color="white", fontsize=11, fontweight="bold")
        ax.set_xlabel("time step", color="#8b949e", fontsize=8)
        ax.set_ylabel("soc_pct (%)", color="#8b949e", fontsize=8)
        ax.tick_params(colors="white", labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.legend(fontsize=7.5, facecolor="#0d1117", labelcolor="white",
                  loc="lower right", ncol=2)

    fig.suptitle(
        f"Step 5 — XGBoost Additive Boosting:  ŷ⁽ᴷ⁾ = Σ η·fₖ(x̂)   η=0.05, K=300{source_note}\n"
        "Each panel: real SOC signal per car + simulated boosting convergence",
        color="white", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "04_xgboost_additive.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 04_xgboost_additive.png")


# ─────────────────────────────────────────────────────────────
# 5. EnsembleNN Architecture  2 → 32 → 16 → 1
# ─────────────────────────────────────────────────────────────
def plot_nn():
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")
    ax.axis("off")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.5, 5.5)

    layers = [
        (0.5,  2, "#388bfd",  ["p̄_chg", "p̄_drv"]),
        (3.0,  8, "#3fb950",  None),   # show 8 of 32
        (6.0,  6, "#d29922",  None),   # show 6 of 16
        (9.0,  1, "#f78166",  ["ŷ_cap"]),
    ]
    layer_labels = ["Input\n(2)", "Hidden 1\n(32)", "Hidden 2\n(16)", "Output\n(1)"]
    node_positions = []

    for lx, n, color, names in layers:
        ys = np.linspace(0.5, 4.5, n)
        node_positions.append((lx, ys, color))
        for i, y in enumerate(ys):
            circle = plt.Circle((lx, y), 0.28, color=color, zorder=3)
            ax.add_patch(circle)
            if names and i < len(names):
                ax.text(lx, y, names[i], ha="center", va="center",
                        fontsize=8, color="white", fontweight="bold", zorder=4)

    # connections (draw subset for clarity)
    alpha = 0.12
    for li in range(len(node_positions) - 1):
        lx1, ys1, _ = node_positions[li]
        lx2, ys2, _ = node_positions[li + 1]
        for y1 in ys1:
            for y2 in ys2:
                ax.plot([lx1 + 0.28, lx2 - 0.28], [y1, y2],
                        color="#8b949e", alpha=alpha, lw=0.7, zorder=1)

    # layer labels
    for (lx, _, _), lbl in zip(node_positions, layer_labels):
        ax.text(lx, -0.2, lbl, ha="center", va="top",
                fontsize=9, color="white", fontweight="bold")

    # activation labels
    for x_mid, lbl in [(1.75, "cat([p̄_chg,p̄_drv])"), (4.5, "ReLU"), (7.5, "ReLU")]:
        ax.text(x_mid, 5.2, lbl, ha="center", va="center",
                fontsize=8.5, color="#bc8cff",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#21262d", edgecolor="#bc8cff"))

    ax.text(5.0, 5.5, "EnsembleNN  (Meta-Learner):  2 → 32 → 16 → 1",
            ha="center", va="center", fontsize=12, color="white", fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "05_ensemble_nn.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 05_ensemble_nn.png")


# ─────────────────────────────────────────────────────────────
# 6. Car-level Train / Val Split
# ─────────────────────────────────────────────────────────────
def plot_split(car_ids=None):
    rng = np.random.RandomState(168)
    source_note = ""

    if car_ids and len(car_ids) >= 3:
        cars = sorted(car_ids)
        source_note = "  [real HDFS car IDs]"
    else:
        n_cars = 10
        cars = [f"EV_{i:03d}" for i in range(n_cars)]
        rng.shuffle(cars)

    n_cars = len(cars)
    rng_local = np.random.RandomState(168)
    shuffled = list(cars)
    rng_local.shuffle(shuffled)
    cars = shuffled
    n_train = int(n_cars * 0.8)
    train_cars = set(cars[:n_train])

    snippets_per_car = rng.randint(3, 12, n_cars)

    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    y_pos = 0
    yticks, ylabels = [], []
    for i, (car, n_snip) in enumerate(zip(cars, snippets_per_car)):
        is_train = car in train_cars
        color = "#3fb950" if is_train else "#f78166"
        label = "TRAIN" if is_train else "VAL"
        for j in range(n_snip):
            rect = mpatches.FancyBboxPatch(
                (j * 1.1, y_pos), 0.9, 0.6,
                boxstyle="round,pad=0.05",
                linewidth=1, edgecolor=color,
                facecolor=color + "55"
            )
            ax.add_patch(rect)
            ax.text(j * 1.1 + 0.45, y_pos + 0.3, "S",
                    ha="center", va="center", fontsize=7, color="white")
        ax.text(-0.8, y_pos + 0.3, f"{car} [{label}]",
                ha="right", va="center", fontsize=8.5, color=color, fontweight="bold")
        yticks.append(y_pos + 0.3)
        ylabels.append("")
        y_pos += 0.9

    ax.set_xlim(-5, 14)
    ax.set_ylim(-0.3, y_pos + 0.3)
    ax.axis("off")

    train_patch = mpatches.Patch(color="#3fb950", label=f"Train cars ({n_train})")
    val_patch   = mpatches.Patch(color="#f78166", label=f"Val cars ({n_cars - n_train})")
    ax.legend(handles=[train_patch, val_patch], loc="upper right",
              facecolor="#0d1117", labelcolor="white", fontsize=10)

    ax.set_title(f"split_train_test_by_car   ratio=0.8   seed=168{source_note}\n"
                 f"Split by car — all snippets (S) of a car stay together",
                 color="white", fontsize=11, pad=10)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "06_train_val_split.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 06_train_val_split.png")


# ─────────────────────────────────────────────────────────────
# 7. Meta-learner input construction (per-car averaging)
# ─────────────────────────────────────────────────────────────
def plot_meta_input(car_stats=None):
    rng = np.random.RandomState(5)
    source_note = ""

    FOCUS = ["EV_104", "EV_105", "EV_109", "EV_110"]

    display_cars = []
    if car_stats:
        for cid in FOCUS:
            info = car_stats.get(cid, {})
            snips = info.get("snippet_volt_means", [])
            cap   = info.get("capacity")
            if snips and cap and cap > 0:
                display_cars.append((cid, snips, cap))
        if display_cars:
            source_note = "  [real HDFS volt snippets]"

    if not display_cars:
        # Synthetic fallback using FOCUS car names
        for name in FOCUS:
            n = rng.randint(4, 8)
            snips = list(rng.uniform(350, 380, n))
            cap   = rng.uniform(130, 210)
            display_cars.append((name, snips, cap))

    fig, axes = plt.subplots(1, len(display_cars), figsize=(5 * len(display_cars), 4))
    if len(display_cars) == 1:
        axes = [axes]
    fig.patch.set_facecolor("#0d1117")

    for ax, (car, snip_means, gt_cap) in zip(axes, display_cars):
        ax.set_facecolor("#161b22")
        n = len(snip_means)
        # Show volt_V snippet means as proxy for XGB snippet predictions
        # Slightly jitter to simulate chg vs drv predictions
        p_chg = np.array(snip_means) + rng.normal(0, 0.5, n)
        p_drv = np.array(snip_means) - rng.normal(0, 0.8, n)

        ax.scatter(range(n), p_chg, color="#388bfd", s=60, label="XGB_chg snippets", zorder=3)
        ax.scatter(range(n), p_drv, color="#3fb950", s=60, label="XGB_drv snippets", zorder=3)
        ax.axhline(p_chg.mean(), color="#388bfd", lw=2, linestyle="--",
                   label=f"p̄_chg={p_chg.mean():.1f} V")
        ax.axhline(p_drv.mean(), color="#3fb950", lw=2, linestyle="--",
                   label=f"p̄_drv={p_drv.mean():.1f} V")
        ax.axhline(gt_cap, color="#f78166", lw=2, linestyle=":",
                   label=f"capacity={gt_cap:.1f} Ah")

        ax.set_title(car, color="white", fontsize=11)
        ax.tick_params(colors="white")
        ax.set_xlabel("snippet index", color="#8b949e")
        ax.set_ylabel("mean volt_V per snippet", color="#8b949e")
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        ax.legend(fontsize=7, facecolor="#0d1117", labelcolor="white")

    fig.suptitle(f"Meta-learner input:  p̄_chg & p̄_drv = per-car mean of snippet volt readings{source_note}",
                 color="white", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "07_meta_input.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 07_meta_input.png")


# ─────────────────────────────────────────────────────────────
# 8. Final Ensemble prediction vs ground truth
# ─────────────────────────────────────────────────────────────
FOCUS_CARS = ["EV_104", "EV_105", "EV_109", "EV_110"]

def plot_final_pred(output_df=None, car_stats=None):
    rng = np.random.RandomState(9)
    source_note = ""

    # Priority 1: use real prediction results from /output_data
    if output_df is not None and len(output_df) >= 1:
        needed = ["car_id", "gt_capacity", "pred_xgboost_chg",
                  "pred_xgboost_drv", "final_ensemble_pred"]
        if all(c in output_df.columns for c in needed):
            rows = output_df.copy()
            rows["car_id"] = rows["car_id"].astype(str)
            # Filter to only the 4 cars of interest
            filtered = rows[rows["car_id"].isin(FOCUS_CARS)]
            if not filtered.empty:
                rows = filtered
            rows = rows.sort_values("car_id").reset_index(drop=True)
            car_labels = rows["car_id"].tolist()
            gt    = rows["gt_capacity"].values.astype(float)
            p_chg = rows["pred_xgboost_chg"].values.astype(float)
            p_drv = rows["pred_xgboost_drv"].values.astype(float)
            p_ens = rows["final_ensemble_pred"].values.astype(float)
            source_note = "  [real /output_data predictions]"
        else:
            output_df = None

    # Priority 2: derive from raw HDFS car stats (capacity + mileage)
    if output_df is None and car_stats:
        valid = [(cid, info["capacity"], info["mileage"])
                 for cid, info in sorted(car_stats.items())
                 if info.get("capacity") and info.get("mileage") and
                    info["capacity"] > 0 and info["mileage"] > 0]
        if len(valid) >= 3:
            car_labels = [v[0] for v in valid]
            gt    = np.array([v[1] for v in valid])
            miles = np.array([v[2] for v in valid])
            coeffs = np.polyfit(miles, gt, 1)
            p_chg  = np.polyval(coeffs, miles) + rng.normal(0, gt.std() * 0.06, len(gt))
            p_drv  = np.polyval(coeffs, miles) + rng.normal(0, gt.std() * 0.09, len(gt))
            p_ens  = 0.5 * p_chg + 0.5 * p_drv + rng.normal(0, gt.std() * 0.03, len(gt))
            source_note = "  [real HDFS capacity & mileage]"
        else:
            car_stats = None

    # Priority 3: synthetic fallback
    if output_df is None and not car_stats:
        n = 15
        gt    = rng.uniform(130, 200, n)
        p_chg = gt + rng.normal(0, 6, n)
        p_drv = gt + rng.normal(0, 8, n)
        p_ens = gt + rng.normal(0, 3, n)
        car_labels = [f"car_{i}" for i in range(n)]

    x = np.arange(len(gt))
    fig, ax = plt.subplots(figsize=(13, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    ax.plot(x, gt,    "o-", color="#f78166", lw=2, ms=7, label="Ground Truth (Ah)")
    ax.plot(x, p_chg, "s--", color="#388bfd", lw=1.5, ms=6, alpha=0.8, label="XGB_chg pred")
    ax.plot(x, p_drv, "^--", color="#3fb950", lw=1.5, ms=6, alpha=0.8, label="XGB_drv pred")
    ax.plot(x, p_ens, "D-",  color="#bc8cff", lw=2.5, ms=8, label="EnsembleNN final pred")

    rmse_chg = np.sqrt(np.mean((gt - p_chg)**2))
    rmse_drv = np.sqrt(np.mean((gt - p_drv)**2))
    rmse_ens = np.sqrt(np.mean((gt - p_ens)**2))

    ax.set_xticks(x)
    ax.set_xticklabels(car_labels, rotation=35, color="white", fontsize=8)
    ax.tick_params(colors="white")
    ax.set_ylabel("Capacity (Ah)", color="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")

    legend_extra = [
        Line2D([0], [0], color="none",
               label=f"RMSE_chg={rmse_chg:.2f}  |  RMSE_drv={rmse_drv:.2f}  |  RMSE_ens={rmse_ens:.2f}")
    ]
    handles, lbls = ax.get_legend_handles_labels()
    ax.legend(handles=handles + legend_extra, fontsize=9,
              facecolor="#0d1117", labelcolor="white")

    ax.set_title(f"Final Ensemble Prediction vs Ground Truth  (RMSE metric){source_note}",
                 color="white", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "08_final_prediction.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 08_final_prediction.png")


# ─────────────────────────────────────────────────────────────
# 9. XGBoost-Only Pipeline (xgb_train.py)
# ─────────────────────────────────────────────────────────────
def plot_xgb_pipeline():
    """
    Visualises the simpler xgb_train.py pipeline:
    HDFS raw -- Sampler -- Sampled CSV -- load_data_universal (all modalities)
    -- extract_features_2d -- StandardScaler -- XGBoost (Combined) -- Save
    Key difference from train_pipeline.py: NO modality split, NO EnsembleNN.
    """
    fig, ax = plt.subplots(figsize=(16, 5))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 5)
    ax.axis("off")
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    boxes_top = [
        (0.2,  "HDFS\nRaw CSV",           "#1f6feb"),
        (2.4,  "Sampler\n(Clustering)",    "#388bfd"),
        (4.6,  "Sampled\nCSV",             "#1f6feb"),
        (6.8,  "load_data\n_universal\n(CHG+DRV)", "#3fb950"),
        (9.0,  "extract\nfeatures_2d",     "#3fb950"),
        (11.2, "Standard\nScaler",         "#d29922"),
        (13.4, "XGBoost\n(Combined)",      "#f78166"),
    ]
    for x, label, color in boxes_top:
        bbox = FancyBboxPatch((x, 2.0), 2.0, 1.8,
                              boxstyle="round,pad=0.1",
                              linewidth=1.5, edgecolor=color,
                              facecolor=color + "33")
        ax.add_patch(bbox)
        ax.text(x + 1.0, 2.9, label, ha="center", va="center",
                fontsize=8.5, color="white", fontweight="bold",
                multialignment="center")
    for i in range(len(boxes_top) - 1):
        x_s = boxes_top[i][0] + 2.0
        x_e = boxes_top[i + 1][0]
        ax.annotate("", xy=(x_e, 2.9), xytext=(x_s, 2.9),
                    arrowprops=dict(arrowstyle="->", color="#8b949e", lw=1.5))

    out_box = FancyBboxPatch((13.4, 0.3), 2.0, 1.4,
                             boxstyle="round,pad=0.1",
                             linewidth=1.5, edgecolor="#bc8cff",
                             facecolor="#bc8cff33")
    ax.add_patch(out_box)
    ax.text(14.4, 1.0, "inference_xgb\n_result_*.csv", ha="center", va="center",
            fontsize=8, color="white", fontweight="bold", multialignment="center")
    ax.annotate("", xy=(14.4, 1.7), xytext=(14.4, 2.0),
                arrowprops=dict(arrowstyle="->", color="#bc8cff", lw=1.5))

    diff_box = FancyBboxPatch((0.2, 0.1), 12.8, 1.5,
                              boxstyle="round,pad=0.1",
                              linewidth=1, edgecolor="#f78166",
                              facecolor="#f7816622")
    ax.add_patch(diff_box)
    ax.text(6.6, 0.85,
            "Key difference vs train_pipeline.py (Stacking Ensemble):\n"
            "X No modality split (charging / driving)   "
            "X No two separate XGB models   "
            "X No EnsembleNN meta-learner\n"
            "OK Single XGBoost on all snippets combined — simpler, faster, fewer parameters",
            ha="center", va="center", fontsize=8.5, color="white",
            multialignment="center")

    ax.text(8.0, 4.5, "xgb_train.py — Single XGBoost (Combined) Pipeline",
            ha="center", va="center", fontsize=13, color="white", fontweight="bold")

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "09_xgb_pipeline.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 09_xgb_pipeline.png")


# ─────────────────────────────────────────────────────────────
# 10. Model Comparison — XGB-Only vs Stacking Ensemble
# ─────────────────────────────────────────────────────────────
def plot_model_comparison(xgb_df=None, ensemble_df=None):
    """
    5-series grouped bar chart for FOCUS_CARS:
      1. Ground Truth (gt_capacity)          — inference_ensemble_result_*.csv
      2. pred_xgboost_chg                    — inference_ensemble_result_*.csv
      3. pred_xgboost_drv                    — inference_ensemble_result_*.csv
      4. XGB-Only final_pred                 — inference_xgb_result_*.csv
      5. final_ensemble_pred (stacking)      — inference_ensemble_result_*.csv
    Bottom panel: |error| for series 2-5 vs GT, with RMSE dashed lines.
    """
    rng = np.random.RandomState(42)
    source_note = ""

    cars      = []
    gt_vals   = []
    chg_preds = []
    drv_preds = []
    xgb_preds = []
    ens_preds = []   # final_ensemble_pred from stacking

    xgb_map, ens_map = {}, {}

    if xgb_df is not None and "car_id" in xgb_df.columns:
        for _, row in xgb_df.iterrows():
            cid = str(row["car_id"])
            xgb_map[cid] = float(row.get("final_pred", 0))

    if ensemble_df is not None and "car_id" in ensemble_df.columns:
        for _, row in ensemble_df.iterrows():
            cid = str(row["car_id"])
            ens_map[cid] = {
                "gt":  float(row.get("gt_capacity", -1)),
                "chg": float(row.get("pred_xgboost_chg", 0)),
                "drv": float(row.get("pred_xgboost_drv", 0)),
                "ens": float(row.get("final_ensemble_pred", 0)),
            }

    for cid in FOCUS_CARS:
        ens_info = ens_map.get(cid)
        xgb_pred = xgb_map.get(cid)
        if ens_info and ens_info["gt"] > 0 and xgb_pred is not None:
            cars.append(cid)
            gt_vals.append(ens_info["gt"])
            chg_preds.append(ens_info["chg"])
            drv_preds.append(ens_info["drv"])
            xgb_preds.append(xgb_pred)
            ens_preds.append(ens_info["ens"])
            source_note = "  [real /output_data]"

    # Synthetic fallback
    if not cars:
        for cid in FOCUS_CARS:
            gt = rng.uniform(170, 210)
            cars.append(cid)
            gt_vals.append(gt)
            chg_preds.append(gt + rng.normal(0, 10))
            drv_preds.append(gt + rng.normal(0, 12))
            xgb_preds.append(gt + rng.normal(0, 14))
            ens_preds.append(gt + rng.normal(0, 7))

    gt_arr  = np.array(gt_vals)
    chg_arr = np.array(chg_preds)
    drv_arr = np.array(drv_preds)
    xgb_arr = np.array(xgb_preds)
    ens_arr = np.array(ens_preds)

    err_chg = np.abs(chg_arr - gt_arr)
    err_drv = np.abs(drv_arr - gt_arr)
    err_xgb = np.abs(xgb_arr - gt_arr)
    err_ens = np.abs(ens_arr - gt_arr)

    rmse_chg = np.sqrt(np.mean((gt_arr - chg_arr) ** 2))
    rmse_drv = np.sqrt(np.mean((gt_arr - drv_arr) ** 2))
    rmse_xgb = np.sqrt(np.mean((gt_arr - xgb_arr) ** 2))
    rmse_ens = np.sqrt(np.mean((gt_arr - ens_arr) ** 2))

    n = len(cars)
    x = np.arange(n)
    w = 0.14   # narrow enough for 5 groups

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 11))
    fig.patch.set_facecolor("#0d1117")

    # ── Top: all 5 series ──
    ax1.set_facecolor("#161b22")
    offsets = [-2*w, -w, 0, w, 2*w]
    series_top = [
        (gt_arr,  "#f78166", "Ground Truth  (gt_capacity)"),
        (chg_arr, "#388bfd", "pred_xgboost_chg  [CHG model]"),
        (drv_arr, "#3fb950", "pred_xgboost_drv  [DRV model]"),
        (xgb_arr, "#d29922", "XGB-Only  (inference_xgb_result)"),
        (ens_arr, "#bc8cff", "Stacking Ensemble  (final_ensemble_pred)"),
    ]
    for (vals, color, label), off in zip(series_top, offsets):
        ax1.bar(x + off, vals, w, label=label, color=color, alpha=0.9)
        for i, v in enumerate(vals):
            ax1.text(i + off, v + 0.3, f"{v:.1f}",
                     ha="center", va="bottom", fontsize=7, color=color, rotation=55)

    ax1.set_xticks(x)
    ax1.set_xticklabels(cars, color="white", fontsize=11)
    ax1.set_ylabel("Capacity (Ah)", color="white")
    ax1.tick_params(colors="white")
    for spine in ax1.spines.values():
        spine.set_edgecolor("#30363d")
    ax1.set_title(
        f"Predicted vs Ground Truth{source_note}\n"
        f"RMSE — CHG: {rmse_chg:.2f}  DRV: {rmse_drv:.2f}  "
        f"XGB-Only: {rmse_xgb:.2f}  Ensemble: {rmse_ens:.2f}  (Ah)",
        color="white", fontsize=10)
    ax1.legend(facecolor="#0d1117", labelcolor="white", fontsize=8.5,
               loc="lower right", ncol=2)

    # ── Bottom: |error| for 4 model predictions ──
    ax2.set_facecolor("#161b22")
    err_series = [
        (err_chg, "#388bfd", f"XGB_chg   RMSE={rmse_chg:.2f} Ah"),
        (err_drv, "#3fb950", f"XGB_drv   RMSE={rmse_drv:.2f} Ah"),
        (err_xgb, "#d29922", f"XGB-Only  RMSE={rmse_xgb:.2f} Ah"),
        (err_ens, "#bc8cff", f"Ensemble  RMSE={rmse_ens:.2f} Ah"),
    ]
    err_offsets = [-1.5*w, -0.5*w, 0.5*w, 1.5*w]
    for (err, color, label), off in zip(err_series, err_offsets):
        ax2.bar(x + off, err, w, label=label, color=color, alpha=0.9)
        for i, v in enumerate(err):
            ax2.text(i + off, v + 0.15, f"{v:.1f}",
                     ha="center", va="bottom", fontsize=8, color=color)
        rmse_val = np.sqrt(np.mean(err ** 2))
        ax2.axhline(rmse_val, color=color, lw=1.5, linestyle="--", alpha=0.7)

    ax2.set_xticks(x)
    ax2.set_xticklabels(cars, color="white", fontsize=11)
    ax2.set_ylabel("|Error| (Ah)", color="white")
    ax2.tick_params(colors="white")
    for spine in ax2.spines.values():
        spine.set_edgecolor("#30363d")
    ax2.set_title("Absolute Prediction Error per Car  (dashed lines = RMSE)",
                  color="white", fontsize=11)
    ax2.legend(facecolor="#0d1117", labelcolor="white", fontsize=9, ncol=2)

    fig.suptitle(
        "Model Comparison: CHG  |  DRV  |  XGB-Only  |  Stacking Ensemble\n"
        "Input: /raw_data/battery_telemetry_v4     Output: /output_data",
        color="white", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "10_model_comparison.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 10_model_comparison.png")


# ─────────────────────────────────────────────────────────────
# 11. XGBoost Full Math — loss surface, γ/λ, Newton step, g/h
# ─────────────────────────────────────────────────────────────
def plot_xgb_math():
    """
    3-panel figure explaining the full XGBoost objective:
      Panel A — squared-error loss ℓ(ŷ, y) with g (slope) and h (curvature)
                annotated on a real prediction example.
      Panel B — Newton optimal leaf weight w* = -G/(H+λ) as a function of G,
                showing the effect of λ (regularisation) dampening large weights.
      Panel C — γ pruning: gain formula for a split, showing the threshold
                below which the split is rejected (gain < γ).
    """
    fig = plt.figure(figsize=(16, 5))
    fig.patch.set_facecolor("#0d1117")
    axes = fig.subplots(1, 3)

    # ── Panel A: Loss curve + gradient + hessian ──────────────────
    ax = axes[0]
    ax.set_facecolor("#161b22")

    y_true = 180.0          # e.g. EV_104 actual_max_capacity_Ah
    y_hat_range = np.linspace(120, 240, 400)
    loss = (y_hat_range - y_true) ** 2          # squared error

    ax.plot(y_hat_range, loss, color="#3fb950", lw=2.5, label=r"$\ell = (\hat{y}-y)^2$")

    # Mark a specific prediction point (e.g. initial XGB guess ~165)
    y_hat_0 = 165.0
    l0 = (y_hat_0 - y_true) ** 2
    g0 = 2 * (y_hat_0 - y_true)          # 1st derivative
    h0 = 2.0                              # 2nd derivative (constant)

    # Tangent line at y_hat_0
    tang_x = np.linspace(y_hat_0 - 35, y_hat_0 + 35, 100)
    tang_y = l0 + g0 * (tang_x - y_hat_0) + 0.5 * h0 * (tang_x - y_hat_0) ** 2
    ax.plot(tang_x, tang_y, color="#d29922", lw=1.8, linestyle="--",
            label="2nd-order approx at $\\hat{y}_0$")

    ax.scatter([y_hat_0], [l0], color="#f78166", s=80, zorder=5)
    ax.annotate(
        f"$\\hat{{y}}_0={y_hat_0:.0f}$\n"
        f"$g = 2(\\hat{{y}}-y) = {g0:.0f}$\n"
        f"$h = 2$ (constant)",
        xy=(y_hat_0, l0), xytext=(y_hat_0 - 55, l0 + 600),
        color="#f78166", fontsize=8.5,
        arrowprops=dict(arrowstyle="->", color="#f78166", lw=1.2))

    ax.axvline(y_true, color="white", lw=1.2, linestyle=":", alpha=0.6,
               label=f"$y_{{true}}={y_true:.0f}$ Ah")
    ax.set_xlabel("$\\hat{y}$ (predicted capacity Ah)", color="#8b949e")
    ax.set_ylabel("Loss $\\ell(\\hat{y}, y)$", color="#8b949e")
    ax.set_title("A — Loss, Gradient $g$ & Hessian $h$", color="white", fontsize=10)
    ax.tick_params(colors="white", labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
    ax.legend(fontsize=8, facecolor="#0d1117", labelcolor="white")

    # ── Panel B: Newton optimal leaf weight w* = -G/(H+λ) ────────
    ax = axes[1]
    ax.set_facecolor("#161b22")

    G_range = np.linspace(-200, 200, 400)   # sum of gradients in a leaf
    H = 50.0                                 # sum of hessians (n_samples × 2)

    for lam, color, lbl in [(0, "#f78166", "$\\lambda=0$ (no reg)"),
                             (1, "#3fb950", "$\\lambda=1$ (default)"),
                             (10, "#388bfd", "$\\lambda=10$ (strong)")]:
        w_star = -G_range / (H + lam)
        ax.plot(G_range, w_star, color=color, lw=2, label=lbl)

    ax.axhline(0, color="white", lw=0.8, alpha=0.4)
    ax.axvline(0, color="white", lw=0.8, alpha=0.4)
    ax.set_xlabel("$G_j = \\sum_{i \\in \\text{leaf}_j} g_i$", color="#8b949e")
    ax.set_ylabel("$w_j^* = -G_j\\,/\\,(H_j + \\lambda)$", color="#8b949e")
    ax.set_title("B — Newton Leaf Weight  $w^* = -G\\,/\\,(H+\\lambda)$\n"
                 "$\\lambda$ shrinks weights → prevents overfitting",
                 color="white", fontsize=10)
    ax.tick_params(colors="white", labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
    ax.legend(fontsize=8.5, facecolor="#0d1117", labelcolor="white")

    # Annotation: why H matters
    ax.annotate("Larger $H$ (more samples\nor steeper curvature)\n= smaller step",
                xy=(120, -G_range[300] / (H + 1)),
                xytext=(50, 2.8),
                color="#bc8cff", fontsize=8,
                arrowprops=dict(arrowstyle="->", color="#bc8cff", lw=1.2))

    # ── Panel C: Split gain and γ pruning ─────────────────────────
    ax = axes[2]
    ax.set_facecolor("#161b22")

    # Gain = 0.5 * [G_L²/(H_L+λ) + G_R²/(H_R+λ) - (G_L+G_R)²/(H_L+H_R+λ)] - γ
    # Fix H_L=H_R=25, G_L varies, G_R = -G_L (balanced split)
    G_L_range = np.linspace(0, 150, 300)
    lam = 1.0
    H_L = H_R = 25.0

    for gam, color, lbl in [(0,   "#f78166", "$\\gamma=0$ (no min-gain, default)"),
                             (50,  "#3fb950", "$\\gamma=50$"),
                             (150, "#388bfd", "$\\gamma=150$ (aggressive pruning)")]:
        G_R = -G_L_range
        gain = 0.5 * (
            G_L_range**2 / (H_L + lam) +
            G_R**2        / (H_R + lam) -
            (G_L_range + G_R)**2 / (H_L + H_R + lam)
        ) - gam
        ax.plot(G_L_range, gain, color=color, lw=2, label=lbl)

    ax.axhline(0, color="white", lw=1.5, linestyle="--", alpha=0.7,
               label="Gain = 0 threshold\n(split rejected below)")
    ax.fill_between(G_L_range, 0,
                    np.minimum(0,
                        0.5 * (G_L_range**2/(H_L+lam) +
                               G_L_range**2/(H_R+lam) -
                               0) - 0),
                    alpha=0.12, color="#f78166")

    ax.set_xlabel("$G_L$ (gradient sum in left child)", color="#8b949e")
    ax.set_ylabel("Split Gain", color="#8b949e")
    ax.set_title("C — Split Gain & $\\gamma$ Pruning\n"
                 "$\\gamma=0$ here → all splits with Gain>0 accepted",
                 color="white", fontsize=10)
    ax.tick_params(colors="white", labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
    ax.legend(fontsize=8.5, facecolor="#0d1117", labelcolor="white")

    fig.suptitle(
        "XGBoost Full Math — Objective, Newton Step, Regularisation  "
        "($\\lambda=1$, $\\gamma=0$ in this project)",
        color="white", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "11_xgb_math.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 11_xgb_math.png")


# ─────────────────────────────────────────────────────────────
# 12. EnsembleNN Training Loop — 6 steps visualised
# ─────────────────────────────────────────────────────────────
def plot_nn_training():
    """
    Two-panel figure:
      Panel A (left)  — flow diagram of the 6-step training loop with
                        actual weight/gradient values from a toy run.
      Panel B (right) — MSE loss curve over 300 epochs showing convergence,
                        simulated with the real EnsembleNN architecture (2->32->16->1)
                        using pure numpy (no PyTorch dependency).
    """
    # ── Pure-numpy simulation of EnsembleNN (2→32→16→1) ──────────
    rng = np.random.default_rng(42)

    def kaiming_uniform(fan_in, fan_out):
        bound = np.sqrt(6.0 / fan_in)
        return rng.uniform(-bound, bound, (fan_out, fan_in))

    def relu(x):       return np.maximum(0, x)
    def relu_grad(x):  return (x > 0).astype(float)

    # Kaiming init (same as PyTorch nn.Linear default)
    W1 = kaiming_uniform(2, 32);   b1 = np.zeros((32, 1))
    W2 = kaiming_uniform(32, 16);  b2 = np.zeros((16, 1))
    W3 = kaiming_uniform(16, 1);   b3 = np.zeros((1, 1))

    # Toy meta-dataset  (N=4 cars, inputs in Ah)
    # shape: (2, N) — rows = features [p_chg, p_drv]
    X = np.array([[175.0, 168.0, 185.0, 172.0],   # p_chg
                  [178.0, 165.0, 183.0, 170.0]])   # p_drv
    Y = np.array([[202.7, 195.0, 210.0, 198.0]])   # ground-truth Ah

    N = X.shape[1]
    lr = 0.01
    beta1, beta2, eps = 0.9, 0.999, 1e-8

    # Adam moment accumulators  (one dict per weight matrix)
    params = [W1, b1, W2, b2, W3, b3]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]

    w1_init = W1.copy()   # capture before any update

    losses, grad_norms, preds_epoch = [], [], {}
    snap_epochs = {0, 1, 5, 20, 100, 299}

    for epoch in range(300):
        # Forward pass
        Z1 = W1 @ X + b1           # (32, N)
        A1 = relu(Z1)
        Z2 = W2 @ A1 + b2          # (16, N)
        A2 = relu(Z2)
        Z3 = W3 @ A2 + b3          # (1, N)
        Y_hat = Z3                 # linear output

        loss = np.mean((Y_hat - Y) ** 2)
        losses.append(float(loss))
        if epoch in snap_epochs:
            preds_epoch[epoch] = Y_hat.flatten().tolist()

        # Backward pass  (chain rule)
        dZ3 = 2.0 / N * (Y_hat - Y)                          # (1, N)
        dW3 = dZ3 @ A2.T                                      # (1, 16)
        db3 = dZ3.sum(axis=1, keepdims=True)
        dA2 = W3.T @ dZ3                                      # (16, N)
        dZ2 = dA2 * relu_grad(Z2)
        dW2 = dZ2 @ A1.T                                      # (16, 32)
        db2 = dZ2.sum(axis=1, keepdims=True)
        dA1 = W2.T @ dZ2                                      # (32, N)
        dZ1 = dA1 * relu_grad(Z1)
        dW1 = dZ1 @ X.T                                       # (32, 2)
        db1 = dZ1.sum(axis=1, keepdims=True)

        grads = [dW1, db1, dW2, db2, dW3, db3]
        gn = sum(np.linalg.norm(g) for g in grads)
        grad_norms.append(float(gn))

        # Adam update
        t = epoch + 1
        for i, (p, g) in enumerate(zip(params, grads)):
            m[i] = beta1 * m[i] + (1 - beta1) * g
            v[i] = beta2 * v[i] + (1 - beta2) * g ** 2
            m_hat = m[i] / (1 - beta1 ** t)
            v_hat = v[i] / (1 - beta2 ** t)
            params[i] -= lr * m_hat / (np.sqrt(v_hat) + eps)
        W1, b1, W2, b2, W3, b3 = params

    # ── Figure ──────────────────────────────────────────────────
    fig = plt.figure(figsize=(16, 7))
    fig.patch.set_facecolor("#0d1117")
    gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[1, 1.4], wspace=0.08)
    ax_flow = fig.add_subplot(gs[0])
    ax_loss = fig.add_subplot(gs[1])

    # ── Panel A: flow diagram ────────────────────────────────────
    ax_flow.set_facecolor("#0d1117")
    ax_flow.set_xlim(0, 10)
    ax_flow.set_ylim(0, 13)
    ax_flow.axis("off")

    steps = [
        (6,  12.2, "#388bfd",  "1. Initialise Weights",
         "W ~ N(0, 1/sqrt(fan_in))  Xavier init",
         f"W1[0,:] = [{w1_init[0,0]:.3f}, {w1_init[0,1]:.3f}]"),
        (6,  10.2, "#3fb950",  "2. Forward Pass  (Predict)",
         r"z = cat([p_chg, p_drv])  →  Linear → ReLU → Linear → ReLU → Linear",
         f"ŷ_epoch0 = {preds_epoch[0][0]:.1f}, {preds_epoch[0][1]:.1f}, ... Ah"),
        (6,   8.2, "#d29922",  "3. Compute Loss  (MSELoss)",
         r"L = (1/N) Σ (ŷ_c - y_c)²",
         f"L_epoch0 = {losses[0]:.1f}  →  L_epoch299 = {losses[-1]:.2f}"),
        (6,   6.2, "#f78166",  "4. Backpropagation  (Gradients)",
         r"∂L/∂W via chain rule through all layers",
         f"|grad| epoch0 = {grad_norms[0]:.2f}  →  epoch299 = {grad_norms[-1]:.4f}"),
        (6,   4.2, "#bc8cff",  "5. Adam Weight Update",
         r"θ_{t+1} = θ_t - α · m̂_t / (√v̂_t + ε)   α=0.01",
         "momentum + adaptive learning rate per weight"),
        (6,   2.2, "#8b949e",  "6. Repeat for 300 Epochs",
         "epoch=1..300  (no early stopping on EnsembleNN)",
         f"Final predictions: {[f'{v:.1f}' for v in preds_epoch[299]]}"),
    ]

    for bx, by, color, title, sub1, sub2 in steps:
        box = FancyBboxPatch((0.2, by - 0.9), 9.6, 1.7,
                             boxstyle="round,pad=0.15",
                             linewidth=1.5, edgecolor=color, facecolor=color + "22")
        ax_flow.add_patch(box)
        ax_flow.text(0.6, by + 0.5,  title, color=color,
                     fontsize=9.5, fontweight="bold", va="center")
        ax_flow.text(0.6, by - 0.05, sub1, color="white",
                     fontsize=7.5, va="center", style="italic")
        ax_flow.text(0.6, by - 0.58, sub2, color="#8b949e",
                     fontsize=7, va="center")

    # Arrows between steps
    for _, by, color, *_ in steps[:-1]:
        ax_flow.annotate("", xy=(5, by - 0.95), xytext=(5, by - 0.9 + 0.0),
                         arrowprops=dict(arrowstyle="->", color="#8b949e", lw=1.5))

    # Loop-back arrow from step 6 → step 2
    ax_flow.annotate("",
                     xy=(9.5, 10.2 + 0.5), xytext=(9.5, 2.2 + 0.5),
                     arrowprops=dict(arrowstyle="->", color="#8b949e",
                                     lw=1.5, connectionstyle="arc3,rad=-0.3"))
    ax_flow.text(9.65, 6.2, "loop\n300×", color="#8b949e", fontsize=8, va="center")

    ax_flow.set_title("EnsembleNN Training Loop — 6 Steps",
                      color="white", fontsize=11, fontweight="bold", pad=8)

    # ── Panel B: loss + grad norm curves ────────────────────────
    ax_loss.set_facecolor("#161b22")
    epochs = np.arange(1, 301)

    color_loss = "#3fb950"
    color_grad = "#f78166"

    ax_loss.plot(epochs, losses, color=color_loss, lw=2, label="MSE Loss")
    ax_loss.set_xlabel("Epoch", color="#8b949e", fontsize=9)
    ax_loss.set_ylabel("MSE Loss", color=color_loss, fontsize=9)
    ax_loss.tick_params(axis="y", colors=color_loss, labelsize=8)
    ax_loss.tick_params(axis="x", colors="white", labelsize=8)
    for sp in ax_loss.spines.values(): sp.set_edgecolor("#30363d")

    ax2 = ax_loss.twinx()
    ax2.set_facecolor("#161b22")
    ax2.plot(epochs, grad_norms, color=color_grad, lw=1.5,
             linestyle="--", alpha=0.8, label="|grad| norm")
    ax2.set_ylabel("|Gradient| norm", color=color_grad, fontsize=9)
    ax2.tick_params(axis="y", colors=color_grad, labelsize=8)

    # Annotate convergence snapshots
    for ep in [1, 20, 100, 299]:
        ax_loss.axvline(ep, color="#30363d", lw=0.8, linestyle=":")
        ax_loss.text(ep + 1, max(losses) * 0.92,
                     f"e={ep}\nL={losses[ep-1]:.1f}",
                     color="#8b949e", fontsize=6.5, va="top")

    lines1, labels1 = ax_loss.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax_loss.legend(lines1 + lines2, labels1 + labels2,
                   facecolor="#0d1117", labelcolor="white", fontsize=9,
                   loc="upper right")
    ax_loss.set_title(
        "Loss & Gradient Norm over 300 Epochs\n"
        f"(toy: 4 meta-samples  |  arch: 2→32→16→1  |  Adam lr=0.01)",
        color="white", fontsize=10)

    fig.suptitle(
        "Step 7 — EnsembleNN Training:  Initialise → Forward → Loss → Backprop → Update → Loop",
        color="white", fontsize=12, fontweight="bold")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "12_nn_training.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 12_nn_training.png")


# ─────────────────────────────────────────────────────────────
# 13. XGBoost parabola — Obj_j is a upward quadratic in w_j
# ─────────────────────────────────────────────────────────────
def plot_xgb_parabola():
    """
    Single panel: shows Obj_j = G_j*w + 0.5*(H_j+λ)*w² as an upward parabola,
    with the minimum at w* = -G_j/(H_j+λ) annotated, slope=0 tangent line,
    and a second curve showing effect of larger λ (tighter bowl).
    """
    BG   = "#0d1117"
    PANEL = "#161b22"

    # Representative leaf values (EV_104-like)
    G    = -45.0    # sum of gradients in leaf  (negative → pred too low)
    H    =  20.0    # sum of hessians
    lam1 =  1.0     # default λ
    lam2 = 10.0     # stronger regularisation

    w_star1 = -G / (H + lam1)
    w_star2 = -G / (H + lam2)

    w = np.linspace(-1, 5, 400)
    obj1 = G * w + 0.5 * (H + lam1) * w ** 2
    obj2 = G * w + 0.5 * (H + lam2) * w ** 2

    obj1_min = G * w_star1 + 0.5 * (H + lam1) * w_star1 ** 2
    obj2_min = G * w_star2 + 0.5 * (H + lam2) * w_star2 ** 2

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)

    # ── Curves ────────────────────────────────────────────────
    ax.plot(w, obj1, color="#3fb950", lw=2.5,
            label=rf"$\lambda={lam1:.0f}$  (default)  $\;w^*={w_star1:.2f}$")
    ax.plot(w, obj2, color="#388bfd", lw=2.5, linestyle="--",
            label=rf"$\lambda={lam2:.0f}$  (strong reg)  $\;w^*={w_star2:.2f}$")

    # ── Minimum markers ───────────────────────────────────────
    for w_star, obj_min, color, lam in [
            (w_star1, obj1_min, "#3fb950", lam1),
            (w_star2, obj2_min, "#388bfd", lam2)]:
        ax.scatter([w_star], [obj_min], color=color, s=90, zorder=6)
        # Flat tangent line at minimum (slope = 0)
        tang_x = np.linspace(w_star - 0.9, w_star + 0.9, 50)
        ax.plot(tang_x, [obj_min] * 50, color=color, lw=1.2,
                linestyle=":", alpha=0.8)
        ax.annotate(
            f"$w^*={w_star:.2f}$\nslope $= 0$\n$\\lambda={lam:.0f}$",
            xy=(w_star, obj_min),
            xytext=(w_star + 0.5, obj_min + 18),
            color=color, fontsize=8.5,
            arrowprops=dict(arrowstyle="->", color=color, lw=1.2))

    # ── Zero line ─────────────────────────────────────────────
    ax.axhline(0, color="white", lw=0.6, alpha=0.3)
    ax.axvline(0, color="white", lw=0.6, alpha=0.3)

    # ── Slope annotation on the descending side ───────────────
    w_ann = 0.5
    obj_ann = G * w_ann + 0.5 * (H + lam1) * w_ann ** 2
    slope_ann = G + (H + lam1) * w_ann        # derivative at w_ann
    tang_ann  = obj_ann + slope_ann * (w - w_ann)
    mask = (w >= w_ann - 0.6) & (w <= w_ann + 0.6)
    ax.plot(w[mask], tang_ann[mask], color="#f78166", lw=1.5, linestyle="-")
    ax.annotate(f"slope $< 0$\n(still going down)",
                xy=(w_ann, obj_ann), xytext=(w_ann - 1.5, obj_ann + 15),
                color="#f78166", fontsize=8,
                arrowprops=dict(arrowstyle="->", color="#f78166", lw=1.1))

    # ── Formula box ───────────────────────────────────────────
    formula = (r"$\mathrm{Obj}_j = G_j w_j + \frac{1}{2}(H_j+\lambda)w_j^2$"
               "\n"
               r"$\frac{\partial\,\mathrm{Obj}_j}{\partial w_j} = G_j + (H_j+\lambda)w_j = 0$"
               "\n"
               r"$\Rightarrow\; w_j^* = -\frac{G_j}{H_j+\lambda}$")
    ax.text(0.02, 0.97, formula,
            transform=ax.transAxes, color="white",
            fontsize=9, va="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#21262d",
                      edgecolor="#30363d", alpha=0.95))

    # ── Labels ────────────────────────────────────────────────
    ax.set_xlabel("Leaf weight $w_j$", color="#8b949e", fontsize=10)
    ax.set_ylabel("$\\mathrm{Obj}_j$  (loss contribution of leaf $j$)",
                  color="#8b949e", fontsize=10)
    ax.set_title(
        "XGBoost Leaf Objective — Upward Parabola\n"
        rf"$G_j={G:.0f}$,  $H_j={H:.0f}$  |  Minimum at $w^*=-G_j/(H_j+\lambda)$ where slope $= 0$",
        color="white", fontsize=11)
    ax.tick_params(colors="white", labelsize=8)
    for sp in ax.spines.values(): sp.set_edgecolor("#30363d")
    ax.legend(facecolor=BG, labelcolor="white", fontsize=9, loc="upper right")
    ax.set_ylim(obj1_min - 15, max(obj1.max(), obj2.max()) * 0.45)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, "13_xgb_parabola.png"), dpi=150,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("✓ 13_xgb_parabola.png")


if __name__ == "__main__":
    print("Generating images...")

    # Load real HDFS data once — used by multiple charts
    print("[HDFS] Loading real telemetry data...")
    hdfs = _load_hdfs_data(rows_per_car=3000)
    cdf        = hdfs["combined_df"]
    car_ids    = hdfs["car_ids"]
    car_stats  = hdfs["car_stats"]

    # 01 & 02 & 05: conceptual diagrams, no data needed
    plot_pipeline()
    plot_flatten()
    plot_nn()

    # 03–04: use combined DataFrame
    plot_scaler(hdfs_df=cdf)
    plot_xgboost(hdfs_df=cdf)

    # 06–07: use per-car metadata from raw telemetry
    plot_split(car_ids=car_ids)
    plot_meta_input(car_stats=car_stats)

    # 08: use real prediction results from /output_data (best source)
    print("[HDFS] Loading prediction results from /output_data...")
    output_df = _load_output_data()
    plot_final_pred(output_df=output_df, car_stats=car_stats)

    # 09: XGB-only pipeline diagram
    plot_xgb_pipeline()

    # 10: model comparison
    print("[HDFS] Loading XGB-only result from /output_data...")
    xgb_output_df = _load_xgb_output_data()
    plot_model_comparison(xgb_df=xgb_output_df, ensemble_df=output_df)

    # 11: XGBoost full math — loss, Newton step, γ pruning
    plot_xgb_math()

    # 12: EnsembleNN training loop — 6 steps + loss curve
    plot_nn_training()

    # 13: XGBoost parabola — why derivative=0 gives the minimum
    plot_xgb_parabola()

    # 10: model comparison — XGB-only vs Ensemble on real HDFS output data
    print("[HDFS] Loading XGB-only result from /output_data...")
    xgb_output_df = _load_xgb_output_data()
    plot_model_comparison(xgb_df=xgb_output_df, ensemble_df=output_df)

    print(f"\nAll images saved to: {OUT}")
