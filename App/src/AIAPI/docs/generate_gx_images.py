"""
Generate explanatory images for the Great Expectations data-quality guide.

Usage (from repo root, with .venv active):
    python App/src/AIAPI/docs/generate_gx_images.py

Outputs (saved to src/AIAPI/docs/images/):
    gx_01_workflow.png        — GX Core 5-step workflow diagram
    gx_02_expectation_map.png — the 3 intents (Analysis / Constraint / Limit)
    gx_03_validation_result.png — pass/fail bar from validation_result.json
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE       = Path(__file__).resolve().parent
IMAGES_DIR = HERE / "images"
IMAGES_DIR.mkdir(exist_ok=True)
APP_ROOT   = HERE.parents[2]
RESULT_JSON = APP_ROOT / "dataset" / "gx_results" / "validation_result.json"

BLUE   = "#1f77b4"
GREEN  = "#2ca02c"
ORANGE = "#ff7f0e"
RED    = "#d62728"
GREY   = "#555555"

plt.rcParams.update({"figure.dpi": 120, "font.size": 10})


# ─────────────────────────────────────────────────────────────
# IMAGE 1 — GX Core workflow
# ─────────────────────────────────────────────────────────────
def workflow_diagram():
    steps = [
        ("1. Data Context", "gx.get_context()", BLUE),
        ("2. Batch", "pandas → Data Source\n→ Asset → Batch", BLUE),
        ("3. Expectation Suite", "33 expectations\n(Analysis/Constraint/Limit)", ORANGE),
        ("4. Validate", "batch.validate(suite)", GREEN),
        ("5. Results", "JSON + pass/fail\nsummary", GREEN),
    ]
    fig, ax = plt.subplots(figsize=(13, 3.2))
    ax.set_xlim(0, len(steps) * 2.6)
    ax.set_ylim(0, 2.4)
    ax.axis("off")

    for i, (title, sub, color) in enumerate(steps):
        x = i * 2.6 + 0.2
        box = FancyBboxPatch((x, 0.6), 2.1, 1.2, boxstyle="round,pad=0.06",
                             linewidth=2, edgecolor=color, facecolor=color + "22")
        ax.add_patch(box)
        ax.text(x + 1.05, 1.45, title, ha="center", va="center",
                fontsize=11, fontweight="bold", color=color)
        ax.text(x + 1.05, 0.95, sub, ha="center", va="center",
                fontsize=8.5, color=GREY)
        if i < len(steps) - 1:
            ax.add_patch(FancyArrowPatch((x + 2.25, 1.2), (x + 2.55, 1.2),
                                         arrowstyle="-|>", mutation_scale=18, color=GREY))

    ax.set_title("Great Expectations Core — Validation Workflow",
                 fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()
    out = IMAGES_DIR / "gx_01_workflow.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("saved", out.name)


# ─────────────────────────────────────────────────────────────
# IMAGE 2 — expectation intent map
# ─────────────────────────────────────────────────────────────
def intent_map():
    cols = [
        ("A · ANALYSE", "What to MEASURE\n(structure & completeness)", BLUE,
         ["Columns match schema",
          "Row count > 1000",
          "Key columns not null",
          "Exactly 11 cars"]),
        ("B · CONSTRAIN", "What must be TRUE\n(domains & cross-field)", ORANGE,
         ["car_id in known set",
          "nominal in {185, 210}",
          "flags are binary {0,1}",
          "max_volt ≥ min_volt",
          "max_temp ≥ min_temp",
          "nominal ≥ actual_cap"]),
        ("C · LIMIT", "What to BOUND\n(physical min/max)", GREEN,
         ["soc, pedals 0–100%",
          "volt_V 150–500",
          "cell volt 2.0–4.6",
          "current −400…400 A",
          "temp −40…80 °C",
          "capacity 120–210 Ah"]),
    ]
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.axis("off")

    for i, (title, sub, color, items) in enumerate(cols):
        x = i * 4 + 0.3
        box = FancyBboxPatch((x, 0.5), 3.5, 8, boxstyle="round,pad=0.1",
                             linewidth=2.5, edgecolor=color, facecolor=color + "18")
        ax.add_patch(box)
        ax.text(x + 1.75, 8.1, title, ha="center", va="center",
                fontsize=14, fontweight="bold", color=color)
        ax.text(x + 1.75, 7.3, sub, ha="center", va="center",
                fontsize=9.5, color=GREY, style="italic")
        for j, it in enumerate(items):
            ax.text(x + 0.25, 6.5 - j * 0.85, "• " + it, ha="left", va="center",
                    fontsize=10, color="#222222")

    ax.set_title("Battery Telemetry — Expectation Intent Map (33 rules)",
                 fontsize=13, fontweight="bold", pad=10)
    fig.tight_layout()
    out = IMAGES_DIR / "gx_02_expectation_map.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("saved", out.name)


# ─────────────────────────────────────────────────────────────
# IMAGE 3 — validation result summary
# ─────────────────────────────────────────────────────────────
def result_summary():
    if not RESULT_JSON.exists():
        print("[skip] no validation_result.json — run gx_battery_telemetry.py first")
        return
    data = json.loads(RESULT_JSON.read_text())
    stats = data.get("statistics", {})
    total = stats.get("evaluated_expectations", 0)
    ok    = stats.get("successful_expectations", 0)
    fail  = stats.get("unsuccessful_expectations", 0)
    pct   = stats.get("success_percent", 0.0)

    # Count by category using column / type heuristics
    cat = {"Analysis": 0, "Constraint": 0, "Limit": 0}
    for r in data.get("results", []):
        t = r["expectation_config"]["type"]
        if t in ("expect_table_columns_to_match_set",
                 "expect_table_row_count_to_be_between",
                 "expect_column_values_to_not_be_null",
                 "expect_column_unique_value_count_to_be_between"):
            cat["Analysis"] += 1
        elif t in ("expect_column_values_to_be_in_set",
                   "expect_column_pair_values_a_to_be_greater_than_b"):
            cat["Constraint"] += 1
        else:
            cat["Limit"] += 1

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # left: pass vs fail donut
    ax = axes[0]
    wedges, _, _ = ax.pie([ok, max(fail, 0.0001)],
                          labels=["Passed", "Failed"] if fail else ["Passed", ""],
                          colors=[GREEN, RED], autopct=lambda p: f"{p*total/100:.0f}",
                          startangle=90, wedgeprops=dict(width=0.4))
    ax.set_title(f"Validation result — {pct:.0f}% success\n({ok}/{total} expectations)",
                 fontsize=12, fontweight="bold")

    # right: by category
    ax = axes[1]
    names = list(cat.keys())
    vals = list(cat.values())
    colors = [BLUE, ORANGE, GREEN]
    bars = ax.bar(names, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.1, str(v),
                ha="center", va="bottom", fontweight="bold")
    ax.set_ylabel("Number of expectations")
    ax.set_title("Expectations by intent", fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(vals) + 2)

    fig.suptitle("Great Expectations — battery_telemetry_v4", fontsize=13, fontweight="bold")
    fig.tight_layout()
    out = IMAGES_DIR / "gx_03_validation_result.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print("saved", out.name)


if __name__ == "__main__":
    print("Generating GX guide images ...")
    workflow_diagram()
    intent_map()
    result_summary()
    print("Done. Images in:", IMAGES_DIR)
