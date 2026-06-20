"""
Generate HDFS telemetry charts and embed them in hdfs_charts.md.

Usage (from project root):
    python src/AIAPI/docs/generate_hdfs_charts.py

Or with custom HDFS URL:
    python src/AIAPI/docs/generate_hdfs_charts.py --hdfs http://hc1-c-0003u.hc.apac.bosch.com:9870

What it does:
  1. Connects to HDFS at HDFS_URL
  2. Lists /raw_data/battery_telemetry_v4 and picks the latest CSV per car
  3. Downloads each CSV, extracts time-series columns
  4. Generates PNG charts (one multi-panel figure per car + one combined SOC overview)
  5. Saves PNGs to   src/AIAPI/docs/images/hdfs_*.png
  6. Rewrites        src/AIAPI/docs/hdfs_charts.md  with embedded image links
"""

import argparse
import os
import re
import sys
import tempfile
import textwrap
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────
HDFS_URL_DEFAULT = "http://hc1-c-0003u.hc.apac.bosch.com:9870"
HDFS_USER        = "hdfs"
RAW_DATA_DIR     = "/raw_data/battery_telemetry_v4"

# Columns to chart per car (name → y-axis label)
METRICS = {
    "soc_pct":           "SOC (%)",
    "volt_V":            "Voltage (V)",
    "current_A":         "Current (A)",
    "max_temp_C":        "Temp Max (°C)",
    "avg_speed_kmh":     "Speed (km/h)",
}
ROWS_LIMIT = 5_000   # max rows loaded per CSV (for speed)

