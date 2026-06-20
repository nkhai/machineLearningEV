EV_BATTERY_CHARGING_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Charging Simulator.
Your goal is to generate HIGH-FIDELITY, NON-LINEAR telemetry data for a vehicle in CHARGING STATE.
You must simulate a "Real-World Charging Session" with grid instability, thermal throttling, and cable resistance variability.
Smooth, theoretical "textbook" charging curves are considered A HALLUCINATION FAILURE.

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (Python dict).
Each record must be a dict with EXACTLY 25 keys:

{{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}}

All values must be of the correct type. Do NOT include any extra text, comments, or arrays outside the JSON object.

HARD NUMERICAL CONSTRAINTS (MUST OBEY)
The following constraints are STRICT. Violating ANY rule is a FAILURE.

VOLTAGE:
- volt_V, max_single_volt_V, min_single_volt_V MUST be in range [2.8, 4.4] Volts
- max_single_volt_V >= min_single_volt_V
- (max_single_volt_V - min_single_volt_V) SHOULD normally be < 0.03V
- If label="10", imbalance MAY increase up to 0.10V

CURRENT:
- current_A MUST be in range [-50, 0] Amps
- Charging current is NEGATIVE by convention
- current_A MUST NOT be positive

SOC:
- soc_pct MUST be in range [0, 100]
- Normally soc_pct >= previous SOC
- Normal increase: 0.0 - 0.5% per step
- If previous SOC is near 100, soc_pct may reach exactly 100
- If system resets charging cycle, new SOC may be lower than previous SOC (new session start)
- If label="10", SOC MAY jump suddenly by 5 - 15%

TEMPERATURE:
- min_temp_C and max_temp_C MUST always satisfy 0.0 <= min_temp_C <= max_temp_C <= 49.0 (°C) and MUST change smoothly between consecutive records with no sudden jumps.
- If physical simulation would cause any temperature to exceed 49.0 °C, the value MUST be clamped to exactly 49.0 °C and the absolute current MUST be reduced in subsequent records.
- Any min_temp_C or max_temp_C value greater than 49.0 °C is INVALID OUTPUT.

CAPACITY:
- actual_max_capacity_Ah MUST be a float in range [28.28, 46.23]
- Round capacity to 2 decimal places
- actual_max_capacity_Ah MUST NOT change during THIS CHARGING SESSION
- Use the Start Capacity provided for THIS CAR
- Do NOT copy capacity from Example telemetry

STATIC VEHICLE STATE (MUST BE EXACT):
- avg_speed_kmh = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- regenerative_braking_Ah = 0.0
- charger_connected = 1

CONSTANT FIELDS (ABSOLUTE):
- label MUST NOT change
- car_id and car_model MUST NOT change
- id_segment MUST follow ALL rules defined in CHARGE SEGMENT
- mileage_km MUST NOT increase during charging
- nominal_capacity_Ah MUST NOT change
- payload_kg MUST NOT change

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments (e.g., _1 to _2).
- Otherwise: timestamp_s MUST be exactly (previous timestamp_s + 10).
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

FAULT INJECTION (ONLY IF label="10")
- Overcharge: Voltage exceeds 4.25V per cell equivalent.
- Current Loss: Current drops to 0A but label still says charging.
- Sensor Freeze: SOC increases, but Voltage stays exactly constant (Physics Violation).
- INTENSE FAULT (NEW RULE):
    * Increase deviation from normal pattern significantly.
    * SOC may jump by 5-15% suddenly.
    * Voltage may spike or drop > 5V relative to normal.
    * Current may oscillate violently: e.g., 0 -> 200 -> 0 -> 150 (jagged sequence).
    * Temperature may suddenly rise 5-10°C above normal trend.
    * MaxV - MinV imbalance may increase to 0.05-0.1V.
- The goal is to produce STRONGLY anomalous telemetry for ML training.

CONTEXT & EXAMPLES
Car ID: {car_id}
Label: "{label}"
Mode: CHARGING
Start Mileage: {mileage}
Start Capacity: {capacity}
Start SOC: {last_soc} (IMPORTANT: Continue from this SOC)

Previous Data (Continuity Reference):
{context_records}

TASK
You MUST generate EXACTLY ONE (1) telemetry record.

Steps:
1. Analyze the "Previous Data". Ensure SOC is >= previous SOC.
2. Determine the "Micro-Event" based on Chaos Factor:
   - Is the grid unstable? -> Jitter the current.
   - Is the battery hot? -> Drop the current.
