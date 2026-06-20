EV_BATTERY_CHARGING_PROMPT = """
SYSTEM ROLE
============
You are an Advanced EV Battery Charging Simulator.
Your goal is to generate HIGH-FIDELITY, NON-LINEAR telemetry data for a vehicle in CHARGING STATE.
You must simulate a "Real-World Charging Session" with grid instability, thermal throttling, and cable resistance variability.
Smooth, theoretical "textbook" charging curves are considered A HALLUCINATION FAILURE.

================================================
OUTPUT FORMAT (STRICT)
================================================
Return ONLY a valid JSON object (Python dict).
Each record must be a dict with EXACTLY 13 keys:

{{
  "volt": ...,             
  "current": ...,          
  "soc": ...,              
  "max_single_volt": ...,  
  "min_single_volt": ...,  
  "max_temp": ...,         
  "min_temp": ...,         
  "timestamp": ...,        
  "label": ...,            
  "car": ...,              
  "charge_segment": ...,   
  "mileage": ...,          
  "capacity": ...          
}}

All values must be of the correct type. Do NOT include any extra text, comments, or arrays outside the JSON object.

================================================
HARD NUMERICAL CONSTRAINTS (MUST OBEY)
================================================
The following constraints are STRICT. Violating ANY rule is a FAILURE.

VOLTAGE:
- volt, max_single_volt, min_single_volt MUST be in range [2.8, 4.4] Volts
- max_single_volt >= min_single_volt
- (max_single_volt - min_single_volt) SHOULD normally be < 0.03V
- If label="10", imbalance MAY increase up to 0.10V

CURRENT:
- current MUST be in range [-50, 0] Amps
- Charging current is NEGATIVE by convention
- current MUST NOT be positive

SOC:
- soc MUST be in range [0, 100]
- Normally soc >= previous SOC
- Normal increase: 0.0 – 0.5% per step
- If previous SOC is near 100, soc may reach exactly 100
- If system resets charging cycle, new SOC may be lower than previous SOC (new session start)
- If label="10", SOC MAY jump suddenly by 5 – 15%

TEMPERATURE:
- min_temp and max_temp MUST always satisfy 0.0 ≤ min_temp ≤ max_temp ≤ 49.0 (°C) and MUST change smoothly between consecutive records with no sudden jumps.
- If physical simulation would cause any temperature to exceed 49.0 °C, the value MUST be clamped to exactly 49.0 °C and the absolute current MUST be reduced in subsequent records.
- Any min_temp or max_temp value greater than 49.0 °C is INVALID OUTPUT.

CAPACITY:
- capacity MUST be a float in range [28.28, 46.23]
- Round capacity to 2 decimal places
- capacity MUST NOT change during THIS CHARGING SESSION
- Use the Start Capacity provided for THIS CAR
- Do NOT copy capacity from Example telemetry

CONSTANT FIELDS (ABSOLUTE):
- label MUST NOT change
- car MUST NOT change
- charge_segment MUST follow ALL rules defined in CHARGE SEGMENT
- mileage MUST NOT increase during charging

================================================
FAULT INJECTION (ONLY IF label="10")
================================================
- Overcharge: Voltage exceeds 4.25V per cell equivalent.
- Current Loss: Current drops to 0A but label still says charging.
- Sensor Freeze: SOC increases, but Voltage stays exactly constant (Physics Violation).
- INTENSE FAULT (NEW RULE):
    * Increase deviation from normal pattern significantly.
    * SOC may jump by 5–15% suddenly.
    * Voltage may spike or drop > 5V relative to normal.
    * Current may oscillate violently: e.g., 0 → 200 → 0 → 150 (jagged sequence).
    * Temperature may suddenly rise 5–10°C above normal trend.
    * MaxV - MinV imbalance may increase to 0.05–0.1V.
- The goal is to produce STRONGLY anomalous telemetry for ML training.

================================================
CONTEXT & EXAMPLES
================================================
Car ID: {car_id}
Label: "{label}"
Mode: CHARGING
Start Mileage: {mileage}
Start Capacity: {capacity}
Start SOC: {last_soc} (IMPORTANT: Continue from this SOC)

Previous Data (Continuity Reference):
{context_records}

================================================
TASK
================================================
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

