"""
Generate architecture & pipeline diagrams for ml_airflow ANALYSIS.md
Outputs PNG images into ./images/ folder.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(IMG_DIR, exist_ok=True)

# ── Shared helpers ──────────────────────────────────────────────
COLORS = {
    "green":   "#4CAF50", "green_l":  "#C8E6C9",
    "blue":    "#1976D2", "blue_l":   "#BBDEFB",
    "orange":  "#FF9800", "orange_l": "#FFE0B2",
    "red":     "#F44336", "red_l":    "#FFCDD2",
    "purple":  "#7B1FA2", "purple_l": "#E1BEE7",
    "teal":    "#00897B", "teal_l":   "#B2DFDB",
    "yellow_l":"#FFF9C4",
    "grey":    "#616161", "grey_l":   "#F5F5F5",
    "white":   "#FFFFFF", "black":    "#212121",
    "pink_l":  "#F8BBD0",
}

def _box(ax, x, y, w, h, text, fc, ec="#333", fs=9, bold=False, alpha=1.0, text_color="#212121"):
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                         boxstyle="round,pad=0.12", fc=fc, ec=ec, lw=1.2, alpha=alpha, zorder=2)
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, ha="center", va="center", fontsize=fs,
            fontweight=weight, color=text_color, zorder=3, wrap=True,
            multialignment="center")
    return box

def _arrow(ax, x1, y1, x2, y2, color="#555", style="-|>", lw=1.5, ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, ls=ls),
                zorder=1)

def _label_arrow(ax, x1, y1, x2, y2, label="", color="#555", style="-|>", lw=1.5, ls="-", fs=7):
    _arrow(ax, x1, y1, x2, y2, color=color, style=style, lw=lw, ls=ls)
    mx, my = (x1+x2)/2, (y1+y2)/2
    if label:
        ax.text(mx, my + 0.18, label, ha="center", va="bottom", fontsize=fs, color=color, style="italic")

def _section(ax, x, y, w, h, title, fc="#f5f5f5"):
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                          fc=fc, ec="#999", lw=1.0, ls="--", alpha=0.35, zorder=0)
    ax.add_patch(rect)
    ax.text(x + 0.15, y + h - 0.15, title, fontsize=8, fontweight="bold", color="#555", va="top", zorder=1)


# ================================================================
# DIAGRAM 1: Overall Architecture
# ================================================================
def draw_architecture():
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(-1, 15)
    ax.set_ylim(-1, 10)
    ax.axis("off")
    fig.suptitle("System Architecture — EV Battery Health Prediction", fontsize=14, fontweight="bold", y=0.97)

    # Sections
    _section(ax, -0.5, 7.0, 5.0, 2.5, "Data Sources", COLORS["purple_l"])
    _section(ax, 5.5, 7.0, 8.5, 2.5, "Airflow DAGs", COLORS["orange_l"])
    _section(ax, -0.5, 2.5, 7.5, 4.0, "ML Pipeline (ml_airflow)", COLORS["green_l"])
    _section(ax, 9.0, 2.5, 5.5, 4.0, "HDFS Storage", COLORS["blue_l"])

    # Data sources
    _box(ax, 1.0, 8.8, 2.2, 0.8, "Kafka\nBattery Telemetry", COLORS["purple_l"], bold=True)
    _box(ax, 3.8, 8.0, 2.8, 0.7, "HDFS\n/raw_data/", COLORS["blue_l"], bold=True)

    # DAGs
    _box(ax, 7.5, 8.8, 2.5, 0.8, "kafka_to_hdfs\nEvery 15 min", COLORS["orange_l"], bold=True)
    _box(ax, 10.5, 8.8, 2.5, 0.8, "Training DAG\nManual", COLORS["orange_l"], bold=True)
    _box(ax, 13.0, 8.0, 2.5, 0.8, "Inference DAG\nManual", COLORS["orange_l"], bold=True)

    # ML Pipeline modules
    _box(ax, 0.8, 5.5, 2.0, 0.7, "config.py\nConstants", COLORS["orange_l"])
    _box(ax, 3.5, 5.5, 2.5, 0.7, "data_processing/\nLoad, Buffer, Split", COLORS["yellow_l"])
    _box(ax, 6.2, 5.5, 2.0, 0.7, "models/nn.py\nEnsembleNN", COLORS["blue_l"])
    _box(ax, 1.5, 3.8, 2.5, 0.7, "train_xg_test.py\nTraining Pipeline", COLORS["green_l"], bold=True)
    _box(ax, 5.0, 3.8, 2.5, 0.7, "infer_nn_test.py\nInference Pipeline", COLORS["pink_l"], bold=True)
    _box(ax, 3.3, 3.0, 2.0, 0.6, "visualize/\nplot_curve.py", COLORS["yellow_l"])

    # HDFS Storage
    _box(ax, 11.0, 5.5, 3.0, 0.7, "HDFS /models/\nXGB + NN + Scalers", COLORS["blue_l"], bold=True)
    _box(ax, 11.0, 4.3, 3.0, 0.7, "HDFS /models/learning_curve/\nPNG Charts", COLORS["yellow_l"])
    _box(ax, 11.0, 3.2, 3.0, 0.7, "HDFS /output_data/\nResult CSVs", COLORS["green_l"])

    # Arrows — data flow
    _label_arrow(ax, 2.1, 8.8, 6.2, 8.8, "consume", COLORS["grey"])
    _label_arrow(ax, 7.5, 8.4, 5.2, 8.0, "upload", COLORS["grey"])
    _arrow(ax, 5.2, 7.9, 10.5, 8.4, COLORS["grey"])
    _arrow(ax, 5.2, 7.9, 13.0, 7.9, COLORS["grey"])
    _arrow(ax, 10.5, 8.4, 2.75, 4.15, COLORS["green"])
    _arrow(ax, 13.0, 7.6, 6.25, 4.15, COLORS["red"])

    # Internal ML arrows
    _arrow(ax, 0.8, 5.1, 1.5, 4.15, COLORS["grey"], ls="--", lw=1)
    _arrow(ax, 3.5, 5.1, 2.75, 4.15, COLORS["grey"], ls="--", lw=1)
    _arrow(ax, 3.5, 5.1, 5.0, 4.15, COLORS["grey"], ls="--", lw=1)
    _arrow(ax, 6.2, 5.1, 2.75, 4.15, COLORS["grey"], ls="--", lw=1)
    _arrow(ax, 6.2, 5.1, 6.25, 4.15, COLORS["grey"], ls="--", lw=1)
    _arrow(ax, 3.3, 3.4, 2.75, 3.8, COLORS["grey"], ls="--", lw=1)

    # To HDFS
    _arrow(ax, 2.75, 3.8, 9.5, 5.5, COLORS["blue"])
    _arrow(ax, 2.75, 3.5, 9.5, 4.3, COLORS["blue"])
    _arrow(ax, 6.25, 3.8, 9.5, 3.2, COLORS["blue"])

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "01_architecture.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 01_architecture.png")


# ================================================================
# DIAGRAM 2: Training Pipeline
# ================================================================
def draw_training_pipeline():
    fig, ax = plt.subplots(figsize=(14, 12))
    ax.set_xlim(-1, 13)
    ax.set_ylim(-1, 13)
    ax.axis("off")
    fig.suptitle("Training Pipeline — run_train_pipeline()", fontsize=14, fontweight="bold", y=0.98)

    # Nodes (top to bottom)
    _box(ax, 6, 12, 3.5, 0.8, "START\nrun_train_pipeline()", COLORS["green"], fs=10, bold=True, text_color="white")

    _box(ax, 6, 10.5, 4.0, 0.8, "STEP 1: Load CSVs from HDFS\nget_hdfs_files_filtered()", COLORS["blue_l"])
    _box(ax, 6, 9.2, 4.0, 0.8, "Parse via GlobalSnippetBuffer\nload_data_universal(mode='train')", COLORS["blue_l"])
    _box(ax, 6, 7.9, 3.5, 0.8, "Split by car_id 80/20\nsplit_train_test_by_car()", COLORS["orange_l"])
    _box(ax, 6, 6.7, 3.5, 0.7, "Filter by modality\ncharger_connected", COLORS["orange_l"])

    # Branches
    _box(ax, 3, 5.5, 3.0, 0.7, "Charging Data\n(charger_connected=1)", COLORS["blue_l"], bold=True)
    _box(ax, 9, 5.5, 3.0, 0.7, "Driving Data\n(charger_connected=0)", COLORS["orange_l"], bold=True)

    _box(ax, 3, 4.3, 3.0, 0.7, "extract_features_2d()\nflatten 128×7 → 896", COLORS["grey_l"])
    _box(ax, 9, 4.3, 3.0, 0.7, "extract_features_2d()\nflatten 128×7 → 896", COLORS["grey_l"])

    _box(ax, 3, 3.0, 3.5, 0.8, "STEP 2A: StandardScaler\n+ XGBoost Charging", COLORS["blue"], bold=True, text_color="white")
    _box(ax, 9, 3.0, 3.5, 0.8, "STEP 2B: StandardScaler\n+ XGBoost Driving", COLORS["orange"], bold=True, text_color="white")

    _box(ax, 6, 1.6, 4.0, 0.8, "STEP 2C: Train EnsembleNN\nMeta-Learner on val predictions", COLORS["green"], bold=True, text_color="white")

    _box(ax, 3, 0.3, 3.5, 0.7, "Save models + scalers\nto HDFS", COLORS["blue_l"], bold=True)
    _box(ax, 9, 0.3, 3.0, 0.7, "Plot learning curves\n→ HDFS PNG", COLORS["yellow_l"], bold=True)

    _box(ax, 6, -0.8, 2.0, 0.6, "END", COLORS["red"], bold=True, text_color="white")

    # Arrows
    _arrow(ax, 6, 11.6, 6, 10.9)
    _arrow(ax, 6, 10.1, 6, 9.6)
    _arrow(ax, 6, 8.8, 6, 8.3)
    _arrow(ax, 6, 7.5, 6, 7.05)
    _arrow(ax, 6, 6.35, 3, 5.85)
    _arrow(ax, 6, 6.35, 9, 5.85)
    _arrow(ax, 3, 5.15, 3, 4.65)
    _arrow(ax, 9, 5.15, 9, 4.65)
    _arrow(ax, 3, 3.95, 3, 3.4)
    _arrow(ax, 9, 3.95, 9, 3.4)
    _arrow(ax, 3, 2.6, 4.5, 2.0, COLORS["blue"])
    _arrow(ax, 9, 2.6, 7.5, 2.0, COLORS["orange"])
    _arrow(ax, 3, 2.6, 3, 0.65, COLORS["blue"])
    _arrow(ax, 9, 2.6, 9, 0.65, COLORS["orange"])
    _arrow(ax, 6, 1.2, 4.5, 0.65, COLORS["green"])
    _arrow(ax, 3, -0.05, 5.2, -0.8)
    _arrow(ax, 9, -0.05, 6.8, -0.8)

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "02_training_pipeline.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 02_training_pipeline.png")


# ================================================================
# DIAGRAM 3: Inference Pipeline
# ================================================================
def draw_inference_pipeline():
    fig, ax = plt.subplots(figsize=(14, 12))
    ax.set_xlim(-1, 13)
    ax.set_ylim(-1, 13)
    ax.axis("off")
    fig.suptitle("Inference Pipeline — run_inference_pipeline_nn()", fontsize=14, fontweight="bold", y=0.98)

    _box(ax, 6, 12, 3.5, 0.8, "START\nrun_inference_pipeline_nn()", COLORS["green"], fs=10, bold=True, text_color="white")
    _box(ax, 6, 10.5, 4.5, 0.8, "STEP 1: Load Models from HDFS\nXGB_chg, XGB_drv, EnsembleNN", COLORS["blue_l"])
    _box(ax, 6, 9.2, 4.0, 0.8, "STEP 2: Load Inference Data\nfrom HDFS (EV_015, EV_016)", COLORS["blue_l"])
    _box(ax, 6, 8.0, 4.0, 0.7, "Parse via GlobalSnippetBuffer\nmode='inference'", COLORS["orange_l"])
    _box(ax, 6, 6.9, 3.5, 0.7, "Split by modality\nCharging vs Driving", COLORS["orange_l"])

    _box(ax, 3, 5.7, 3.0, 0.7, "XGB Charging\nPredict", COLORS["blue"], bold=True, text_color="white")
    _box(ax, 9, 5.7, 3.0, 0.7, "XGB Driving\nPredict", COLORS["orange"], bold=True, text_color="white")

    _box(ax, 6, 4.3, 4.0, 0.8, "STEP 4: Ensemble per car_id\nBoth predictions available?", COLORS["yellow_l"], bold=True)

    _box(ax, 2, 3.0, 3.0, 0.7, "EnsembleNN\n→ final_pred", COLORS["green"], bold=True, text_color="white")
    _box(ax, 6, 3.0, 2.8, 0.7, "Simple Average\n(fallback)", COLORS["orange_l"])
    _box(ax, 10, 3.0, 2.8, 0.7, "Single Model\nprediction", COLORS["grey_l"])

    _box(ax, 6, 1.5, 4.0, 0.7, "Compute RMSE & Plot\ncomparison chart", COLORS["purple_l"])
    _box(ax, 6, 0.3, 3.5, 0.7, "Save results CSV to HDFS\nsave_csv_hdfs()", COLORS["blue_l"], bold=True)
    _box(ax, 6, -0.8, 2.0, 0.6, "END", COLORS["red"], bold=True, text_color="white")

    # Arrows
    _arrow(ax, 6, 11.6, 6, 10.9)
    _arrow(ax, 6, 10.1, 6, 9.6)
    _arrow(ax, 6, 8.8, 6, 8.35)
    _arrow(ax, 6, 7.65, 6, 7.25)
    _arrow(ax, 6, 6.55, 3, 6.05)
    _arrow(ax, 6, 6.55, 9, 6.05)
    _arrow(ax, 3, 5.35, 4.5, 4.7, COLORS["blue"])
    _arrow(ax, 9, 5.35, 7.5, 4.7, COLORS["orange"])
    _label_arrow(ax, 4.5, 3.9, 2, 3.35, "Yes + NN", COLORS["green"])
    _label_arrow(ax, 6, 3.9, 6, 3.35, "Yes, no NN", COLORS["orange"])
    _label_arrow(ax, 7.5, 3.9, 10, 3.35, "Only one", COLORS["grey"])
    _arrow(ax, 2, 2.65, 4.5, 1.85, COLORS["green"])
    _arrow(ax, 6, 2.65, 6, 1.85, COLORS["orange"])
    _arrow(ax, 10, 2.65, 7.5, 1.85, COLORS["grey"])
    _arrow(ax, 6, 1.15, 6, 0.65)
    _arrow(ax, 6, -0.05, 6, -0.5)

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "03_inference_pipeline.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 03_inference_pipeline.png")


# ================================================================
# DIAGRAM 4: Data Processing (GlobalSnippetBuffer)
# ================================================================
def draw_data_processing():
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.set_xlim(-0.5, 15)
    ax.set_ylim(-0.5, 5.5)
    ax.axis("off")
    fig.suptitle("Data Processing Pipeline — GlobalSnippetBuffer", fontsize=14, fontweight="bold", y=0.98)

    # Input
    _section(ax, -0.3, 1.5, 2.2, 2.5, "Input", COLORS["purple_l"])
    _box(ax, 0.8, 2.7, 1.8, 1.2, "CSV Chunks\n(200K rows\neach)", COLORS["purple_l"], bold=True)

    # Buffer processing steps
    _section(ax, 2.5, 0.5, 8.5, 4.5, "GlobalSnippetBuffer", COLORS["green_l"])
    _box(ax, 3.7, 3.8, 2.0, 0.8, "Preprocessing\n• clip soc [0,100]\n• step_idx = ts//10\n• validate capacity", COLORS["yellow_l"], fs=7)
    _box(ax, 6.2, 3.8, 2.0, 0.7, "Group by\n(car_id,\nid_segment)", COLORS["orange_l"], fs=8)
    _box(ax, 8.7, 3.8, 2.0, 0.7, "Sliding Window\nsize = 128 steps", COLORS["blue_l"], fs=8, bold=True)
    _box(ax, 6.5, 1.5, 2.5, 0.8, "Validation\n• 128 unique steps\n• continuous range\n• select features", COLORS["teal_l"], fs=7)

    # Output
    _section(ax, 11.5, 0.5, 3.2, 4.5, "Output", COLORS["blue_l"])
    _box(ax, 13.0, 3.8, 2.5, 0.8, "Finished Samples\n(128×7 array,\nmetadata)", COLORS["green_l"], bold=True)
    _box(ax, 13.0, 1.5, 2.5, 0.8, "Remainder Buffer\n(leftover rows\n< 128)", COLORS["red_l"])

    # Arrows
    _arrow(ax, 1.7, 2.7, 2.7, 3.8)
    _arrow(ax, 4.7, 3.8, 5.2, 3.8)
    _arrow(ax, 7.2, 3.8, 7.7, 3.8)
    _arrow(ax, 8.7, 3.4, 7.75, 1.9)
    _label_arrow(ax, 7.75, 1.5, 11.75, 3.8, "pass ✓", COLORS["green"])
    _label_arrow(ax, 6.5, 1.1, 13.0, 1.1, "remainder", COLORS["red"])
    _arrow(ax, 13.0, 1.1, 3.7, 1.1, COLORS["red"], ls="--")  # loop back
    _arrow(ax, 3.7, 1.1, 3.7, 3.4, COLORS["red"], ls="--")

    ax.text(3.0, 0.7, "next chunk →", fontsize=7, color=COLORS["red"], style="italic")

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "04_data_processing.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 04_data_processing.png")


# ================================================================
# DIAGRAM 5: Model Architecture
# ================================================================
def draw_model_architecture():
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(-1, 14)
    ax.set_ylim(-0.5, 7)
    ax.axis("off")
    fig.suptitle("Model Architecture — XGBoost Ensemble + Neural Network Meta-Learner",
                 fontsize=14, fontweight="bold", y=0.98)

    # Base models
    _section(ax, -0.5, 1.5, 5.5, 5.0, "Base Models (XGBoost)", COLORS["blue_l"])

    _box(ax, 2.2, 5.0, 4.0, 1.2,
         "XGBoost — Charging Model\n\nInput: 128 × 7 = 896 features\nScaler: StandardScaler\nOutput: pred_chg (Ah)",
         COLORS["blue_l"], bold=True, fs=8)

    _box(ax, 2.2, 2.8, 4.0, 1.2,
         "XGBoost — Driving Model\n\nInput: 128 × 7 = 896 features\nScaler: StandardScaler\nOutput: pred_drv (Ah)",
         COLORS["orange_l"], bold=True, fs=8)

    # Meta-learner
    _section(ax, 6.5, 0.5, 7.0, 6.0, "Meta-Learner (PyTorch)", COLORS["green_l"])

    _box(ax, 10, 5.5, 3.5, 0.7, "Input: 2 values\n(pred_chg, pred_drv)", COLORS["grey_l"], bold=True)
    _box(ax, 10, 4.3, 3.0, 0.7, "Linear(2 → 32) + ReLU", COLORS["blue_l"])
    _box(ax, 10, 3.2, 3.0, 0.7, "Linear(32 → 16) + ReLU", COLORS["blue_l"])
    _box(ax, 10, 2.1, 3.0, 0.7, "Linear(16 → 1)", COLORS["blue_l"])
    _box(ax, 10, 1.0, 3.5, 0.7, "Output: Predicted\nCapacity (Ah)", COLORS["green"], bold=True, text_color="white")

    # Arrows
    _label_arrow(ax, 4.2, 5.0, 8.25, 5.5, "pred_chg", COLORS["blue"])
    _label_arrow(ax, 4.2, 2.8, 8.25, 5.3, "pred_drv", COLORS["orange"])
    _arrow(ax, 10, 5.15, 10, 4.65)
    _arrow(ax, 10, 3.95, 10, 3.55)
    _arrow(ax, 10, 2.85, 10, 2.45)
    _arrow(ax, 10, 1.75, 10, 1.35)

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "05_model_architecture.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 05_model_architecture.png")


# ================================================================
# DIAGRAM 6: End-to-End Data Flow
# ================================================================
def draw_e2e_dataflow():
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(-1, 16)
    ax.set_ylim(-1, 11)
    ax.axis("off")
    fig.suptitle("End-to-End Data Flow", fontsize=14, fontweight="bold", y=0.98)

    # ── Row 1: Ingestion ──
    _section(ax, -0.5, 8.0, 15.5, 2.5, "1. Data Ingestion", COLORS["purple_l"])
    _box(ax, 1.5, 9.2, 2.5, 0.8, "EV Vehicles\nBattery Telemetry", COLORS["purple_l"], bold=True)
    _box(ax, 5.0, 9.2, 2.5, 0.8, "Kafka Topic", COLORS["orange_l"], bold=True)
    _box(ax, 9.0, 9.2, 3.0, 0.7, "kafka_to_hdfs DAG\nevery 15 min", COLORS["orange_l"])
    _box(ax, 13.0, 9.2, 2.5, 1.2, "HDFS\n/raw_data/\nEV_012 ~ EV_016", COLORS["blue_l"], bold=True)

    _label_arrow(ax, 2.75, 9.2, 3.75, 9.2, "publish")
    _label_arrow(ax, 6.25, 9.2, 7.5, 9.2, "consume")
    _label_arrow(ax, 10.5, 9.2, 11.75, 9.2, "upload")

    # ── Row 2: Training ──
    _section(ax, -0.5, 3.5, 15.5, 4.0, "2. Training", COLORS["green_l"])
    _box(ax, 1.5, 6.5, 2.8, 0.8, "GlobalSnippetBuffer\nWindow=128, Feat=7", COLORS["yellow_l"])
    _box(ax, 1.5, 5.2, 2.5, 0.7, "split_train_test\n80% / 20%", COLORS["orange_l"])
    _box(ax, 1.5, 4.2, 2.5, 0.7, "CHG + DRV\nSamples", COLORS["grey_l"])

    _box(ax, 5.5, 6.2, 2.5, 0.7, "XGBoost\nCharging", COLORS["blue"], text_color="white", bold=True)
    _box(ax, 5.5, 5.0, 2.5, 0.7, "XGBoost\nDriving", COLORS["orange"], text_color="white", bold=True)
    _box(ax, 5.5, 3.9, 2.5, 0.7, "EnsembleNN\nMeta-Learner", COLORS["green"], text_color="white", bold=True)

    _box(ax, 11.0, 5.2, 3.8, 1.5,
         "HDFS /models/\n─────────────────\nxgb_model_chg.json\nxgb_model_drv.json\nscaler_chg.joblib\nscaler_drv.joblib\nensemble_nn.pth",
         COLORS["blue_l"], bold=True, fs=7)

    _label_arrow(ax, 13.0, 8.6, 2.9, 6.9, "read EV_012-014", COLORS["blue"])
    _arrow(ax, 1.5, 6.1, 1.5, 5.55)
    _arrow(ax, 1.5, 4.85, 1.5, 4.55)
    _label_arrow(ax, 2.75, 6.2, 4.25, 6.2, "flatten", COLORS["grey"])
    _label_arrow(ax, 2.75, 5.0, 4.25, 5.0, "flatten", COLORS["grey"])
    _label_arrow(ax, 5.5, 5.6, 5.5, 4.25, "val preds", COLORS["green"])
    _label_arrow(ax, 5.5, 4.6, 5.5, 4.25, "val preds", COLORS["green"])
    _arrow(ax, 6.75, 6.2, 9.1, 5.8, COLORS["blue"])
    _arrow(ax, 6.75, 5.0, 9.1, 5.2, COLORS["orange"])
    _arrow(ax, 6.75, 3.9, 9.1, 4.6, COLORS["green"])

    # ── Row 3: Inference ──
    _section(ax, -0.5, -0.5, 15.5, 3.5, "3. Inference", COLORS["pink_l"])
    _box(ax, 1.5, 1.8, 2.8, 0.8, "GlobalSnippetBuffer\nmode='inference'", COLORS["yellow_l"])
    _box(ax, 5.5, 1.8, 2.5, 0.7, "Inference\nEngine", COLORS["purple_l"], bold=True)
    _box(ax, 10, 1.8, 3.0, 0.7, "Results CSV\nHDFS /output_data/", COLORS["green_l"], bold=True)
    _box(ax, 10, 0.5, 3.0, 0.7, "RMSE Chart\nHDFS /models/learning_curve/", COLORS["yellow_l"])

    _label_arrow(ax, 13.0, 8.6, 2.9, 2.2, "read EV_015-016", COLORS["red"])
    _arrow(ax, 2.9, 1.8, 4.25, 1.8)
    _arrow(ax, 11.0, 4.5, 6.75, 2.15, COLORS["blue"], ls="--")
    _arrow(ax, 6.75, 1.8, 8.5, 1.8, COLORS["green"])
    _arrow(ax, 6.75, 1.5, 8.5, 0.5, COLORS["orange"])

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "06_e2e_dataflow.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 06_e2e_dataflow.png")


# ================================================================
# DIAGRAM 7: Directory Structure
# ================================================================
def draw_directory_structure():
    fig, ax = plt.subplots(figsize=(10, 9))
    ax.set_xlim(-0.5, 10)
    ax.set_ylim(-0.5, 11)
    ax.axis("off")
    fig.suptitle("Directory Structure — src/airflow/", fontsize=14, fontweight="bold", y=0.98)

    tree = [
        (0, "src/airflow/", True, COLORS["grey"]),
        (1, "dags/", True, COLORS["orange_l"]),
        (2, "train_airflow.py  — Training DAG", False, COLORS["green_l"]),
        (2, "inference_airflow.py  — Inference DAG", False, COLORS["pink_l"]),
        (2, "kafka_to_hdfs.py  — Data Ingestion DAG", False, COLORS["purple_l"]),
        (1, "ml_airflow/", True, COLORS["blue_l"]),
        (2, "config/", True, COLORS["orange_l"]),
        (3, "config.py  — Global constants & params", False, COLORS["orange_l"]),
        (2, "data_processing/", True, COLORS["yellow_l"]),
        (3, "data_utils.py  — HDFS I/O, data loading", False, COLORS["yellow_l"]),
        (3, "snippetbuffer.py  — Time-series windowing", False, COLORS["yellow_l"]),
        (3, "split_and_extract.py  — Train/test split, features", False, COLORS["yellow_l"]),
        (2, "models/", True, COLORS["blue_l"]),
        (3, "nn.py  — EnsembleNN meta-learner", False, COLORS["blue_l"]),
        (2, "testing/", True, COLORS["green_l"]),
        (3, "train_xg_test.py  — Full training pipeline", False, COLORS["green_l"]),
        (3, "infer_nn_test.py  — Full inference pipeline", False, COLORS["pink_l"]),
        (2, "visualize/", True, COLORS["teal_l"]),
        (3, "plot_curve.py  — Learning curve plotter", False, COLORS["teal_l"]),
        (1, "plugins/  (empty)", True, COLORS["grey_l"]),
    ]

    y = 10.0
    for indent, label, is_dir, color in tree:
        x = 0.5 + indent * 0.8
        icon = "[D] " if is_dir else "[F] "
        weight = "bold" if is_dir else "normal"
        fs = 9 if is_dir else 8
        ax.text(x, y, icon + label, fontsize=fs, fontweight=weight,
                fontfamily="monospace", va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc=color, ec="none", alpha=0.5))
        y -= 0.5

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "07_directory_structure.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 07_directory_structure.png")


# ================================================================
# DIAGRAM 8: Feature Table Visualization
# ================================================================
def draw_feature_table():
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")
    fig.suptitle("Feature Columns (7 features × 128 time steps per window)", fontsize=13, fontweight="bold", y=0.96)

    columns = ["#", "Feature", "Unit", "Description"]
    data = [
        ["1", "volt_V",           "V",  "Battery pack voltage"],
        ["2", "current_A",        "A",  "Battery current"],
        ["3", "soc_pct",          "%",  "State of Charge (clipped 0–100)"],
        ["4", "max_single_volt_V","V",  "Maximum single cell voltage"],
        ["5", "min_single_volt_V","V",  "Minimum single cell voltage"],
        ["6", "max_temp_C",       "°C", "Maximum temperature"],
        ["7", "min_temp_C",       "°C", "Minimum temperature"],
    ]

    table = ax.table(cellText=data, colLabels=columns, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.8)

    # Style header
    for j in range(len(columns)):
        table[0, j].set_facecolor(COLORS["blue"])
        table[0, j].set_text_props(color="white", fontweight="bold")
    # Style rows
    for i in range(1, len(data) + 1):
        for j in range(len(columns)):
            table[i, j].set_facecolor(COLORS["blue_l"] if i % 2 == 0 else COLORS["white"])

    plt.tight_layout()
    fig.savefig(os.path.join(IMG_DIR, "08_feature_table.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ 08_feature_table.png")


# ================================================================
# MAIN
# ================================================================
if __name__ == "__main__":
    print(f"Generating diagrams into {IMG_DIR}/ ...")
    draw_architecture()
    draw_training_pipeline()
    draw_inference_pipeline()
    draw_data_processing()
    draw_model_architecture()
    draw_e2e_dataflow()
    draw_directory_structure()
    draw_feature_table()
    print(f"\nDone! {len(os.listdir(IMG_DIR))} images generated.")