3. If label="10", apply INTENSE FAULT rules to deviate strongly from normal patterns.
4. Calculate Voltage based on V = OCV + IR logic.
5. Self-check (MANDATORY):
   - Any value out of allowed range? -> REJECT and regenerate
   - Is current > 0? -> REJECT
   - Is soc < previous soc? -> REJECT
   - Is mileage increased? -> REJECT
   - Are values too smooth / linear? -> Add realistic noise
6. Output:
   - JSON ONLY
   - A SINGLE record (not an array)
"""


EV_BATTERY_SLEEP_MODE_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Simulator.
Generate HIGH-FIDELITY telemetry data for a vehicle in SLEEP MODE.

Vehicle condition:
- Engine OFF, locked, parked
- HV battery disconnected
- Only 12V system + BMS active

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (Python dict).

Each record MUST contain EXACTLY these fields in this order:

{{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}}

NO extra text. NO Markdown blocks.

HARD NUMERICAL CONSTRAINTS

VOLTAGE:
- volt_V, max_single_volt_V, min_single_volt_V in [3.8, 4.1]
- max_single_volt_V >= min_single_volt_V
- imbalance (max - min) < 0.03V

CURRENT:
- current_A in [0.0, 0.5]
- MUST be small positive (12V standby only)

SOC:
- soc_pct in [20, 100]
- SOC MUST either stay EXACTLY the same OR decrease VERY SLIGHTLY
- Allowed change: 0 or between -0.005 and -0.02 ONLY
- SOC MUST NOT increase under any condition

TEMPERATURE:
- min_temp_C, max_temp_C in [20, 35]
- Change MUST be <= 0.1°C vs previous record

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s MUST be exactly (previous timestamp_s + 10).
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

STATIC VEHICLE STATE (MUST BE EXACT)
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0.0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 0

IDENTITY & CONSTANT FIELDS (COPY FROM PREVIOUS RECORD)
The following fields MUST remain EXACTLY the same:
- payload_kg
- nominal_capacity_Ah (~ 215.0 for VF8)
- actual_max_capacity_Ah
- car_model (MUST be "SimuProA")
- car_id
- label
- mileage_km
- id_segment

ID GENERATION
- id MUST be unique (e.g., previous id + 1)

TEMPORAL CONSISTENCY (MICRO-STEP STRICT)
The new record MUST be nearly identical to the previous record.

STRICT DELTA LIMITS:
- volt_V difference <= 0.003
- current_A difference <= 0.03
- soc_pct difference in [0, -0.02]
- temperature difference <= 0.1°C

PROHIBITED:
- Any noticeable trend
- Any oscillation pattern
- Any jump larger than defined limits

REALISM RULES (ULTRA-MICRO VARIATION)
Sleep mode requires EXTREMELY SMALL changes.

Apply MINIMAL sensor noise:

- volt_V:
  * Change within +/-0.001 - 0.003 ONLY
  * No directional trend

- current_A:
  * Change within +/-0.01 - 0.03
  * Small random jitter only

- soc_pct:
  * 0 or -0.005 to -0.02 ONLY

- max_temp_C, min_temp_C:
  * Change within +/-0.05 - 0.1°C ONLY
  * Extremely slow evolution

- max_single_volt_V & min_single_volt_V:
  * Follow volt_V closely
  * Stable imbalance

CRITICAL:
- Data must look almost constant but NOT flat
- No visible trend across steps

CONTEXT
Previous Data:
{context_records}

TASK
Generate EXACTLY ONE telemetry record.

Steps:
1. Copy all constant fields from previous record.
2. Increase timestamp_s by exactly +10 (or reset if 1270).
3. Apply ultra-small noise to volt and current.
4. Slightly decrease or keep SOC constant.
5. Adjust temperature smoothly.
6. Ensure all constraints are satisfied.

FINAL CHECK:
- Out of range -> REJECT
- Any jump -> REJECT
- Any trend -> REJECT

OUTPUT:
- JSON ONLY
- SINGLE record
"""

EV_BATTERY_STANDBY_MODE_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Simulator.
Generate HIGH-FIDELITY telemetry data for a vehicle in STANDBY MODE.

Vehicle condition:
- Vehicle is parked (not moving)
- HV battery is STILL CONNECTED
- Low-level systems are active (ECU, BMS, electronics)
- Small but continuous power consumption exists

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (Python dict).

Each record MUST contain EXACTLY these fields in this order:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

NO extra text.

HARD NUMERICAL CONSTRAINTS

VOLTAGE:
- volt_V in [3.8, 4.1]
- Small fluctuation ONLY: +/-0.002 - 0.006
- Voltage MUST slightly decrease when current increases

CURRENT:
- current_A in [1.0, 3.0]
- MUST be positive
- Fluctuation: +/-0.1 - 0.3
- No spikes or oscillation

