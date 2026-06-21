# Chat Session Context — Battery Health ML Pipeline
> **Date:** 2026-06-11 to 2026-06-21  
> **Project:** `eet-dp-predictive-ai-concept`  
> **Scope:** Math documentation, XGBoost derivations, EnsembleNN training loop, EDA / data validation / SOM anomaly detection

---

## Project Setup

### Key Files

| File | Purpose |
|---|---|
| `src/AIAPI/docs/math_analysis.md` | Full ML pipeline documentation with embedded images |
| `src/AIAPI/docs/generate_math_images.py` | Generates all PNG images (01–13) embedded in `math_analysis.md` |
| `src/AIAPI/core/nn.py` | EnsembleNN definition (2→32→16→1 MLP) |
| `src/AIAPI/core/config.py` | HDFS URL, feature columns, window size |
| `src/AIAPI/api/train_pipeline.py` | Full training pipeline (XGBoost + EnsembleNN) |
| `src/AIAPI/api/xgb_train.py` | XGBoost-only pipeline |
| `src/AIAPI/api/train.py` | Inference pipeline |

### Infrastructure

- **HDFS:** `http://hc1-c-0003u.hc.apac.bosch.com:9870`, user=`hdfs`
- **Key HDFS paths:**
  - `/raw_data/battery_telemetry_v4/{car_id}/` — raw telemetry CSVs
  - `/output_data/` — `inference_ensemble_result_*.csv`, `inference_xgb_result_*.csv`
  - `/models/battery_health_ensemble/`, `/models/battery_health_xgb/`
- **Focus cars:** `EV_104, EV_105, EV_109, EV_110`
- **All cars:** `EV_066, EV_101–EV_110` (11 total)
- **Python:** 3.14, Windows

### EnsembleNN Architecture (`core/nn.py`)

```python
class EnsembleNN(nn.Module):
    def __init__(self):
        super(EnsembleNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(2, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1)
        )
    def forward(self, p_chg, p_drv):
        x = torch.cat([p_chg, p_drv], dim=1)
        return self.net(x)
```

- Input: `[p_chg, p_drv]` — XGBoost charging and driving predictions per car (Ah)
- Output: final battery capacity prediction (Ah)
- Total parameters: **657**
- Training: 300 epochs, Adam lr=0.01, MSELoss

---

## Images Generated (`generate_math_images.py`)

| File | Function | Description |
|---|---|---|
| `01_pipeline_overview.png` | `plot_pipeline()` | Full pipeline flow diagram |
| `02_window_flatten.png` | `plot_flatten()` | Window→feature vector flattening |
| `03_standardscaler.png` | `plot_scaler(hdfs_df)` | StandardScaler on real volt_V, current_A, soc_pct |
| `04_xgboost_additive.png` | `plot_xgboost(hdfs_df)` | 2×2 grid, one panel per focus car, boosting convergence |
| `05_ensemble_nn.png` | `plot_nn()` | Architecture diagram 2→32→16→1 |
| `06_train_val_split.png` | `plot_split(car_ids)` | Train/val car split |
| `07_meta_input.png` | `plot_meta_input(car_stats)` | Focus cars volt snippets |
| `08_final_prediction.png` | `plot_final_pred(output_df, car_stats)` | Final predictions vs GT |
| `09_xgb_pipeline.png` | `plot_xgb_pipeline()` | xgb_train.py flow diagram |
| `10_model_comparison.png` | `plot_model_comparison(xgb_df, ensemble_df)` | 5-series grouped bar + error panel |
| `11_xgb_math.png` | `plot_xgb_math()` | 3 panels: loss+g/h, Newton w*, split gain vs γ |
| `12_nn_training.png` | `plot_nn_training()` | 6-step flow diagram + loss/gradient curves over 300 epochs |
| `13_xgb_parabola.png` | `plot_xgb_parabola()` | Upward parabola showing Obj_j minimum at w* |

