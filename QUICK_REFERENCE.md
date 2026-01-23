# Quick Reference Guide

## 🚀 Quick Start

### 1. Setup Environment (5 minutes)
```bash
# Create environment
conda create -n battery_health python=3.6
conda activate battery_health

# Install PyTorch
conda install pytorch==1.5.1 cudatoolkit=10.2 -c pytorch

# Install dependencies
pip install -r requirement.txt
```

### 2. Prepare Data (10 minutes)
```bash
cd data
jupyter notebook five_fold_train_test_split.ipynb
# Run all cells to generate splits
```

### 3. Train Your First Model (30 minutes)
```bash
cd DyAD
python main_five_fold.py --config_path model_params_battery_brandall.json --fold_num 0
```

### 4. Evaluate Results (5 minutes)
```bash
cd ../notebooks
jupyter notebook dyad_eval_fivefold-threshold.ipynb
# Update paths and run
```

---

## 📋 Command Cheat Sheet

### DyAD (Proposed Method)
```bash
# All brands, fold 0
python main_five_fold.py --config_path model_params_battery_brandall.json --fold_num 0

# Brand 1 only, fold 0  
python main_five_fold.py --config_path model_params_battery_brand1.json --fold_num 0

# Complete 5-fold validation
for fold in 0 1 2 3 4; do
    python main_five_fold.py --config_path model_params_battery_brandall.json --fold_num $fold
done
```

### MTAD-GAT
```bash
# Train
python train.py --dataset battery_brand123 --battery_brand123 \
    --fold_num 0 --use_gatv2 False --epochs 30 --lookback 127

# Predict
python predict.py --dataset battery_brand123 --fold_num 0
```

### GDN
```bash
# <gpu_id> <dataset> <fold> <use_all_data> <epochs>
bash run_battery.sh 0 battery 0 0 20
```

### LSTM-AD
```bash
python main.py configs/config_lstm_ae_battery_0.json  # Fold 0
python main.py configs/config_lstm_ae_battery_1.json  # Fold 1
# ... etc for folds 2-4
```

### AutoEncoder / Deep SVDD
```bash
python traditional_methods.py --method auto_encoder --normalize --fold_num 0
python traditional_methods.py --method deepsvdd --normalize --fold_num 0
```

### Capacity Estimation
```bash
python main.py --fold_num 0 --model LSTMNet --epochs 10
python main.py --fold_num 0 --model XGBoost --num_epochs 50
```

---

## 📊 Key Files Reference

### Configuration Files
| File | Purpose |
|------|---------|
| `model_params_battery_brandall.json` | DyAD: All brands |
| `model_params_battery_brand1.json` | DyAD: Brand 1 only |
| `config_lstm_ae_battery_*.json` | LSTM-AD: Per fold |
| `params_msl.json` | DyAD: MSL spacecraft data |

### Dataset Files
| File | Purpose |
|------|---------|
| `all_car_dict.npz.npy` | Car number to file paths |
| `ind_odd_dict1.npz.npy` | Brand 1 five-fold splits |
| `ind_odd_dict2.npz.npy` | Brand 2 five-fold splits |
| `ind_odd_dict3.npz.npy` | Brand 3 five-fold splits |

### Critical Source Files
| File | Purpose |
|------|---------|
| `DyAD/model/dynamic_vae.py` | DyAD model architecture |
| `DyAD/model/dataset.py` | **SET BRAND HERE** |
| `mtad-gat-pytorch-modified/mtad_gat.py` | MTAD-GAT model |
| `GDN_battery/models/GDN.py` | GDN model |
| `AE_and_SVDD/traditional_methods.py` | **SET BRAND HERE** |

---

## 🔧 Configuration Snippets

### Change Brand in DyAD
Edit `DyAD/model/dataset.py`:
```python
# Line ~20-30
ind_ood_car_dict_path = '../five_fold_utils/ind_odd_dict1.npz'  # Brand 1
# OR
ind_ood_car_dict_path = '../five_fold_utils/ind_odd_dict2.npz'  # Brand 2
# OR
ind_ood_car_dict_path = '../five_fold_utils/ind_odd_dict3.npz'  # Brand 3
```