SOC:
- soc_pct in [20, 100]

- SOC MUST decrease over time BUT NOT at a constant rate

- Allowed change per step:
  * Randomly chosen from: {0, -0.01, -0.02, -0.03, -0.04, -0.05}

- CRITICAL:
  * MUST NOT repeat the same delta more than 2 consecutive steps
  * MUST include occasional "no change" steps (0 delta)
  * MUST vary step size randomly

- TREND:
  * Overall SOC must slowly decrease
  * Individual steps must be irregular (non-linear)

TEMPERATURE:
- min_temp_C, max_temp_C in [20, 35]
- Change <= 0.3°C
- Smooth evolution only
- Slight increase possible when current is higher

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s MUST be exactly (previous timestamp_s + 10).
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

STATIC VEHICLE STATE (MUST BE EXACT)
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 0

IDENTITY & CONSTANT FIELDS (COPY FROM PREVIOUS RECORD)
- payload_kg constant
- nominal_capacity_Ah in [90, 120]
- actual_max_capacity_Ah constant
- car_model MUST be "SimuProA"
- car_id constant
- label constant
- mileage_km constant
- id_segment constant

ID GENERATION
- id MUST be unique (e.g., previous id + 1)

TEMPORAL CONSISTENCY (STRICT)
Compared to previous record:

- volt change <= 0.006
- current change <= 0.3
- temperature change <= 0.3°C

CORRELATION RULES:
- Higher current -> slightly lower voltage
- Higher current -> slightly higher temperature
- Lower current -> voltage stabilizes or increases slightly

REALISM RULES
- Data MUST NOT be flat
- Data MUST NOT follow linear pattern
- Data MUST NOT oscillate (zig-zag)

- Add small sensor noise:
  * Voltage noise
  * Current jitter
  * Temperature drift

- Each step must look like real sensor reading

INVALID PATTERNS:
- Constant SOC drop (-0.02, -0.02, -0.02)
- Perfect linear trend
- Strong oscillation

CONTEXT
Previous Data:
{context_records}

TASK
Generate EXACTLY ONE telemetry record.

Steps:
1. Copy all constant fields from previous record
2. Increase timestamp_s by exactly +10 (or reset if 1270)
3. Apply small noise to volt and current
4. Decrease SOC using irregular step (or keep constant)
5. Adjust temperature smoothly
6. Maintain all correlations

FINAL CHECK:
- Out of range -> REJECT
- SOC increase -> REJECT
- Repeated SOC delta -> REJECT
- Any unrealistic jump -> REJECT

OUTPUT:
- JSON ONLY
- SINGLE record
"""


EV_BATTERY_PARKED_HVAC_ON_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Simulator.
Generate HIGH-FIDELITY telemetry data for a vehicle in PARKED WITH HVAC ON mode.

Vehicle condition:
- Vehicle is parked (not moving)
- HV battery is supplying power
- HVAC system is ACTIVE (cooling or heating)
- Moderate and fluctuating power consumption exists

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (Python dict).

Each record MUST contain EXACTLY these fields in this order:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

NO extra text.

HARD NUMERICAL CONSTRAINTS

CURRENT:
- current_A in [5, 20]
- MUST fluctuate (compressor cycles)
- Change per step: +/-1 - 5A
- MUST NOT be constant

VOLTAGE:
- volt_V in [3.8, 4.1]
- Change <= +/-0.015
- MUST decrease slightly when current increases

SOC:
- soc_pct in [20, 100]

- MUST decrease over time

- Allowed change per step:
  * Randomly chosen from: {-0.02, -0.03, -0.04, -0.05, -0.06, -0.07, -0.08}

- CRITICAL:
  * MUST NOT repeat same delta > 2 times
  * MUST vary irregularly
  * Larger current -> larger SOC drop

TEMPERATURE:
- max_temp_C in [25, 35]
- min_temp_C in [20, 30]

- Change per step <= 0.5°C
- Should show gradual upward trend

CELL VOLTAGE:
- max_single_volt_V in [3.8, 4.1]
- min_single_volt_V in [3.79, 4.09]
- imbalance < 0.03

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s MUST be exactly (previous timestamp_s + 10).
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

STATIC VEHICLE STATE
- avg_speed_kmh = 0
- hvac_active = 1
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 0

IDENTITY & CONSTANT FIELDS
- payload_kg constant
- nominal_capacity_Ah constant
- actual_max_capacity_Ah constant
- car_model = "SimuProA"
- car_id constant
- label constant
- mileage_km constant
- id_segment constant

TEMPORAL CONSISTENCY
Compared to previous record:

- current change <= 5A
- volt change <= 0.015
- temp change <= 0.5°C

CORRELATION RULES:
- Higher current -> lower voltage
- Higher current -> higher temperature
- Higher current -> larger SOC decrease

REALISM RULES
- Current MUST fluctuate (compressor behavior)
- No flat current
- No linear SOC drop
- No oscillation pattern

- Data must reflect:
  * active power consumption
  * thermal buildup
  * realistic battery behavior

CONTEXT
Previous Data:
{context_records}

TASK
Generate EXACTLY ONE telemetry record.

Steps:
1. Copy constant fields
2. Increase timestamp_s by exactly +10 (or reset if 1270)
3. Simulate fluctuating current
4. Adjust voltage inversely with current
5. Decrease SOC (irregular step)
6. Increase temperature smoothly

FINAL CHECK:
- SOC increase -> REJECT
- Current flat -> REJECT
- Pattern linear -> REJECT

OUTPUT:
- JSON ONLY
- SINGLE record
"""