> `plot_nn_training()` uses **pure numpy** (no PyTorch) to simulate the 2→32→16→1 forward pass, backprop, and Adam update.

---

## Q&A Topics Covered This Session

### Topic 1 — EnsembleNN: many cars but only 2 input neurons

Even though there are many cars (many rows), the network has **2 input neurons** because each car is represented by exactly 2 values: `p_chg` and `p_drv`.

```
Input tensor shape: (N, 2)
                     ↑  ↑
                N cars  2 features (p_chg, p_drv)
```

The XGBoost models already **averaged** all segments per car into one scalar before the NN sees them.

---

### Topic 2 — Worked Numerical Example: EnsembleNN (2→2→1, Epoch 1)

**Setup (simplified 2→2→1 for readability):**

```
W1 = [[0.5, -0.3], [0.2, 0.8]],  b1 = [0, 0]
W2 = [[0.6, 0.4]],               b2 = 0
Input: x = [175.0, 178.0]  (p_chg=175, p_drv=178 for EV_104)
y_true = 202.7 Ah
```

**Step 2 — Forward pass:**
- `z1 = W1 @ x = [34.1, 177.4]`
- `a1 = ReLU(z1) = [34.1, 177.4]` (both positive → unchanged)
- `ŷ = W2 @ a1 = 0.6×34.1 + 0.4×177.4 = 91.42 Ah`

**Step 3 — Loss:**
- `L = (91.42 - 202.7)² = 12,383.2`

**Step 4 — Backprop:**
- `∂L/∂ŷ = 2(91.42 - 202.7) = -222.56`
- `∂L/∂W2 = [-222.56×34.1, -222.56×177.4] = [-7589.3, -39482.1]`
- `∂L/∂a1 = [-222.56×0.6, -222.56×0.4] = [-133.5, -89.0]`
- ReLU gate: both z1 > 0 → gradient passes through unchanged
- `∂L/∂W1 = outer([-133.5, -89.0], [175, 178]) = [[-23369, -23769], [-15579, -15846]]`

**Step 5 — Adam update (t=1):**

| Quantity | W2[0] | W2[1] |
|---|---|---|
| g | -7589.3 | -39482.1 |
| m₁ = 0.1·g | -758.9 | -3948.2 |
| v₁ = 0.001·g² | 57,597 | 1,558,840 |
| m̂₁ = m₁/0.1 | -7589.3 | -39482.1 |
| v̂₁ = v₁/0.001 | 5.76×10⁷ | 1.56×10⁹ |
| W2_new = W2 - 0.01·m̂/√v̂ | 0.61 | 0.41 |

> Key insight: at t=1, Adam always steps exactly ±α = ±0.01 regardless of gradient magnitude (normalising effect).

---

### Topic 3 — Symbol Clarification

| Symbol | Name | Operation |
|---|---|---|
| ⊙ (`$\odot$`) | Hadamard product | element-wise multiply — used for ReLU gradient gate |
| ⊗ (`$\otimes$`) | Outer product | every pair multiplied — used for `∂L/∂W1 = dz1 ⊗ x` |
| · or @ | Dot / matrix product | row × column sum |

**⊙ in ReLU backprop:**
```
∂L/∂z1 = ∂L/∂a1 ⊙ 1[z1>0]
        = [-133.5, -89.0] ⊙ [1, 1] = [-133.5, -89.0]
```
If a neuron had z1 < 0, the gate is **0** and the gradient is blocked — that weight does not update.

**⊗ for weight gradient:**
```
∂L/∂W1 = [-133.5, -89.0] ⊗ [175, 178]
        = [[-133.5×175, -133.5×178], [-89.0×175, -89.0×178]]
        = [[-23369, -23769], [-15579, -15846]]
```
Shape matches W1 (2×2) — one gradient value per weight.

---

### Topic 4 — Newton Step Derivation (Taylor 2nd-Order Proof)