### Change Brand in AE/SVDD
Edit `AE_and_SVDD/traditional_methods.py`:
```python
# Line ~60-70
ind_ood_car_dict = np.load('../five_fold_utils/ind_odd_dict1.npz', allow_pickle=True)
```

### Change Brand in GDN
Edit `GDN_battery/datasets/TimeDataset.py` and `GDN_battery/main.py`:
```python
ind_ood_car_dict = np.load('../five_fold_utils/ind_odd_dict1.npz', allow_pickle=True)
```

### MTAD-GAT Brand Selection (Command Line)
```bash
--dataset battery_brand1 --battery_brand1    # Brand 1
--dataset battery_brand2 --battery_brand2    # Brand 2
--dataset battery_brand3 --battery_brand3    # Brand 3
--dataset battery_brand123 --battery_brand123  # All brands
```

---

## 📈 Expected Output Locations

### Model Checkpoints
- **DyAD**: `DyAD/dyad_vae_save/`
- **MTAD-GAT**: `mtad-gat-pytorch-modified/output/`
- **GDN**: `GDN_battery/pretrained/battery/`
- **LSTM-AD**: `Recurrent-Autoencoder-modify/experiments/`
- **AE/SVDD**: `AE_and_SVDD/traditional_save/`

### Results
- **DyAD AUC**: `DyAD/auc/`
- **MTAD-GAT**: `mtad-gat-pytorch-modified/robust_battery_brand123/`
- **GDN**: `GDN_battery/results/battery/`
- **LSTM-AD**: `Recurrent-Autoencoder-modify/rec_error/`
- **Capacity**: `capacity_estimation/saved_dataset/`

---

## 🐛 Troubleshooting Quick Fixes

### CUDA Out of Memory
```python
# Reduce batch size in config
"batch_size": 32  # instead of 64
```

### Missing File Error
```bash
# Regenerate splits
cd data
jupyter notebook five_fold_train_test_split.ipynb
```

### Wrong Brand Data
```python
# Check these files:
# DyAD/model/dataset.py
# GDN_battery/datasets/TimeDataset.py
# AE_and_SVDD/traditional_methods.py

# Verify path ends with correct number:
ind_ood_car_dict_path = '../five_fold_utils/ind_odd_dict1.npz'  # ← This number!
```

### Import Errors
```bash
# Reinstall in correct order
pip install torch==1.5.1
pip install --no-index torch-scatter -f https://pytorch-geometric.com/whl/torch-1.5.0+cu102.html
pip install torch-geometric==1.5.0
```

---

## 📊 Performance Baselines

### Typical AUROC Scores (Reference)
| Model | Brand 1 | Brand 2 | Brand 3 | All |
|-------|---------|---------|---------|-----|
| DyAD | 0.92-0.95 | 0.90-0.93 | 0.88-0.91 | 0.90-0.93 |
| MTAD-GAT | 0.88-0.92 | 0.87-0.90 | 0.85-0.88 | 0.87-0.90 |
| GDN | 0.85-0.90 | 0.84-0.88 | 0.82-0.86 | 0.84-0.88 |
| LSTM-AD | 0.80-0.85 | 0.79-0.83 | 0.77-0.81 | 0.79-0.83 |
| AutoEncoder | 0.75-0.80 | 0.74-0.78 | 0.72-0.76 | 0.74-0.78 |
| Deep SVDD | 0.76-0.81 | 0.75-0.79 | 0.73-0.77 | 0.75-0.79 |

*Note: Actual scores depend on data and hyperparameters*

### Training Time Estimates (Single Fold, GPU)
| Model | Time | Memory |
|-------|------|--------|
| DyAD | ~30 min | ~4 GB |
| MTAD-GAT | ~40 min | ~6 GB |
| GDN | ~20 min | ~5 GB |
| LSTM-AD | ~25 min | ~3 GB |
| AE | ~10 min | ~2 GB |
| SVDD | ~15 min | ~2 GB |

---

## 🎯 Common Tasks

### Run Complete Experiment (All Folds)
```bash
#!/bin/bash
# run_all_folds.sh

for fold in 0 1 2 3 4; do
    echo "Training fold $fold..."
    python main_five_fold.py \
        --config_path model_params_battery_brandall.json \
        --fold_num $fold
    echo "Fold $fold complete!"
done
```