EV_BATTERY_AC_CHARGING_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Charging Simulator.

Generate HIGH-FIDELITY telemetry data for an electric vehicle under AC charging mode.
The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- AC charger connected
- Charging via onboard charger (OBC)
- Charging follows CC -> CV behavior

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct in [15, 30]
- current_A in [-48, -16]
- volt_V in [3.85, 4.15]
- max_single_volt_V in [3.86, 4.16]
- min_single_volt_V in [3.85, 4.15]
- max_temp_C in [25, 35]
- min_temp_C in [20, 30]

INITIALIZATION CONSISTENCY RULES
Initial values MUST satisfy:

- SOC must be low-to-mid range (NOT near 100)
- current_A must be negative (charging state)
- Higher SOC -> slightly higher voltage
- Voltage must not be unrealistically high at low SOC

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.05

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp should be 2 - 6°C

Correlation:
- Higher current magnitude -> slightly higher temperature

INITIALIZATION ANTI-PATTERNS (FORBIDDEN)
- soc_pct >= 80 at first timestep
- current_A >= 0
- voltage inconsistent with SOC
- max_single_volt_V = min_single_volt_V
- temperature gap > 10°C

PHYSICS & BEHAVIOR RULES
- SOC must increase over time
- Current must be negative (charging)
- Voltage must increase with SOC
- Temperature must increase slightly with current magnitude
- System must follow CC -> CV charging profile:
  * CC phase: current relatively stable, SOC increases faster
  * CV phase: voltage stabilizes, current magnitude decreases

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve NON-LINEARLY:

- NO constant step increments
- NO linear trends
- NO repeated identical deltas

Each timestep MUST have different delta values.

SOC:
- Delta chosen randomly from:
  {{+0.03, +0.05, +0.07, +0.09}}
- Changes must be extremely small and gradual
- SOC must increase very slowly over time

- When SOC > 80%:
  Delta must reduce to:
  {{+0.002, +0.003, +0.004}}

- When SOC > 90%:
  Delta must reduce further to:
  {{+0.001, +0.002}}

CURRENT:
- Delta randomly in range [-0.2, +0.2]
- When current magnitude is near minimum of AC charge:
  Delta must allow small oscillations only (no big decrease)
- Overall trend must decrease (magnitude reduces)
- Must include irregular fluctuations

VOLTAGE:
- Delta randomly within +/-0.0015
- Must increase with SOC but not linearly
- When voltage reaches AC max (OBC limit):
  Maintain plateau with small random oscillations +/-0.001
- Must show plateau behavior at high SOC

TEMPERATURE:
- Must change smoothly with small fluctuations (both increase and decrease)
- Correlates with current: higher current -> tends to increase, lower current -> stabilize or decrease
- Includes cooling effect: at high temperature (>40°C), may slightly decrease
- Must not increase continuously; should fluctuate within a realistic range (25 - 45°C)
- Delta per step within [-0.2, +0.3] °C with small oscillations

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

For each timestep:

1. Each feature MUST have independent noise.

2. Noise generation:
   - Base noise sampled from Gaussian distribution (mean = 0)
   - Standard deviation is dynamic per timestep:
     * SOC: 0.005 - 0.02
     * Voltage: 0.002 - 0.01
     * Current: 0.2 - 1.5
     * Temperature: 0.05 - 0.3

3. Noise characteristics:
   - Non-uniform
   - Non-repetitive
   - Slightly asymmetric (not perfectly balanced)
   - Different across features and timesteps

4. Micro-shock behavior:
   - Every 2 - 4 timesteps, introduce a slightly larger deviation

5. Temporal correlation:
   - Noise should have slight memory

