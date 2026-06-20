# Data Generation Pipeline - Current Status

## Architecture Overview

The EV battery telemetry data generation system consists of three parallel codebases:

| Directory | Purpose |
|---|---|
| `charging/` | Production AC charging data generator |
| `driving/` | Production urban driving data generator |
| `EV101/` | LangChain + Agent architecture (modular packages) |

All three share the same data model: a **25-field EV battery telemetry record** published to Kafka and consumed by FastAPI endpoints with SSE streaming.

---

## The 25-Field Telemetry Schema

Every record contains these fields:

| Field | Type | Description |
|---|---|---|
| `id` | str | Unique session identifier (e.g. `RC847291`, `DR912345`) |
| `id_segment` | str | Segment index appended to `id` (e.g. `RC847291_5`) |
| `volt_V` | float | Average cell voltage [2.8, 4.4] |
| `current_A` | float | Battery current (negative during charging) [-50, 0] for charging; [20, 80] for driving |
| `soc_pct` | float | State of charge [0, 100] |
| `max_single_volt_V` | float | Highest cell voltage, >= min_single_volt_V, imbalance < 0.03V |
| `min_single_volt_V` | float | Lowest cell voltage |
| `max_temp_C` | float | Highest cell temp [0, 49] |
| `min_temp_C` | float | Lowest cell temp, <= max_temp_C |
| `timestamp_s` | int | Elapsed seconds in current segment [-10 .. 1270], resets to 0 after 1270 |
| `avg_speed_kmh` | float | Average speed (0 for charging, 40-90 for driving) |
| `hvac_active` | int | HVAC on/off |
| `payload_kg` | float | Vehicle payload, constant during a session |
| `regenerative_braking_Ah` | float | Energy recovered (0 for charging) |
| `motor_rpm` | float | Motor RPM (0 for charging, 4000-15000 for driving) |
| `gear_position` | str | `"P"` for charging, `"D"` for driving |
| `accelerator_pedal_pct` | float | Driver throttle input (0 for charging, 5-25 for driving) |
| `brake_pedal_pct` | float | Brake pedal input |
| `charger_connected` | int | 1 for charging, 0 for driving |
| `label` | str | `"00"` = normal, `"10"` = fault injection mode |
| `car_id` | str | Vehicle identifier set by start script |
| `car_model` | str | e.g. `"VF8-1"` |
| `mileage_km` | float | Cumulative distance (increases during driving, constant during charging) |
| `actual_max_capacity_Ah` | float | Degraded capacity [28.28, 46.23] |
| `nominal_capacity_Ah` | float | Nominal capacity [90, 120], constant per session |

---

## OLD PIPELINE (Production: `charging/` and `driving/`)

### Data Flow

```
startEV/start_EV1XX.sh
    |
    v
uvicorn (FastAPI on port 8001-8011)
    |
    ├── main.py          -- FastAPI app, SSE endpoints, start/stop/control
    │       |
    │       ├── producer.py        -- Kafka producer loop
    │       │       |
    │       │       ├── llm_generate.py   -- LLM generator (generator function)
    │       │       │       |
    │       │       │       ├── prompt.py -- Raw text prompt templates
    │       │       │       |
    │       │       │       └── LLM API: /models/gemma-4-31B-it-FP8
    │       │       │
    │       │       └── KafkaProducer -> ev.battery.telemetry_v3
    │       │
    │       ├── client_consumer.py      -- Telemetry consumer (reads from Kafka)
    │       │       |
    │       │       └── state.py        -- In-memory state (latest_record, history)
    │       │
    │       └── admin_main.py           -- Admin FastAPI (vehicle CRUD, status stream)
    │               |
    │               └── admin_consumer.py -- Status consumer
    │
    └── state.py -- Shared thread-safe in-memory dicts (latest_record, history, ev_control_state)
```

### Key Characteristics