**Full 6-step proof added to `math_analysis.md`:**

1. **Exact objective:** $\mathcal{L}^{(k)} = \sum_i \ell(y_i, \hat{y}_i^{(k-1)} + f_k(x_i)) + \Omega(f_k)$

2. **Taylor 2nd-order expand** $\ell$ around $\hat{y}^{(k-1)}$ with $\delta = f_k(x_i)$:
   $$\ell \approx \text{const} + g_i\delta + \tfrac{1}{2}h_i\delta^2 \quad \Rightarrow \quad \text{drop constant}$$

3. **Regularisation:** $\Omega(f_k) = \gamma T + \frac{1}{2}\lambda\sum_j w_j^2$
   > The $\frac{1}{2}\lambda\sum w_j^2$ is **NOT removed** — it merges with the Taylor term in step 4:
   > $\frac{1}{2}H_j w_j^2 + \frac{1}{2}\lambda w_j^2 = \frac{1}{2}(H_j+\lambda)w_j^2$

4. **Group by leaf:** $\text{Obj}_j = G_j w_j + \frac{1}{2}(H_j+\lambda)w_j^2$

5. **Set derivative = 0:** $G_j + (H_j+\lambda)w_j = 0$
   > Why derivative = 0 gives minimum: the coefficient $(H_j+\lambda) > 0$ means the parabola opens **upward** — the flat point is always the bottom, never the top.

6. **Solve:** $\boxed{w_j^* = -\dfrac{G_j}{H_j+\lambda}}$

---

### Topic 5 — What is δ?

$\delta = f_k(x_i)$ — the **prediction added by the new tree** at round k for sample i.

```
Round k=1:  ŷ=0    + δ=165.0 → 165.0 Ah
Round k=2:  ŷ=165  + δ=8.3   → 173.3 Ah
Round k=3:  ŷ=173  + δ=4.1   → 177.4 Ah
...                              → ~202 Ah
```

---

### Topic 6 — What is Ω(f_k)?

$\Omega(f_k)$ is the **regularisation penalty** — cost for tree complexity:

$$\Omega(f_k) = \underbrace{\gamma T}_{\text{penalty per leaf}} + \underbrace{\frac{1}{2}\lambda\sum_j w_j^2}_{\text{penalty for large weights}}$$

Without $\Omega$, XGBoost overfits every sample. $\Omega$ forces: only split when gain > cost.

---

### Topic 7 — XGBoost Objective Function: 3 Levels

| Level | Formula | Exact or Approx? | Purpose |
|---|---|---|---|
| 1 | $\sum \ell(y_i, \hat{y}^{(k-1)} + f_k) + \Omega$ | **Exact** | Defines the goal |
| 2 | $\sum [g_i f_k + \frac{1}{2}h_i f_k^2] + \Omega$ | **Taylor Approximation** | Makes it analytically solvable |
| 3 | $G_j w_j + \frac{1}{2}(H_j+\lambda)w_j^2$ | Approx + grouped by leaf | Gives $w_j^*$ in closed form |

Level 1 (the "Full Objective Function") is **exact** — the approximation is Level 1 → Level 2 via Taylor expansion.

---

### Topic 8 — Why set derivative = 0 (confirmed as minimum, not just candidate)

A "critical point" (derivative = 0) is a minimum when the **2nd derivative > 0**:

$$\frac{\partial^2 \text{Obj}_j}{\partial w_j^2} = H_j + \lambda > 0 \quad \text{always (since } H_j \geq 0, \lambda > 0\text{)}$$

The word "candidate" is mathematically careful language before doing the 2nd-derivative check. In XGBoost the check always passes → it is always a minimum.

**Connection to loss function:** $\text{Obj}_j$ IS derived from $\ell$ (via Taylor), so minimising $\text{Obj}_j$ = minimising the (approximate) loss.

---

### Topic 9 — Weak Points of XGBoost