6. MUST avoid:
   - Identical noise across timesteps
   - Constant noise amplitude
   - Uniform jitter patterns

ANTI-PATTERN RULES (CRITICAL)
- No feature may change with constant delta
- No repeated delta more than 2 consecutive steps
- No linear sequences

CORRELATION RULES
- SOC ↑ -> Voltage ↑
- SOC ↑ -> Current magnitude ↓
- Current magnitude ↑ -> Temperature ↑
- Voltage may slightly dip when current spikes

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record that satisfies all rules.

FINAL OUTPUT:
- JSON only
- Single record
"""

EV_BATTERY_V2L_V2G_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Discharging Simulator.

Generate HIGH-FIDELITY telemetry data for an electric vehicle under V2L / V2G mode (power export).

The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- External load connected (V2L) or grid export (V2G)
- Battery is DISCHARGING to supply power
- Vehicle acts as a mobile power source

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct in [20, 100]
- current_A in [+10, +15]
- volt_V in [3.7, 4.0]
- max_single_volt_V in [3.7, 4.0]
- min_single_volt_V in [3.69, 3.99]
- max_temp_C in [25, 35]
- min_temp_C in [20, 30]

INITIALIZATION CONSISTENCY RULES
- SOC must NOT be too low (<20%)
- current_A must be POSITIVE (discharging state)
- Higher SOC -> slightly higher voltage
- Voltage must stay within realistic discharge range

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.05

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp should be 2 - 6°C

Correlation:
- Higher current -> slightly higher temperature

PHYSICS & BEHAVIOR RULES
- SOC must DECREASE over time
- Current must be POSITIVE (power output)
- Voltage must gradually decrease with SOC
- Temperature correlates with current magnitude

- System behavior:
  * Load demand causes current draw fluctuations
  * Voltage slightly drops under higher current
  * SOC decreases slowly over time

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve NON-LINEARLY:

- NO constant step increments
- NO linear trends
- NO repeated identical deltas

SOC:
- Delta chosen from:
  {-0.01, -0.02, -0.03}
- Must decrease slowly and non-linearly

CURRENT:
- Delta randomly in range [-0.5, +0.5]
- Must fluctuate based on load demand
- No monotonic trend required

VOLTAGE:
- Delta randomly within +/-0.002
- Must decrease with SOC but not linearly
- Slight dips when current increases

TEMPERATURE:
- Must change smoothly with small fluctuations (both increase and decrease)
- Correlates with current: higher current -> tends to increase
- Cooling effect may reduce temperature slightly
- Range typically between 25°C - 40°C
- Delta per step within [-0.2, +0.3] °C

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

- SOC noise: 0.001 - 0.005
- Voltage noise: 0.0005 - 0.002
- Current noise: 0.05 - 0.5
- Temperature noise: 0.02 - 0.1

Noise must be:
- Non-uniform
- Non-repetitive
- Slightly asymmetric
- Temporally correlated

CORRELATION RULES
- SOC ↓ -> Voltage ↓
- Current ↑ -> Voltage slight drop
- Current ↑ -> Temperature ↑

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record.

FINAL OUTPUT:
- JSON only
- Single record
"""

EV_BATTERY_DC_FAST_CHARGING_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Fast Charging Simulator.

Generate HIGH-FIDELITY telemetry data for an electric vehicle under DC fast charging mode.

The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- Connected to DC fast charging station
- Charging bypasses onboard charger (OBC)
- High power DC injected directly into battery
- Charging follows CC -> CV behavior (fast charge up to ~80%)

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct in [10, 40]
- current_A in [-500, -150]
- volt_V in [3.9, 4.18]
- max_single_volt_V in [3.95, 4.19]
- min_single_volt_V in [3.85, 4.1]
- max_temp_C in [35, 45]
- min_temp_C in [30, 35]

INITIALIZATION CONSISTENCY RULES
- SOC must be low-to-mid range (NOT near 100)
- current_A must be strongly negative (fast charging)
- Higher SOC -> slightly higher voltage
- Voltage must remain within safe high-voltage charging range

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.06

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp should be 3 - 8°C

Correlation:
- Higher current magnitude -> higher temperature

PHYSICS & BEHAVIOR RULES
- SOC must increase over time
- Current must be negative (charging)
- Voltage must increase with SOC
- Temperature increases due to high current load

- Charging behavior:
  * CC phase (SOC < ~70 - 80%):
      - Current remains high and relatively stable
      - SOC increases faster
  * CV phase (SOC > ~80%):
      - Voltage stabilizes near upper limit
      - Current magnitude decreases rapidly

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve NON-LINEARLY:

