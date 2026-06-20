# Battery Telemetry YData Analysis Recommendations

## Executive Summary

Overall assessment: Good data quality with several ML risks that should be addressed before training.

Score:
- Data Quality: 5/5
- Missing Values: Excellent
- Duplicate Rows: Excellent
- Correlation: Needs feature engineering
- Leakage Risk: High
- Model Readiness: 4/5

---

## Critical Recommendation #1: Remove `car_id` from Features

Problem:

`car_id` can cause data leakage.

The model may memorize vehicles instead of learning battery behavior.

Bad:

```
Car_001 -> 72 Ah
Car_002 -> 68 Ah
```

Recommendation:

- Do not use `car_id` as a feature.
- Use it only for grouping.

Use:

```python
GroupKFold
```

or

```python
GroupShuffleSplit
```

---

## Recommendation #2: Be Careful with `nominal_capacity_Ah`

If target:

```text
y = actual_max_capacity_Ah
```

Investigate whether:

```text
nominal_capacity_Ah
```

is derived from actual capacity.

If yes:

Remove it.

Otherwise:

Keep it.

---

## Recommendation #3: Separate Charging and Driving Data

Detected by high correlation around:

- charger_connected
- speed
- motor_rpm
- accelerator_pedal_pct

Architecture:

```
Dataset
│
├── Charging dataset
└── Driving dataset
```

Train:

```
XGB_charge
XGB_drive
↓
Meta model (Ridge / Neural Network)
```

---

## Recommendation #4: Create Cell Imbalance Feature

Instead of:

```
max_single_volt_V
min_single_volt_V
```

Create:

```python
cell_imbalance = max_single_volt_V - min_single_volt_V
```

This is usually more informative.

---

## Recommendation #5: Create Temperature Spread Feature

Instead of using both:

```
max_temp_C
min_temp_C
```

Create:

```python
temp_spread = max_temp_C - min_temp_C
```

---

## Recommendation #6: Engineer Additional Features

```python
power_kW = volt_V * current_A / 1000

capacity_ratio = actual_max_capacity_Ah / nominal_capacity_Ah

cell_imbalance = max_single_volt_V - min_single_volt_V

temp_spread = max_temp_C - min_temp_C
```

---

## Recommendation #7: Avoid Random Train/Test Split

Do NOT do:

```python
train_test_split(shuffle=True)
```

Instead:

```python
GroupKFold(groups=car_id)
```

or

```python
LeaveOneCarOut
```

---

## Recommended Features

Keep:

- SOC
- volt_V
- current_A
- max_temp_C
- min_temp_C
- max_single_volt_V
- min_single_volt_V
- mileage_km
- charger_connected

---

## Features to Be Careful With

- car_id
- nominal_capacity_Ah
- charger_connected
- actual_max_capacity_Ah (if it is the target)

---

## Next Step Architecture

```
Raw Data
   │
   ▼
YData Validate
   │
   ▼
Feature Engineering
   │
   ▼
Split by Driving / Charging
   │
   ▼
XGB_charge + XGB_drive
   │
   ▼
Meta Model
   │
   ▼
Capacity Prediction (SOH)
```