| # | Weak point | Root cause |
|---|---|---|
| 1 | Cannot extrapolate beyond training range | Tree structure clips to edge leaf |
| 2 | No temporal awareness | Each snippet is independent — no memory across months |
| 3 | Sensitive to feature engineering | Flattened window loses time-series patterns |
| 4 | High-variance trees with small dataset | 11 cars — one noisy car can dominate split thresholds |
| 5 | EnsembleNN meta-learner is data-starved | 657 params trained on ≤ 4 samples = memorisation |

---

### Topic 10 — Data Improvements Needed

| Priority | Fix | Target |
|---|---|---|
| 1 | More cars | 11 → 50+ (minimum), 200+ (ideal) |
| 2 | Full lifecycle coverage | Cars from new (210 Ah) to degraded (160 Ah) |
| 3 | More segments per car | ~9 snippets now → 50+ snippets (500+ rows per car) |
| 4 | Balanced modality | ≥ 20 charging + ≥ 20 driving snippets per car |
| 5 | Better ground truth labels | Full charge-cycle measurement (not OBD approximation) |

---

## Known Bugs (Not Yet Fixed)

- **`train_pipeline.py` line 73:** `X_val_c` is truncated — should be `X_val_chg_scaled = None`  
  Causes `NameError` at runtime if val_chg is empty. User undid the fix — still present.

---

## math_analysis.md Section Map

| Section | Line (approx) | Content |
|---|---|---|
| Step 1 | ~20 | Window extraction, GlobalSnippetBuffer |
| Step 2 | ~40 | Feature extraction, flatten 128×7 → 896 |
| Step 3 | ~60 | StandardScaler normalisation |
| Step 4 | ~80 | Train/val split by car |
| Step 5 | ~100 | XGBoost — full objective, γ, λ, Newton proof, split gain |
| Step 6 | ~185 | Meta-learner input construction |
| Step 7 | ~200 | EnsembleNN — architecture, 6-step training loop, worked example |
| Step 8 | ~310 | Final ensemble prediction (inference) |
| Step 9 | ~330 | RMSE evaluation metrics |
| XGB-Only Pipeline | ~360 | xgb_train.py flow |
| Model Comparison | ~543 | XGB-Only vs Ensemble on real HDFS data |
| Weak Points | ~580 | XGBoost limitations |
| Data Improvements | ~640 | What data is needed |

---

## Session 2026-06-09 — Additional Context

> Topics covered in the earlier session (June 09–10) not already captured above.

### S2-1 — γ is NOT an Eigenvalue

When asked "do we calculate eigenvalue?", answer is **no**. In XGBoost formulas:
- $\gamma$ = `min_split_loss` — minimum loss reduction required to split a node (default `0` in code, not set)
- $\lambda$ = `reg_lambda` — L2 regularization on leaf weights (default `1` in code, not set)
- Neither is an eigenvalue — the pipeline uses no matrix decomposition (no PCA, no SVD, no eigendecomposition)

### S2-2 — λ (reg_lambda) Explained

| Value | Effect on leaf weight |
|---|---|
| λ = 0 | $w_j^* = -G_j/H_j$ — no regularization, overfits |
| λ = 1 (default) | $w_j^* = -G_j/(H_j+1)$ — shrinks weights slightly |
| λ large | $w_j^* \to 0$ — very conservative model |

In the code `reg_lambda` is **not explicitly set** → defaults to `1`.

### S2-3 — L(k) is Derivation Only, Not Computed at Runtime

$\mathcal{L}^{(k)}$ is used **on paper** to derive $w_j^*$.  
At **runtime**, XGBoost only computes:
- $g_i = 2(\hat{y}_i - y_i)$ — first derivative of loss
- $h_i = 2$ — second derivative (constant for squared error)
- $G_j = \sum_{i \in \text{leaf}_j} g_i$ — leaf gradient sum
- $H_j = \sum_{i \in \text{leaf}_j} h_i$ — leaf hessian sum
- $w_j^* = -G_j / (H_j + \lambda)$ — applied directly