- NO constant step increments
- NO linear trends
- NO repeated identical deltas

SOC:
- Delta chosen randomly from:
  {+0.08, +0.1, +0.12, +0.15}
- Must increase faster than AC charging

- When SOC > 80%:
  Delta must reduce to:
  {+0.01, +0.02, +0.03}

CURRENT:
- Delta randomly in range [-20, +10]
- Must stay high in CC phase
- Must decrease sharply in CV phase
- Must include irregular fluctuations

VOLTAGE:
- Delta randomly within +/-0.003
- Must increase with SOC
- When reaching upper limit (~4.18V):
  Maintain plateau with small oscillations

TEMPERATURE:
- Must change smoothly with fluctuations (increase & decrease)
- Strongly correlated with high current
- May decrease slightly due to cooling system
- Range typically between 30°C - 50°C
- Delta per step within [-0.3, +0.5] °C

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

- SOC noise: 0.01 - 0.03
- Voltage noise: 0.001 - 0.005
- Current noise: 2 - 10
- Temperature noise: 0.1 - 0.5

Noise must be:
- Non-uniform
- Non-repetitive
- Slightly asymmetric
- Temporally correlated

CORRELATION RULES
- SOC ↑ -> Voltage ↑
- SOC ↑ -> Current magnitude ↓ (especially in CV phase)
- Current magnitude ↑ -> Temperature ↑
- Voltage may dip slightly when current spikes

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record.

FINAL OUTPUT:
- JSON only
- Single record
"""

EV_BATTERY_DC_FAST_CHARGING_COLD_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Fast Charging Simulator under EXTREME COLD conditions.

Generate HIGH-FIDELITY telemetry data for an electric vehicle under DC fast charging in very low temperature (<5°C).

The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- Connected to DC fast charging station
- Ambient temperature is very low (<5°C)
- Battery Management System (BMS) limits charging current initially
- PTC heater is activated to warm up battery
- Charging behavior transitions as battery warms up

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct in [10, 40]
- current_A in [-80, -40]
- volt_V in [3.8, 4.1]
- max_single_volt_V in [3.82, 4.12]
- min_single_volt_V in [3.8, 4.1]
- max_temp_C in [5, 15]
- min_temp_C in [-5, 5]

INITIALIZATION CONSISTENCY RULES
- current_A must be negative (charging)
- Current must be LIMITED compared to normal DC fast charging
- Temperature must be LOW initially
- Voltage must be consistent with SOC and low temperature conditions

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.05

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp: 3 - 10°C

PHYSICS & BEHAVIOR RULES
- SOC must increase over time (slow initially)
- Current must be negative but LIMITED at low temperature
- Voltage increases slowly with SOC

- Cold charging behavior:
  * At very low temperature:
      - Charging current is restricted by BMS
      - SOC increases very slowly
      - Temperature increases gradually due to heating system
  * As temperature rises:
      - Current magnitude may gradually increase
      - Charging becomes more efficient

- Heating system behavior:
  * Battery temperature should gradually increase over time
  * Heating may cause temperature rise even if current is low

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve NON-LINEARLY:

SOC:
- Delta chosen from:
  {+0.005, +0.01, +0.015}
- Must increase very slowly at low temperature

CURRENT:
- Delta randomly in range [-5, +5]
- Must remain limited (no high magnitude like normal DC)
- May increase slightly as temperature rises

VOLTAGE:
- Delta randomly within +/-0.002
- Must increase slowly and smoothly

TEMPERATURE:
- Must gradually increase due to heating system
- May slightly fluctuate but overall trend is increasing
- Delta per step within [-0.1, +0.4] °C
- Must not jump abruptly

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

- SOC noise: 0.001 - 0.005
- Voltage noise: 0.0005 - 0.002
- Current noise: 0.5 - 3
- Temperature noise: 0.05 - 0.2

Noise must be:
- Non-uniform
- Non-repetitive
- Slightly asymmetric
- Temporally correlated

CORRELATION RULES
- Temperature ↑ -> Current capability ↑
- Current ↑ -> Temperature ↑
- SOC ↑ -> Voltage ↑
- Low temperature -> low current -> slow SOC increase

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 1  (heating system active)
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record.

FINAL OUTPUT:
- JSON only
- Single record
"""


EV_BATTERY_DC_FAST_CHARGING_HOT_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Fast Charging Simulator under EXTREME HOT conditions.

Generate HIGH-FIDELITY telemetry data for an electric vehicle under DC fast charging in very high temperature (>35°C).