**LLM Generation (`llm_generate.py`):**
- Uses raw `requests.Session.post()` to call the LLM API at `http://hc1-c-0003u.hc.apac.bosch.com:30000/v1/chat/completions`
- Generator function (`def generate_ev_data(...)` with `yield`) - produces one record per `next()` call
- Manual JSON parsing: `json.loads(content)` after stripping NaN/None
- Manual field validation: `REQUIRED_FIELDS - record.keys()` to check missing fields, then manual `del` for extra fields
- Manual type casting: iterates through `float_fields` and casts each
- State persisted to `save_data_to_file/{car_id}.json` - stores last 5 records, nominal capacity, and cycle count

**Prompt System (`prompt.py`):**
- 11 raw text prompt templates as Python string constants
- Uses `.format()` for variable substitution: `EV_BATTERY_AC_CHARGING_PROMPT.format(context_records=...)`
- Prompts contain `{car_id}`, `{label}`, `{mileage}`, `{capacity}`, `{last_soc}`, `{context_records}` as format placeholders
- JSON examples in prompts use `{{` and `}}` for Python string escaping
- No LangChain abstractions - plain strings

**State Management (`state.py`):**
- Module-level dicts: `latest_record = {}`, `history = defaultdict(list)`, `ev_control_state = {}`
- Thread-safe access via `ev_state_lock`
- Functions like `append_history(car_id, record)`, `set_latest_record(car_id, record)`, `get_ev_label(car_id)`

**Producer Loop (`producer.py`):**
- Creates KafkaProducer with retry logic
- Creates telemetry topic if not exists
- Calls `generate_ev_data()` as a generator, iterates with `next()`
- Type sanitization on every record before sending
- 3-second interval between records

**Session Lifecycle:**
- First run: `id` = `"RC" + random 6-digit`, `timestamp_s` starts at -10 (first loop makes it 0), segment index = 1
- Nominal capacity randomized to [90, 120]
- Actual capacity = nominal * random(0.95, 0.99)
- Mileage randomized to [10000, 999999]
- Payload randomized to [0, 100] kg for charging
- Segment limit: 15 for charging, 18 for driving
- `timestamp_s` increments by 10 each step, resets to 0 at 1270
- RC->DR transition: replaces `RC` prefix with `DR` in driving mode

### Startup Scripts

Each `startEV/start_EVXXX.sh` sets `EV_ID`, `CAR_MODEL`, `VIN` env vars and starts uvicorn on a unique port:

| Script | Port |
|---|---|
| `start_EV101.sh` - `start_EV110.sh` | 8001 - 8010 |

`startadmin.sh` starts the admin backend on port 8050 + Dash frontend.

Ports increment by 1, skipping 8005.

---

## EV101 - Modular Agent Architecture (NEW)

### Data Flow

```
EV101/scripts/start_EV1XX.sh
    |
    v
uvicorn app:app --port 8001-8010
    |
    ├── app.py                  -- FastAPI entry point
    │       |
    │       ├── services/producer.py   -- Kafka producer loop
    │       │       |
    │       │       ├── agent/ev_agent.py  -- EVAgent (self-contained)
    │       │       │       |
    │       │       │       ├── agent/decision.py  -- Decision engine
    │       │       │       ├── agent/tools/       -- Tool registry
    │       │       │       │       ├── base.py
    │       │       │       │       ├── driving.py (URBAN_CRUISE)
    │       │       │       │       └── charging.py (AC_CHARGING)
    │       │       │       │
    │       │       │       ├── core/models.py  -- Pydantic models
    │       │       │       │       |
    │       │       │       │       └── EVBatteryTelemetry, EVDegradationState
    │       │       │       │
    │       │       │       └── prompts/loader.py -- YAML + LangChain factory
    │       │       │
    │       │       └── KafkaProducer -> ev.battery.telemetry_v3
    │       │
    │       ├── services/consumer.py      -- Telemetry consumer
    │       │       |
    │       │       └── core/state.py     -- Thread-safe state
    │       │
    │       └── admin/main.py             -- Admin FastAPI (vehicle CRUD)
    │               |
    │               └── admin/consumer.py -- Status consumer
    │
    └── core/state.py -- Shared thread-safe in-memory state
        └── core/constants.py -- Thresholds, Kafka config, AgentState enum
```