The full loss $\mathcal{L}^{(k)}$ is **never explicitly evaluated** per iteration.

### S2-4 — Concrete Data Example (EV_066)

Sample raw CSV columns relevant to pipeline:
```
actual_max_capacity_Ah = 193.72   ← y label (ground truth capacity)
nominal_capacity_Ah    = 210.0    ← used for SoH = 193.72/210 × 100% = 92.2%
charger_connected      = 0        ← driving session → uses FEATURE_COLS_DRV
car_id                 = EV_066
id_segment             = DR101229_1
timestamp_s            = 0, 10, 20, 30, ...  (10s intervals)
step_idx               = timestamp_s // 10   = 0, 1, 2, 3, ...
```

7 rows of this data → **no window emitted** (need 128 rows with step_idx 0→127).

### S2-5 — x.flatten() Illustrated (T=3, F=2)

```python
# Window before flatten:
x = [[3.8, 10.0],   # t=0: volt_V, current_A
     [3.9,  9.5],   # t=1
     [4.0,  9.0]]   # t=2

# After x.flatten() — row-major order:
X[i] = [3.8, 10.0, 3.9, 9.5, 4.0, 9.0]   # length = T×F = 6

# Real project: T=128, F=7 → length = 896
```

### S2-6 — HDFS Folder Structure (Confirmed)

```
hdfs://
├── raw_data/battery_telemetry_v4/{car_id}/
│     └── {car_id}_data_{YYYYMMDD}_{HHMMSS}.csv   ← raw stream
├── raw_sample_data/sampled_training/
│     ├── processed_registry.json                 ← incremental tracker
│     └── {car_id}_sampled_batch{N}.csv           ← sampler output
├── models/battery_health_ensemble/
│     ├── latest.json                             ← version pointer
│     └── v_{YYYYMMDD_HHmmss}/
│           ├── xgb_model_chg.json / scaler_chg.joblib
│           ├── xgb_model_drv.json / scaler_drv.joblib
│           └── ensemble_nn.pth
└── output_data/
      └── inference_ensemble_result_*.csv
```

### S2-7 — Images Generated (Session 2026-06-09)

Separate set of 8 images created by `docs/generate_math_images.py`:

| File | Content |
|---|---|
| `images/01_pipeline_overview.png` | End-to-end pipeline box diagram |
| `images/02_window_flatten.png` | (T×F) heatmap → 1D bar visual |
| `images/03_standardscaler.png` | Histogram before/after z-score normalisation |
| `images/04_xgboost_additive.png` | 6 panels — boosting convergence at rounds 0,1,5,20,100,299 |
| `images/05_ensemble_nn.png` | NN node diagram 2→32→16→1 with activation labels |
| `images/06_train_val_split.png` | Car-level snippet blocks coloured train/val |
| `images/07_meta_input.png` | Per-car scatter of XGB snippet predictions + mean lines |
| `images/08_final_prediction.png` | Line chart: GT vs XGB_chg vs XGB_drv vs EnsembleNN + RMSE |

> These images are referenced in `docs/math_analysis.md`.  
> To regenerate: `python src/AIAPI/docs/generate_math_images.py`

---

## Session 2026-06-21 — Data Quality & Anomaly Detection

> **Scope:** Local EDA (fg-data-profiling), data validation (Great Expectations),
> unsupervised anomaly detection (SOM). HDFS was inaccessible, so all work used a
> local export of the dataset.

### Environment (IMPORTANT)

- **Project venv:** `.venv` at repo root → `/Users/mac/Desktop/khaiworkplace/EV_Project/machineLearningEV/.venv`
  - Activate: `source .venv/bin/activate`
  - Has pandas 2.3.3, matplotlib 3.10.8, numpy. **Global `python3` has NO pandas** — always use the venv. `python` exists only inside the venv.