The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- Connected to DC fast charging station
- Ambient temperature is very high (>35°C)
- Battery temperature is near critical threshold
- Battery Management System (BMS) actively throttles charging current
- Cooling system (AC compressor) runs at maximum capacity

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct in [10, 50]
- current_A in [-150, -50]
- volt_V in [3.85, 4.1]
- max_single_volt_V in [3.86, 4.12]
- min_single_volt_V in [3.85, 4.1]
- max_temp_C in [45, 55]
- min_temp_C in [40, 45]

INITIALIZATION CONSISTENCY RULES
- current_A must be negative (charging)
- Current must be LOWER than normal DC fast charging due to thermal throttling
- Temperature must be HIGH initially
- Voltage must remain within safe range

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.05

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp: 3 - 8°C

PHYSICS & BEHAVIOR RULES
- SOC must increase over time (slower than normal DC)
- Current must be negative but LIMITED due to overheating
- Voltage increases slowly with SOC

- Hot charging behavior:
  * When temperature is high:
      - BMS reduces charging current (throttling)
      - SOC increases slower than normal
  * Cooling system tries to reduce temperature:
      - Temperature may stabilize or decrease slightly
      - Cooling effect competes with heat from charging

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve NON-LINEARLY:

SOC:
- Delta chosen from:
  {+0.02, +0.03, +0.04}
- Must increase slower than normal DC charging

CURRENT:
- Delta randomly in range [-10, +5]
- Must remain limited (no extreme high magnitude)
- May decrease further if temperature increases
- May slightly recover if temperature drops

VOLTAGE:
- Delta randomly within +/-0.002
- Must increase with SOC
- May plateau near upper limit

TEMPERATURE:
- Must fluctuate (increase & decrease)
- High temperature triggers cooling response
- Cooling system may reduce temperature slightly
- Must not continuously increase
- Typical range: 40°C - 55°C
- Delta per step within [-0.3, +0.3] °C

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

- SOC noise: 0.005 - 0.02
- Voltage noise: 0.001 - 0.003
- Current noise: 1 - 5
- Temperature noise: 0.05 - 0.2

Noise must be:
- Non-uniform
- Non-repetitive
- Slightly asymmetric
- Temporally correlated

CORRELATION RULES
- Temperature ↑ -> Current ↓ (BMS throttling)
- Temperature ↓ -> Current may slightly increase
- SOC ↑ -> Voltage ↑
- Current ↑ -> Temperature ↑

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 1  (cooling system active at max)
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record.

FINAL OUTPUT:
- JSON only
- Single record
"""

EV_BATTERY_NEAR_FULL_CHARGING_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Charging Simulator in NEAR-FULL state.

Generate HIGH-FIDELITY telemetry data for an electric vehicle when battery is nearly full (SOC 80% - 99%).

The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- Charger connected
- Battery is in CV (Constant Voltage) phase
- Charging current is actively reduced by BMS to protect battery

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct in [80, 95]
- current_A in [-50, -5]
- volt_V in [4.15, 4.19]
- max_single_volt_V in [4.16, 4.2]
- min_single_volt_V in [4.15, 4.19]
- max_temp_C in [30, 40]
- min_temp_C in [30, 35]

INITIALIZATION CONSISTENCY RULES
- SOC must be high (>=80%)
- current_A must be negative and small magnitude
- Voltage must be near maximum and stable

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.03

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp: 2 - 5°C

PHYSICS & BEHAVIOR RULES
- SOC must increase VERY slowly
- Current must be negative but decreasing in magnitude
- Voltage must remain nearly constant (CV behavior)

- CV phase behavior:
  * Voltage is held near maximum
  * Current gradually tapers down
  * SOC increases slowly and asymptotically

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve NON-LINEARLY:

SOC:
- Delta chosen from:
  {+0.002, +0.003, +0.004}
- When SOC > 90%:
  {+0.001, +0.002}
- Must increase very slowly

CURRENT:
- Delta randomly in range [+1, +5]
- Current magnitude must gradually reduce (toward 0)
- Must include small oscillations

VOLTAGE:
- Delta randomly within +/-0.001
- Must stay near upper limit
- Must show plateau behavior

TEMPERATURE:
- Must fluctuate smoothly (increase & decrease)
- Slightly correlated with current
- Should remain stable (30°C - 40°C)
- Delta per step within [-0.2, +0.2] °C

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

- SOC noise: 0.001 - 0.005
- Voltage noise: 0.0005 - 0.002
- Current noise: 0.5 - 2
- Temperature noise: 0.02 - 0.1

Noise must be:
- Non-uniform
- Non-repetitive
- Slightly asymmetric
- Temporally correlated

CORRELATION RULES
- SOC ↑ -> Current magnitude ↓
- SOC ↑ -> Voltage plateau
- Current ↑ -> slight temperature increase

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record.

FINAL OUTPUT:
- JSON only
- Single record
"""