### Key Features

**EVAgent Architecture (`agent/ev_agent.py`):**
- Each EV is an autonomous agent with its own memory, tools, and decision engine
- `EVAgentState` dataclass: SOC, mileage, battery health, session info, thresholds
- `DecisionEngine.decide()`: autonomous SOC-threshold logic (charge when low, drive when high)
- `EVAgent.generate_record()`: orchestrates decide → transition → execute → validate → persist

**Tool Pattern (`agent/tools/`):**
- Each tool is a callable object: `DrivingTool` (URBAN_CRUISE), `ChargingTool` (AC_CHARGING)
- Tool-specific overrides: `charger_connected`, `gear_position`, mileage updates
- Extensible: add new tool subclass + register in `EVAgent.tools` dict

**Dynamic Autonomous Lifecycle:**
```
DRIVING (SOC 95%) --SOC drops--> CHARGING (SOC 20% -> 90%) --SOC rises--> DRIVING (SOC 90%)
     |                                   |                                   |
 DrivingTool                       ChargingTool                       DrivingTool
 URBAN_CRUISE                      AC_CHARGING                          URBAN_CRUISE
 speed 40-60km/h                   current -50~0A                     cycle_count++, capacity degradation
 SOC decreases                      SOC increases                     session ID changes RC<->DR
 mileage increases                  mileage constant
```

After each charge cycle: battery degrades (`actual_capacity *= random(0.9995, 1.0)`).

**Prompt System (`prompts/loader.py`):**
- Loads YAML templates (`prompts/charging.yaml`, `prompts/driving.yaml`)
- `make_langchain_safe()` resolves double-brace conflicts for LangChain `ChatPromptTemplate`
- Scenarios: `AC_CHARGING`, `URBAN_CRUISE` (extensible to more)

**Pydantic Models (`core/models.py`):**
- `EVBatteryTelemetry`: 25-field model with field and model validators
- `EVDegradationState`: persistent vehicle state with `last_soc`, `last_mileage` properties

**State Management (`core/state.py`):**
- Module-level private vars with `threading.Lock`
- All access through lock-protected methods, returns copies for thread safety

**Producer Loop (`services/producer.py`):**
```python
agent = EVAgent(car_id=car_id, car_model=car_model, get_label_fn=get_label_fn)
while not stop_event.is_set():
    record = agent.generate_record()  # Agent decides its own next action
    producer.send(TELEMETRY_TOPIC, key=car_id, value=record)
```

### Dependencies Added
- `pyyaml` — YAML prompt loading
- `agent/` modules — circular import resolved via `AgentState` in `core/constants.py`

---

## OLD vs NEW EV101 Architecture

### Generator Pattern

```python
# OLD (monolithic flat-file): EVDataGenerator class
class EVDataGenerator:
    def __init__(self):
        self._llm = ChatOpenAI(...)
        self._chain = prompt_template | self._llm
        # All state, logic, overrides in one class
    
    def __next__(self):
        self._evaluate_state_transition()  # if/elif branching
        # Everything: LLM call, overrides, validation in one method

# NEW (EV101): Modular agent architecture
agent = EVAgent(car_id="EV_101")
for record in agent:
    # Agent internally:
    # 1. decision_engine.decide() -> "drive" or "charge"
    # 2. _transition_state() if tool changed
    # 3. tools[selected].execute(agent) -> LLM call
    # 4. override core fields, validate, persist
    print(record.soc_pct)
```

### Extensibility

```python
# OLD: Add new driving mode
class EVDataGenerator:
    def __next__(self):
        if self.scenario == "URBAN_CRUISE": ...
        elif self.scenario == "HIGHWAY": ...  # Add branch
        # ... all logic in one method

# NEW: Add new driving mode
# agent/tools/highway.py
class HighwayTool(BaseTool):
    name = "highway"
    scenario = "HIGHWAY_CRUISE"
    def execute(self, agent): ...
    def _apply_overrides(self, agent, record): ...

# agent/ev_agent.py
self.tools["highway"] = HighwayTool(self._llm)
# Add to decision engine if needed
```