- **fg-data-profiling 4.19.1:** import name is `data_profiling`; needed `pip install "setuptools<81"` (provides `pkg_resources`).
- **Great Expectations 1.18.1** (GX Core): `import great_expectations as gx`, `from great_expectations import expectations as gxe`.
- **SOM:** `minisom` + `sklearn.preprocessing.MinMaxScaler`.
- **OS:** macOS, zsh.

### Local Dataset (`App/dataset/`)

- **`battery_telemetry_v4/{car_id}/*.csv`** — local export of raw telemetry.
  - 11 cars: EV_066, EV_101–EV_110. Focus: EV_104, EV_105, EV_109, EV_110.
  - **2,440 CSVs · 200,609 rows · 26 columns · 1,526 segments.**
  - Per-car rows/files: EV_066 = 1322/15 (smallest), EV_104 = 29016/359, EV_105 = 23368/315, EV_109 = 22995/315, EV_110 = 22658/313.
  - Sessions: 53,727 charging vs 146,882 driving. 0 duplicates. Nulls only in `vehicle_name` (20,542). `label` constant 0.
  - Numeric ranges: current_A −332→328, volt_V 205.5–445, soc_pct 5.32–100, actual_max_capacity 164–205, temps −4.8→65.
- **`output/`** — prediction CSVs.

### S3-1 — EDA via fg-data-profiling

- **Notebook:** `notebooks/eda_battery_telemetry.ipynb` — actually executed (not mock).
- **Reports → `App/dataset/eda_reports/`** (all real, generated):
  - `eda_full_report.html` (16.5 MB), `eda_compare_chg_drv.html` (14.8 MB), `eda_ts_EV_104.html` (8 MB), `eda_compare_focus_cars.html` (1.2 MB), `eda_predictions_report.html` (7.4 MB).
- **Two bugs fixed:**
  1. `compare()` instance method takes a single report → use module-level `from data_profiling import compare; compare([reports])`.
  2. 4-dataset comparison needs 4 colors → `PALETTE = ["#1f77b4","#ff7f0e","#2ca02c","#d62728"]` via `html={"style":{"primary_colors":PALETTE}}`.
- **Guide:** `App/src/AIAPI/docs/fg_data_profiling_guide.md` + 4 preview PNGs from `docs/generate_eda_preview_images.py` (eda_01_dataset_overview, eda_02_feature_distributions, eda_03_capacity_by_car, eda_04_prediction_error).

### S3-2 — Data Validation via Great Expectations

- **Script:** `App/src/AIAPI/data_quality/gx_battery_telemetry.py` — **33 expectations, all pass.**
  - 3 groups: **A** (ANALYSIS — schema/completeness/cardinality), **B** (CONSTRAINT — value sets / cross-field), **C** (LIMIT — physical bounds).
  - **Key gotcha:** create the context BEFORE building the suite. `build_suite()` returns `gx.ExpectationSuite(name=..., expectations=[list])`, then `context.suites.add(build_suite())`. Avoids `DataContextRequiredError`.
  - Output → `App/dataset/gx_results/validation_result.json`.
- **Guide:** `App/src/AIAPI/docs/great_expectations_guide.md` + 3 PNGs from `docs/generate_gx_images.py` (gx_01_workflow, gx_02_expectation_map, gx_03_validation_result).

### S3-3 — Anomaly Detection via SOM (Self-Organizing Map)