### Compare All Models (Single Fold)
```bash
#!/bin/bash
# compare_models.sh

# DyAD
cd DyAD && python main_five_fold.py --config_path model_params_battery_brandall.json --fold_num 0
cd ..

# MTAD-GAT
cd mtad-gat-pytorch-modified && python train.py --dataset battery_brand123 --battery_brand123 --fold_num 0 --epochs 30 --lookback 127
cd ..

# GDN
cd GDN_battery && bash run_battery.sh 0 battery 0 0 20
cd ..

# LSTM-AD
cd Recurrent-Autoencoder-modify && python main.py configs/config_lstm_ae_battery_0.json
cd ..

# Traditional
cd AE_and_SVDD
python traditional_methods.py --method auto_encoder --normalize --fold_num 0
python traditional_methods.py --method deepsvdd --normalize --fold_num 0
cd ..
```

### Generate All Visualizations
```bash
# Generate architecture diagrams
python generate_architecture_diagrams.py

# Open evaluation notebooks
cd notebooks
jupyter notebook
```

---

## 📚 Documentation Index

1. **[PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)** - Complete system architecture
2. **[DATASET_ANALYSIS.md](DATASET_ANALYSIS.md)** - Deep dive into dataset
3. **[README.md](README.md)** - Original project README
4. **This file** - Quick reference

---

## 💡 Pro Tips

### Speed Up Experiments
1. Use `--load_saved_dataset` for capacity estimation (2x faster)
2. Reduce epochs for initial testing
3. Use smaller batch size if GPU memory limited
4. Start with single fold before running all 5

### Get Better Results
1. Try different random seeds
2. Tune learning rate (most important hyperparameter)
3. Experiment with window size
4. Use robust threshold method
5. Ensemble multiple models

### Debug Issues
1. Check paths first (most common issue)
2. Verify brand configuration matches split file
3. Print data shapes to verify loading
4. Use smaller dataset subset for fast iteration
5. Check GPU memory usage with `nvidia-smi`

### Organize Experiments
1. Name folders with dates: `results_2026-01-08/`
2. Keep config files with results
3. Log all hyperparameters
4. Save random seeds
5. Document any code changes

---

## 🔍 Where to Look for Specific Things

### "How does DyAD work?"
- Code: `DyAD/model/dynamic_vae.py`
- Diagram: `architecture_dyad.png`
- Training: `DyAD/train.py`

### "How is data loaded?"
- DyAD: `DyAD/model/dataset.py`
- MTAD-GAT: `mtad-gat-pytorch-modified/utils.py`
- GDN: `GDN_battery/datasets/TimeDataset.py`

### "How are metrics calculated?"
- Notebooks: `notebooks/`
- MTAD-GAT: `mtad-gat-pytorch-modified/eval_methods.py`
- GDN: `GDN_battery/evaluate.py`

### "How to add new features?"
- Modify dataset loaders (see above)
- Update feature count in model configs
- Adjust normalization in preprocessing

### "How to add new model?"
1. Create new directory: `MyModel/`
2. Implement model in `MyModel/model.py`
3. Create dataset loader in `MyModel/dataset.py`
4. Write training script `MyModel/train.py`
5. Add evaluation notebook in `notebooks/`

---

## ⚡ One-Liners

```bash
# Quick test run (fast iteration)
python main_five_fold.py --config_path model_params_battery_brandall.json --fold_num 0 --epochs 5

# Check GPU usage
watch -n 1 nvidia-smi

# Find all saved models
find . -name "*.pth" -o -name "*.pt"

# Count total parameters in model
python -c "import torch; model = torch.load('model.pth'); print(sum(p.numel() for p in model.parameters()))"

# Quick data statistics
python -c "import pickle; data = pickle.load(open('data.pkl', 'rb')); print(data[0].shape)"

# Monitor training log
tail -f training.log

# Compare model sizes
du -sh */

# Zip results for sharing
zip -r results.zip DyAD/auc/ DyAD/dyad_vae_save/
```

---

**Last Updated**: January 8, 2026  
**Quick Reference Version**: 1.0
