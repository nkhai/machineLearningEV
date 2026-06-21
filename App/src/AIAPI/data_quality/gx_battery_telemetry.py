"""
Great Expectations data-quality validation for battery_telemetry_v4.

Usage (from repo root, with .venv active):
    python App/src/AIAPI/data_quality/gx_battery_telemetry.py

What it does:
  1. Loads every CSV under App/dataset/battery_telemetry_v4/{car_id}/
  2. Builds an Expectation Suite grouped into 3 intents:
        A) ANALYSIS    — schema / completeness / cardinality (what to *measure*)
        B) CONSTRAINT  — value sets & cross-field rules (what must be *true*)
        C) LIMIT       — physical min/max bounds (what to *bound*)
  3. Runs a Checkpoint and prints a pass/fail summary
  4. Writes JSON results to App/dataset/gx_results/validation_result.json

GX version: 1.x (GX Core)
"""

import json
from pathlib import Path

import pandas as pd
import great_expectations as gx
from great_expectations import expectations as gxe

# ─────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────
HERE       = Path(__file__).resolve().parent
APP_ROOT   = HERE.parents[2]                      # .../App
TELEMETRY  = APP_ROOT / "dataset" / "battery_telemetry_v4"
RESULT_DIR = APP_ROOT / "dataset" / "gx_results"
RESULT_DIR.mkdir(exist_ok=True)

# Known valid domains (from dataset profiling)
KNOWN_CARS    = ["EV_066", "EV_101", "EV_102", "EV_103", "EV_104", "EV_105",
                 "EV_106", "EV_107", "EV_108", "EV_109", "EV_110"]
NOMINAL_SET   = [185.0, 210.0]
GEAR_SET      = ["D", "P"]
BINARY_SET    = [0, 1]

REQUIRED_COLUMNS = [
    "actual_max_capacity_Ah", "nominal_capacity_Ah", "car_id", "id_segment",
    "timestamp_s", "volt_V", "current_A", "soc_pct", "charger_connected",
    "min_single_volt_V", "max_single_volt_V", "min_temp_C", "max_temp_C",
    "motor_rpm", "avg_speed_kmh", "accelerator_pedal_pct", "brake_pedal_pct",
    "regenerative_braking_Ah", "payload_kg", "mileage_km", "hvac_active",
    "gear_position", "car_model",
]


# ─────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    files = sorted(TELEMETRY.rglob("*.csv"))
    print(f"Loading {len(files)} telemetry CSVs ...")
    df = pd.concat(
        [pd.read_csv(f, low_memory=False) for f in files],
        ignore_index=True,
    )
    print(f"Combined shape: {df.shape}")
    return df