### Module Layout

| OLD (flat-file structure) | NEW (`EV101/`) |
|---|---|
| `main_langchain.py` | `app.py` |
| `producer_langchain.py` | `services/producer.py` + `services/kafka.py` |
| `consumer_langchain.py` | `services/consumer.py` |
| `ev_agent.py` (26KB monolithic) | `agent/ev_agent.py` + `agent/decision.py` + `agent/tools/` |
| `models_langchain.py` | `core/models.py` |
| `state_langchain.py` | `core/state.py` + `core/constants.py` |
| `prompt_langchain.py` | `prompts/loader.py` |
| `prompt/*.yaml` | `prompts/*.yaml` |
| `admin_kafka/*.py` | `admin/*.py` |
| `startEV/*.sh` | `scripts/*.sh` |
| `save_data_to_file/` | `data/` |

---

## API Endpoints (All Pipelines)

| Endpoint | Method | Description |
|---|---|---|
| `/api/latest` | GET | Latest telemetry record for this car |
| `/api/history` | GET | Full telemetry history |
| `/api/stream` | GET | SSE stream of telemetry records |
| `/api/health` | GET | Health/status of EV control state |
| `/api/start` | POST | Start data generation |
| `/api/stop` | POST | Stop data generation |
| `/api/set_label` | POST | Set label to "00" (normal) or "10" (fault) |
| `/api/status/latest` | GET | Latest status record |
| `/api/status/history` | GET | Status history |
| `/api/status/stream` | GET | SSE stream of status records |
| `/api/ev` | POST | Register vehicle (admin) |
| `/api/ev/{car_id}/details` | GET | Vehicle details (admin) |
| `/api/ev` | GET | List all vehicles (admin) |

---

## Kafka Topics

| Topic | Direction | Description |
|---|---|---|
| `ev.battery.telemetry_v3` | Publish + Subscribe | Battery telemetry records |
| `ev.vehicle.status` | (commented out) | Vehicle status records |

Each record is published with the `car_id` as the Kafka message key.

---

## Prompt Templates

### Charging Prompts (`charging/prompt.py`)

| Constant | Scenario |
|---|---|
| `EV_BATTERY_AC_CHARGING_PROMPT` | Normal AC charging (default) |
| `EV_BATTERY_CHARGING_PROMPT` | General charging with grid instability |
| `EV_BATTERY_SLEEP_MODE_PROMPT` | Vehicle locked, 12V standby only |
| `EV_BATTERY_STANDBY_MODE_PROMPT` | Vehicle on, engine off |
| `EV_BATTERY_PARKED_HVAC_ON_PROMPT` | Parked with HVAC running |
| `EV_BATTERY_V2L_V2G_PROMPT` | Vehicle-to-load / vehicle-to-grid |
| `EV_BATTERY_DC_FAST_CHARGING_PROMPT` | DC fast charging |
| `EV_BATTERY_DC_FAST_CHARGING_COLD_PROMPT` | Cold weather DC fast charging |
| `EV_BATTERY_DC_FAST_CHARGING_HOT_PROMPT` | Hot weather DC fast charging |
| `EV_BATTERY_NEAR_FULL_CHARGING_PROMPT` | Near 100% SOC charging |
| `EV_BATTERY_FULLY_CHARGED_PROMPT` | Fully charged, maintenance mode |

### Driving Prompt (`driving/prompt.py`)

| Constant | Scenario |
|---|---|
| `EV_BATTERY_URBAN_CRUISE_PROMPT` | Urban cruising 40-60 km/h |

Each prompt defines:
- System role and scenario description
- Exact output format (25 JSON keys)
- Hard numerical constraints (voltage, current, SOC, temperature ranges)
- Relationship rules (accelerator -> current -> voltage -> SOC)
- Temporal consistency requirements
- Self-check / rejection rules
- Fault injection rules for label="10"
- Previous data context via `{context_records}` placeholder