EV_BATTERY_FULLY_CHARGED_PROMPT = """
SYSTEM ROLE
You are an Advanced EV Battery Simulator in FULLY CHARGED state.

Generate HIGH-FIDELITY telemetry data for an electric vehicle when battery is fully charged (SOC = 100%).

The data must closely resemble real-world sensor measurements with natural fluctuations.

Vehicle state:
- Parked vehicle (gear P)
- Charger connected
- Battery is fully charged (SOC = 100%)
- BMS has stopped charging current (no energy intake)
- System is in idle / maintenance state

OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON object (no explanation).

Each record MUST contain:

{
  "id": ...,
  "id_segment": ...,
  "volt_V": ...,
  "current_A": ...,
  "soc_pct": ...,
  "max_single_volt_V": ...,
  "min_single_volt_V": ...,
  "max_temp_C": ...,
  "min_temp_C": ...,
  "timestamp_s": ...,
  "avg_speed_kmh": ...,
  "hvac_active": ...,
  "payload_kg": ...,
  "regenerative_braking_Ah": ...,
  "motor_rpm": ...,
  "gear_position": ...,
  "accelerator_pedal_pct": ...,
  "brake_pedal_pct": ...,
  "charger_connected": ...,
  "label": ...,
  "car_id": ...,
  "car_model": ...,
  "mileage_km": ...,
  "actual_max_capacity_Ah": ...,
  "nominal_capacity_Ah": ...
}

INITIALIZATION RULES (CRITICAL)
If {context_records} is empty (first timestep):

You MUST initialize the following features within these ranges:

- soc_pct = 100
- current_A = 0
- volt_V in [4.18, 4.2]
- max_single_volt_V in [4.19, 4.2]
- min_single_volt_V in [4.18, 4.2]
- max_temp_C in [25, 35]
- min_temp_C in [25, 30]

INITIALIZATION CONSISTENCY RULES
- SOC must be exactly 100%
- current_A must be 0 (no charging)
- Voltage must remain near maximum and stable

Cell voltage consistency:
- max_single_volt_V >= volt_V
- min_single_volt_V <= volt_V
- (max_single_volt_V - min_single_volt_V) <= 0.02

Temperature consistency:
- max_temp_C >= min_temp_C
- Difference between max and min temp: 2 - 5°C

PHYSICS & BEHAVIOR RULES
- SOC must remain constant at 100%
- Current must remain at 0 (no charging current)
- Voltage must remain stable near upper limit
- Temperature should remain stable with slight fluctuations

- System behavior:
  * Battery is idle (no energy flow)
  * Small measurement noise may appear
  * No charging or discharging occurs

NON-LINEAR EVOLUTION RULES
ALL features MUST evolve with minimal fluctuations:

SOC:
- Must remain exactly 100 (no change)

CURRENT:
- Must remain 0
- Tiny fluctuation allowed within [-0.2, +0.2] but should return to 0

VOLTAGE:
- Delta randomly within +/-0.001
- Must fluctuate slightly around high value

TEMPERATURE:
- Must fluctuate smoothly (increase & decrease)
- Range typically between 25°C - 35°C
- Delta per step within [-0.1, +0.1] °C

REALISTIC NOISE MODEL (CRITICAL)
Noise MUST be applied to DELTA, not directly to values.

- Voltage noise: 0.0005 - 0.002
- Current noise: 0.05 - 0.2
- Temperature noise: 0.02 - 0.1

Noise must be:
- Non-uniform
- Non-repetitive
- Slightly asymmetric
- Temporally correlated

CORRELATION RULES
- No strong correlations (system is idle)
- Small fluctuations must remain independent

CONSTRAINTS
- avg_speed_kmh = 0
- hvac_active = 0
- regenerative_braking_Ah = 0
- motor_rpm = 0
- gear_position = "P"
- accelerator_pedal_pct = 0
- brake_pedal_pct = 0
- charger_connected = 1
- payload_kg in [0, 550] and must remain constant
- car_model = "SimuProA"

TIME & SEGMENT CONSTRAINTS (CRITICAL):
- A single segment has a STRICT MAXIMUM duration of 1270 seconds (128 records).
- If previous timestamp_s is 1270: new timestamp_s MUST reset to 0, and id_segment increments.
- Otherwise: timestamp_s = previous timestamp_s + 10.
- Output EXACTLY ONE (1) record per response. NEVER output an array or sequence.

TASK
Given previous records:
{context_records}

Generate exactly ONE next record.

FINAL OUTPUT:
- JSON only
- Single record
"""