def build_suite() -> gx.ExpectationSuite:
    expectations = []

    # ── A) ANALYSIS — schema, completeness, cardinality ──────────────────────
    # Are the expected columns present? (structural integrity)
    expectations.append(
        gxe.ExpectTableColumnsToMatchSet(
            column_set=REQUIRED_COLUMNS, exact_match=False, severity="critical"
        )
    )
    expectations.append(
        gxe.ExpectTableRowCountToBeBetween(min_value=1000, severity="warning")
    )
    # Key identity / label columns must never be null (completeness)
    for col in ["car_id", "id_segment", "actual_max_capacity_Ah",
                "nominal_capacity_Ah", "charger_connected", "timestamp_s"]:
        expectations.append(
            gxe.ExpectColumnValuesToNotBeNull(column=col, severity="critical")
        )
    # Exactly 11 cars expected in the dataset (cardinality)
    expectations.append(
        gxe.ExpectColumnUniqueValueCountToBeBetween(
            column="car_id", min_value=11, max_value=11, severity="warning"
        )
    )

    # ── B) CONSTRAINT — value sets & cross-field consistency ─────────────────
    expectations.append(
        gxe.ExpectColumnValuesToBeInSet(
            column="car_id", value_set=KNOWN_CARS, severity="critical"
        )
    )
    expectations.append(
        gxe.ExpectColumnValuesToBeInSet(
            column="nominal_capacity_Ah", value_set=NOMINAL_SET, severity="critical"
        )
    )
    expectations.append(
        gxe.ExpectColumnValuesToBeInSet(
            column="gear_position", value_set=GEAR_SET, severity="warning"
        )
    )
    for col in ["charger_connected", "hvac_active"]:
        expectations.append(
            gxe.ExpectColumnValuesToBeInSet(
                column=col, value_set=BINARY_SET, severity="critical"
            )
        )
    # Cross-field: per-cell min voltage must not exceed max voltage
    expectations.append(
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="max_single_volt_V", column_B="min_single_volt_V",
            or_equal=True, severity="critical",
        )
    )
    # Cross-field: min temp must not exceed max temp
    expectations.append(
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="max_temp_C", column_B="min_temp_C",
            or_equal=True, severity="critical",
        )
    )
    # Cross-field: degraded capacity can never exceed nominal capacity
    expectations.append(
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="nominal_capacity_Ah", column_B="actual_max_capacity_Ah",
            or_equal=True, severity="critical",
        )
    )

    # ── C) LIMIT — physical min/max bounds (sensor plausibility) ─────────────
    limits = {
        "soc_pct":                 (0, 100),
        "accelerator_pedal_pct":   (0, 100),
        "brake_pedal_pct":         (0, 100),
        "avg_speed_kmh":           (0, 200),
        "motor_rpm":               (0, 20000),
        "volt_V":                  (150, 500),       # pack voltage
        "min_single_volt_V":       (2.0, 4.6),       # cell voltage
        "max_single_volt_V":       (2.0, 4.6),       # cell voltage
        "min_temp_C":              (-40, 80),
        "max_temp_C":              (-40, 80),
        "current_A":               (-400, 400),      # +discharge / -charge
        "regenerative_braking_Ah": (0, 5),
        "payload_kg":              (0, 500),
        "mileage_km":              (0, 1_000_000),
        "actual_max_capacity_Ah":  (120, 210),       # SoH ~57%..100% of 210
        "timestamp_s":             (0, None),
    }
    for col, (lo, hi) in limits.items():
        kwargs = dict(column=col, severity="warning")
        if lo is not None:
            kwargs["min_value"] = lo
        if hi is not None:
            kwargs["max_value"] = hi
        expectations.append(gxe.ExpectColumnValuesToBeBetween(**kwargs))

    return gx.ExpectationSuite(
        name="battery_telemetry_v4_suite", expectations=expectations
    )


def main():
    df = load_data()

    # GX Core workflow: context must exist before building the suite
    context = gx.get_context()
    suite = context.suites.add(build_suite())
    print(f"Suite holds {len(suite.expectations)} expectations\n")

    batch = (
        context.data_sources.add_pandas("battery_pandas")
        .add_dataframe_asset(name="telemetry")
        .add_batch_definition_whole_dataframe("batch_def")
        .get_batch(batch_parameters={"dataframe": df})
    )

    results = batch.validate(suite)

    # ── Summary ──────────────────────────────────────────────────────────────
    print("=" * 64)
    print(f"OVERALL SUCCESS : {results.success}")
    stats = results.statistics
    print(f"Evaluated       : {stats['evaluated_expectations']}")
    print(f"Successful      : {stats['successful_expectations']}")
    print(f"Failed          : {stats['unsuccessful_expectations']}")
    print(f"Success %       : {stats['success_percent']:.1f}")
    print("=" * 64)

    print("\nFailed expectations:")
    any_failed = False
    for r in results.results:
        if not r.success:
            any_failed = True
            cfg = r.expectation_config
            col = cfg.kwargs.get("column", cfg.kwargs.get("column_A", "—"))
            pct = r.result.get("unexpected_percent", 0.0) or 0.0
            print(f"  [FAIL] {cfg.type:<48} col={col:<24} unexpected={pct:.3f}%")
    if not any_failed:
        print("  (none — all expectations passed)")

    out = RESULT_DIR / "validation_result.json"
    out.write_text(json.dumps(results.to_json_dict(), indent=2, default=str))
    print(f"\nFull JSON results → {out}")


if __name__ == "__main__":
    main()