- **Reference impl:** `machineLearningA-Z/DL.P2.Self_Organizing_Map(SOM)/SOM.py`.
- **Script:** `App/src/AIAPI/data_quality/som_anomaly_detection.py`
  - Aggregates 200,609 rows → **1,526 segment vectors** (mean+std of 13 SIGNALS = 26 features), `MinMaxScaler`, `MiniSom 14×14` (σ=1.0, lr=0.5, 2000 iters, seed 42).
  - Anomaly score = **MID** (mean inter-neuron distance) of the winning neuron; threshold = p95.
  - SIGNALS: volt_V, current_A, soc_pct, avg_speed_kmh, motor_rpm, min_single_volt_V, max_single_volt_V, min_temp_C, max_temp_C, accelerator_pedal_pct, brake_pedal_pct, regenerative_braking_Ah, actual_max_capacity_Ah.
  - Outputs → `App/dataset/som_results/som_anomaly_ranking.csv` + 4 charts (som_01_distance_map, som_02_score_distribution, som_03_top_cases, som_04_feature_compare).
  - **Flagged 77 anomalies. Top case: EV_066 / DR101229_2 (score 1.000).**
- **Guide:** `App/src/AIAPI/docs/som_anomaly_detection_guide.md`.

### S3-4 — Worked Case Study: EV_066 / DR101229_2 (rank #1)

File: `App/dataset/battery_telemetry_v4/EV_066/EV_066_20260508_151315.csv`.
Compared target (128 rows) vs normal driving baseline (1,070 segments / 141,572 rows):

| Signal | DR101229_2 | Normal | Flag |
|---|---:|---:|---|
| min_single_volt_V | **2.08** (floored at 2.0 for 46% of rows) | 3.98 | 🔴 cell under-voltage |
| max_single_volt_V | 2.96 (min 2.70) | 4.14 | 🔴 strongest cell collapsing |
| volt_V (pack) | 296 (314→278) | 362 | 🔴 pack sagging |
| current_A | **151** (up to 191) | 67 | 🔴 ~2.3× normal |
| soc_pct | 93% | 66% | ⚠️ high SoC but voltage collapsing |
| accelerator_pedal_pct | 14% | 37% | ⚠️ low pedal, high current |

- **Diagnosis:** at 93% SoC the weakest cell is pinned at the 2.0 V floor while drawing 2–3× normal current at only 14% accelerator → classic **severely degraded / failing cell** (or voltage-sensor fault).
- **Key point:** GX min/max rules would MISS this — each individual value is within range; it's the **combination** that's abnormal, which is exactly what the SOM catches.
- `DR101229_1` (preceding segment, NOT flagged) keeps cells at 2.4–3.6 V — low but not floored.
- **Chart:** `App/src/AIAPI/docs/images/som_05_case_DR101229_2.png` (6-panel within-car time-series comparison).
- Documented as a "Worked case study" section in `som_anomaly_detection_guide.md`.
- EV_066 SoH = 193.72/210 = 92.2%.

### S3-5 — Lesson

User explicitly checked whether reports were actually generated (caught a case where docs claimed execution without output existing). **Always verify outputs exist on disk**, don't just write code/docs that claim to run.

### S3 Artifacts Map

| Path | Type |
|---|---|
| `notebooks/eda_battery_telemetry.ipynb` | fg-data-profiling EDA notebook |
| `App/dataset/eda_reports/*.html` | 5 generated EDA reports |
| `App/src/AIAPI/docs/fg_data_profiling_guide.md` + `generate_eda_preview_images.py` | EDA guide + 4 PNGs |
| `App/src/AIAPI/data_quality/gx_battery_telemetry.py` | GX — 33 expectations |
| `App/dataset/gx_results/validation_result.json` | GX output |
| `App/src/AIAPI/docs/great_expectations_guide.md` + `generate_gx_images.py` | GX guide + 3 PNGs |
| `App/src/AIAPI/data_quality/som_anomaly_detection.py` | SOM detector |
| `App/dataset/som_results/som_anomaly_ranking.csv` + 4 charts | SOM output |
| `App/src/AIAPI/docs/som_anomaly_detection_guide.md` | SOM guide + case study |
| `App/src/AIAPI/docs/images/som_05_case_DR101229_2.png` | Case-study chart |