OUT_DIR = os.path.join(os.path.dirname(__file__), "images")
MD_FILE = os.path.join(os.path.dirname(__file__), "hdfs_charts.md")
os.makedirs(OUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def _ts_from_name(fname: str) -> str:
    """Extract YYYYMMDD_HHMMSS from filename for sorting; fallback to fname."""
    m = re.search(r"(\d{8}_\d{6})", fname)
    return m.group(1) if m else fname


def _latest_csv_per_car(client, directory: str) -> dict:
    """Return {car_id: full_hdfs_path} for the newest CSV of each car."""
    try:
        items = client.list(directory)
    except Exception as e:
        print(f"[HDFS] Cannot list {directory}: {e}")
        return {}

    car_best: dict[str, tuple[str, str]] = {}  # car_id -> (ts_str, hdfs_path)

    for item in items:
        item_path = f"{directory}/{item}"
        status = client.status(item_path)

        if status["type"] == "DIRECTORY":
            # Subdirectory named after car_id  e.g.  /…/EV_101/
            car_id = item
            try:
                sub_items = client.list(item_path)
            except Exception:
                continue
            for f in sub_items:
                if not f.endswith(".csv"):
                    continue
                ts = _ts_from_name(f)
                prev_ts = car_best.get(car_id, ("", ""))[0]
                if ts > prev_ts:
                    car_best[car_id] = (ts, f"{item_path}/{f}")
        elif item.endswith(".csv"):
            # Flat file like  EV_101_20240315_120000.csv
            m = re.match(r"(EV_\d+)", item)
            if not m:
                continue
            car_id = m.group(1)
            ts = _ts_from_name(item)
            prev_ts = car_best.get(car_id, ("", ""))[0]
            if ts > prev_ts:
                car_best[car_id] = (ts, item_path)

    return {car: info[1] for car, info in car_best.items()}


def _download_df(client, hdfs_path: str, limit: int) -> pd.DataFrame | None:
    """Download CSV from HDFS into a temp file and return a DataFrame (head=limit rows)."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        client.download(hdfs_path, tmp_path, overwrite=True)
        df = pd.read_csv(tmp_path, nrows=limit)
        return df
    except Exception as e:
        print(f"  [WARN] Could not load {hdfs_path}: {e}")
        return None
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────
# CHART: one multi-panel figure per car
# ─────────────────────────────────────────────────────────────
PANEL_COLORS = ["#388bfd", "#3fb950", "#f78166", "#d29922", "#bc8cff"]

def _plot_car(car_id: str, df: pd.DataFrame, hdfs_file: str) -> str:
    """Generate a multi-panel time-series chart for one car. Returns saved PNG path."""
    available = [m for m in METRICS if m in df.columns]
    if not available:
        return None

    x = df["timestamp_s"].values if "timestamp_s" in df.columns else np.arange(len(df))

    n = len(available)
    fig = plt.figure(figsize=(14, 2.8 * n))
    fig.patch.set_facecolor("#0d1117")
    gs = gridspec.GridSpec(n, 1, hspace=0.45)

    for i, metric in enumerate(available):
        ax = fig.add_subplot(gs[i])
        ax.set_facecolor("#161b22")
        y = pd.to_numeric(df[metric], errors="coerce").fillna(0).values
        ax.plot(x, y, color=PANEL_COLORS[i % len(PANEL_COLORS)], lw=1.4, alpha=0.9)
        ax.fill_between(x, y, alpha=0.12, color=PANEL_COLORS[i % len(PANEL_COLORS)])
        ax.set_ylabel(METRICS[metric], color="white", fontsize=9)
        ax.tick_params(colors="white", labelsize=8)
        ax.set_xlim(x[0], x[-1])
        for spine in ax.spines.values():
            spine.set_edgecolor("#30363d")
        if i == 0:
            ax.set_title(
                f"{car_id}  —  {len(df):,} rows  |  source: {os.path.basename(hdfs_file)}",
                color="white", fontsize=11, pad=6,
            )
        if i == n - 1:
            ax.set_xlabel("timestamp_s", color="#8b949e", fontsize=9)

    out_path = os.path.join(OUT_DIR, f"hdfs_{car_id}.png")
    plt.savefig(out_path, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✓ hdfs_{car_id}.png")
    return out_path


# ─────────────────────────────────────────────────────────────
# CHART: combined SOC overview (all cars on one axes)
# ─────────────────────────────────────────────────────────────
def _plot_soc_overview(car_data: dict[str, pd.DataFrame]) -> str:
    """SOC% trend for every car on one chart. Returns saved PNG path."""
    cars_with_soc = {c: df for c, df in car_data.items() if "soc_pct" in df.columns}
    if not cars_with_soc:
        return None

    cmap = plt.get_cmap("tab10")
    fig, ax = plt.subplots(figsize=(14, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    for idx, (car_id, df) in enumerate(sorted(cars_with_soc.items())):
        x = df["timestamp_s"].values if "timestamp_s" in df.columns else np.arange(len(df))
        y = pd.to_numeric(df["soc_pct"], errors="coerce").fillna(0).values
        # Normalise x to 0..1 for multi-car overlay
        if len(x) > 1:
            xn = (x - x[0]) / max(x[-1] - x[0], 1)
        else:
            xn = x
        ax.plot(xn, y, lw=1.6, alpha=0.85, color=cmap(idx % 10), label=car_id)

    ax.set_xlabel("Normalised time (0 = start of recording)", color="#8b949e", fontsize=10)
    ax.set_ylabel("SOC (%)", color="white", fontsize=10)
    ax.set_title("SOC (%) Overview — all vehicles (latest HDFS snapshot)", color="white", fontsize=12)
    ax.tick_params(colors="white", labelsize=9)
    ax.legend(fontsize=9, facecolor="#0d1117", labelcolor="white", ncol=4)
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")

    out_path = os.path.join(OUT_DIR, "hdfs_soc_overview.png")
    plt.savefig(out_path, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print("  ✓ hdfs_soc_overview.png")
    return out_path


# ─────────────────────────────────────────────────────────────
# MARKDOWN WRITER
# ─────────────────────────────────────────────────────────────
def _write_md(car_data: dict, car_files: dict, generated_at: str):
    lines = [
        "# HDFS Telemetry Charts",
        "",
        f"> **Generated:** {generated_at}  ",
        f"> **Source:** `{RAW_DATA_DIR}` on HDFS  ",
        "> Charts show the **latest available CSV snapshot** per vehicle.",
        "",
        "---",
        "",
        "## SOC Overview — All Vehicles",
        "",
        "![SOC Overview](images/hdfs_soc_overview.png)",
        "",
        "---",
        "",
        "## Per-Vehicle Telemetry",
        "",
    ]

    for car_id in sorted(car_data.keys()):
        df = car_data[car_id]
        hdfs_file = os.path.basename(car_files.get(car_id, ""))
        rows = len(df)
        cols_found = [m for m in METRICS if m in df.columns]

        lines += [
            f"### {car_id}",
            "",
            f"| Property | Value |",
            f"|---|---|",
            f"| HDFS file | `{hdfs_file}` |",
            f"| Rows loaded | {rows:,} |",
            f"| Metrics charted | {', '.join(f'`{m}`' for m in cols_found)} |",
            "",
            f"![{car_id} telemetry](images/hdfs_{car_id}.png)",
            "",
            "---",
            "",
        ]

    with open(MD_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n✓ Markdown written → {MD_FILE}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate HDFS telemetry charts → MD")
    parser.add_argument("--hdfs", default=HDFS_URL_DEFAULT, help="HDFS WebHDFS base URL")
    parser.add_argument("--user", default=HDFS_USER, help="HDFS username")
    parser.add_argument("--dir", default=RAW_DATA_DIR, help="HDFS directory to scan")
    parser.add_argument("--limit", type=int, default=ROWS_LIMIT, help="Max rows per CSV")
    args = parser.parse_args()

    try:
        from hdfs import InsecureClient
    except ImportError:
        print("ERROR: 'hdfs' package not installed. Run: pip install hdfs")
        sys.exit(1)

    print(f"[HDFS] Connecting to {args.hdfs} as '{args.user}'")
    client = InsecureClient(args.hdfs, user=args.user, timeout=60)

    # 1. Discover latest CSV per car
    print(f"[HDFS] Scanning {args.dir} ...")
    car_files = _latest_csv_per_car(client, args.dir)
    if not car_files:
        print("No CSV files found on HDFS. Exiting.")
        sys.exit(0)
    print(f"[HDFS] Found {len(car_files)} cars: {sorted(car_files)}")

    # 2. Download and chart
    car_data: dict[str, pd.DataFrame] = {}
    for car_id, hdfs_path in sorted(car_files.items()):
        print(f"  Downloading {car_id} ← {hdfs_path}")
        df = _download_df(client, hdfs_path, args.limit)
        if df is None or df.empty:
            continue
        car_data[car_id] = df
        _plot_car(car_id, df, hdfs_path)

    if not car_data:
        print("No data could be loaded. Exiting.")
        sys.exit(0)

    # 3. SOC overview
    print("  Generating SOC overview chart...")
    _plot_soc_overview(car_data)

    # 4. Write markdown
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _write_md(car_data, car_files, generated_at)

    print(f"\nDone! Images: {OUT_DIR}")
    print(f"      Markdown: {MD_FILE}")


if __name__ == "__main__":
    main()
