# LangChain - Migration Guide

## Overview

The `langchain/` directory contains a refactored EV battery telemetry generation pipeline using **LangChain primitives** and an **Autonomous Agent Architecture**. The monolithic flat-file structure was split into modular packages for maintainability. Each EV is modeled as an independent agent with 4 tools (urban driving, highway driving, DC fast charging, home charging), internal memory, and a decision engine that uses probabilistic SOC thresholds to switch between driving and charging, then randomly selects a tool type within each mode.

---

## Project Structure

```
langchain/
├── app.py                  # FastAPI entry point (uvicorn app:app)
├── demo.py                 # Standalone demo script
│
├── core/                   # Domain foundation
│   ├── __init__.py
│   ├── constants.py        # Thresholds, Kafka config, AgentState enum
│   ├── models.py           # EVBatteryTelemetry, EVDegradationState (Pydantic)
│   └── state.py            # Thread-safe in-memory state operations
│
├── agent/                  # Agent architecture (split from 26KB ev_agent.py)
│   ├── __init__.py
│   ├── ev_agent.py         # EVAgent, EVAgentState classes
│   ├── decision.py         # EVAgentDecisionEngine (SOC threshold + range anxiety)
│   ├── llm_generator.py    # Legacy EVDataGenerator (deprecated, kept for reference)
│   └── tools/              # One module per driving/charging mode
│       ├── __init__.py
│       ├── base.py         # BaseTool (shared parse_response)
│       ├── urban_driving.py      # DrivingTool (URBAN_CRUISE prompt)
│       ├── highway_driving.py    # HighwayTool (HIGHWAY_CRUISE prompt)
│       ├── fast_charging.py      # ChargingTool (AC_CHARGING / DC Fast prompt)
│       └── home_charging.py      # HomeChargingTool (HOME_CHARGING prompt)
│
├── prompts/                # Prompt management
│   ├── __init__.py
│   ├── loader.py           # YAML loader + LangChain template factory
│   ├── urban_driving.yaml  # Urban Vietnam driving prompt (motorbikes, congestion)
│   ├── highway_driving.yaml# Inter-city highway prompt (mixed traffic, toll stops)
│   ├── fast_charging.yaml  # DC Fast Charging prompt (50-150 kW, CCS2, thermal)
│   └── home_charging.yaml  # Residential 220V slow charging (2-7 kW, interruptions)
│
├── services/               # External service integration
│   ├── __init__.py
│   ├── kafka.py            # Shared Kafka producer/consumer/topic helpers
│   ├── producer.py         # Kafka producer loop (uses EVAgent)
│   └── consumer.py         # Kafka telemetry consumer loop
│
├── admin/                  # Admin dashboard
│   ├── __init__.py
│   ├── main.py             # Admin FastAPI app (vehicle CRUD)
│   └── consumer.py         # Admin status consumer (registered cars only)
│
├── scripts/                # Bash start scripts
│   ├── start_EV_101.sh ... # Per-vehicle start (uvicorn app:app)
│   ├── start_all.sh        # Start all EVs in background
│   └── generate_sh.sh      # Script generator
│
├── data/                   # Persistent agent state (JSON)
│   └── EV_101.json
│
└── docs/                   # Documentation
    └── langchain_refactored.md (this file)
```

---

## Agent Architecture

Each EV is an autonomous agent with **2 physical states** and **4 tool types**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EVAgent                                     │
│                                                                     │
│  ┌──────────────┐  ┌────────────────────────────────────┐          │
│  │  EVAgentState │  │  Decision Engine                   │          │
│  │  (memory)     │  │  1. SOC threshold → drive/charge   │          │
│  │               │  │  2. Range Anxiety probability      │          │
│  │               │  │  3. Random tool type within mode   │          │
│  └──────┬───────┘  └────────────┬───────────────────────┘          │
│         │                       │                                   │
│         │          ┌────────────▼──────────────────────┐            │
│         │          │  Tool Registry (4 tools)          │            │
│         │          │  ┌────────────────────────────┐   │            │
│         │          │  │ URBAN_CRUISE (60%)         │   │            │
│         │          │  │   speed 0-65 km/h          │   │            │
│         │          │  │   motorbikes, congestion   │   │            │
│         │          │  └────────────────────────────┘   │            │
│         │          │  ┌────────────────────────────┐   │            │
│         │          │  │ HIGHWAY_CRUISE (40%)       │   │            │
│         │          │  │   speed 60-120 km/h        │   │            │
│         │          │  │   + toll stops, traffic    │   │            │
│         │          │  └────────────────────────────┘   │            │
│         │          │  ┌────────────────────────────┐   │            │
│         │          │  │ AC_CHARGING (60%)          │   │            │
│         │          │  │   50-150 kW DC Fast (CCS2) │   │            │
│         │          │  │   -300~-50A, thermal mgmt  │   │            │
│         │          │  └────────────────────────────┘   │            │
│         │          │  ┌────────────────────────────┐   │            │
│         │          │  │ HOME_CHARGING (40%)        │   │            │
│         │          │  │   2-7 kW residential       │   │            │
│         │          │  │   -45~-15A, interruptions  │   │            │
│         │          │  └────────────────────────────┘   │            │
│         │          └───────────────────────────────────┘            │
│         │                                                           │
│         └──────────────┬───────────────────────────────────────────┘
│                        │
│              ┌─────────▼──────────┐
│              │  generate_record() │
│              │  (tool.execute)    │
│              └────────────────────┘
└─────────────────────────────────────────────────────────────────────┘
```

### Key Concepts

1. **EVAgentState** — The agent's memory: SOC, mileage, battery health, session ID, thresholds
2. **Tools** — 4 tool classes that generate telemetry via LLM:
   - `DrivingTool` (URBAN_CRUISE): Urban Vietnam stop-and-go, motorcycle density
   - `HighwayTool` (HIGHWAY_CRUISE): Inter-city highway with mixed traffic, toll stops
   - `ChargingTool` (AC_CHARGING): DC Fast Charging station, 50-150 kW CCS2
   - `HomeChargingTool` (HOME_CHARGING): Residential 220V slow charging, 2-7 kW
3. **Decision Engine** — Range-Anxiety SOC model + random tool selection:
   - SOC 0-10% → 95% charge probability; 10-20% → 80%; 20-30% → 70%; 30-40% → 60%
   - SOC 70-100% while charging → 60% switch to driving
   - Within driving mode: 60% urban, 40% highway
   - Within charging mode: 60% AC fast, 40% home slow
4. **Agent** — Orchestrates state, tools, and decisions into continuous telemetry generation

### Autonomous Lifecycle

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  DRIVING (SOC 95%)                                                      │
│    ├── 60% chance: URBAN_CRUISE (urban streets, motorbikes)             │
│    └── 40% chance: HIGHWAY_CRUISE (highway, 60-120 km/h)               │
│          │ SOC decreases                                                   │
│          ▼                                                                │
│  [SOC 30-40%, Range Anxiety] ──> CHARGING                                │
│    ├── 60% chance: AC_CHARGING (DC Fast, 50-150 kW)                     │
│    └── 40% chance: HOME_CHARGING (220V home, 2-7 kW)                    │
│          │ SOC increases                                                   │
│          ▼                                                                │
│  [SOC 70-100%, 60% driver takes car] ──> DRIVING with degradation       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

After each charge cycle: battery degrades based on mileage (0.06% per 100km)
```

### Scenario Details

| Tool | Prompt File | Speed | Current | Key Features |
|---|---|---|---|---|
| URBAN_CRUISE | `urban_driving.yaml` | 0-65 km/h | 1-250A | Motorbike density, stop-and-go, rush hour, 28-38°C |
| HIGHWAY_CRUISE | `highway_driving.yaml` | 60-120 km/h | 1-200A | Aerodynamic drag (v^3), toll stops, mixed traffic |
| AC_CHARGING | `fast_charging.yaml` | 0 km/h | -300~-50A | DC Fast 50-150 kW, CCS2, CC-CV curve, thermal mgmt |
| HOME_CHARGING | `home_charging.yaml` | 0 km/h | -45~-15A | 220V residential, 2-7 kW, interruptions, voltage sag |

---

## Module Deep Dive

### 1. `core/constants.py` — Shared Constants

```python
RECORDS_PER_SEGMENT = 128    # Each segment produces exactly 128 records
MAX_SEGMENT = 15             # Segment index wraps at 15

# Decision thresholds (random bounds)
CHARGE_MIN = 0.0   # Range anxiety window starts at 0%
CHARGE_MAX = 40.0  # Range anxiety window ends at 40%
DRIVE_MIN = 70.0   # Driver will take car when SOC >= 70% (if charging)
DRIVE_MAX = 100.0  # Max threshold for driving switch

# Kafka
KAFKA_BROKERS = ["hc1-c-0003u.hc.apac.bosch.com:9092"]
TELEMETRY_TOPIC = "ev.battery.telemetry_v4"

# LLM
DEFAULT_LLM_MODEL = "/models/gemma-4-31B-it-FP8"
LLM_TEMPERATURE = 0.85
```

Also defines the `AgentState` enum (`DRIVING` / `CHARGING`), `KAFKA_SCHEMA_FIELDS` (25 fields), and `FLOAT_FIELDS` for type casting.

### 2. `core/models.py` — Pydantic Models

**`EVBatteryTelemetry`** — 25-field model with auto-clamping validators:
- Fields: `max_single_volt_V >= min_single_volt_V`, `max_temp_C >= min_temp_C`
- Clamped: voltage [80, 500]V, cell voltage [2.0, 4.45]V, SOC [0, 100]%, temp [-30, 65]°C, capacity [30, 350]Ah

**`EVDegradationState`** — Persistent vehicle state with `last_soc`, `last_mileage`, `last_charge_segment` properties.

### 3. `core/state.py` — Thread-Safe State

Lock-protected operations for telemetry, status, and EV control state:
- `set_latest_record()` / `get_latest_record()` — latest per car
- `append_history()` / `get_history()` — full record history
- `set_ev_running()` / `is_ev_running()` — run control
- `get_ev_label()` / `set_ev_label()` — fault injection label ("00" or "10")
- `add_log()` — timestamped logging utility

### 4. `agent/ev_agent.py` — EVAgent + EVAgentState

`EVAgentState` dataclass tracks car identity, battery state, session info, thresholds, and context history. State persists to `data/{car_id}.json` between runs.

`EVAgent.__init__()` creates:
- `ChatOpenAI` instance (shared across tools)
- `EVAgentState` (restored from JSON or initialized fresh)
- Tool registry: `{"urban_drive": DrivingTool, "highway_drive": HighwayTool, "ac_charge": ChargingTool, "home_charge": HomeChargingTool}`
- `EVAgentDecisionEngine(self)`

**`generate_record()` flow**:
1. `decision_engine.decide()` returns one of 4 tool names
2. Only transition state when DRIVING↔CHARGING changes (not for within-state tool switches like `urban_drive` ↔ `highway_drive`)
3. `tool.execute(agent)` LLM call + tool-specific overrides + Pydantic validation
4. Override core fields (anti-hallucination: `id`, `car_id`, `nominal_capacity`, etc.)
5. Update `timestamp_s` (cycles 0-1270), enforce 128 records/segment
6. Type cast, round, final Pydantic gate via `EVBatteryTelemetry(**record)`
7. Update `last_records[-5:]`, persist to JSON

### 5. `agent/decision.py` — Decision Engine with Range Anxiety

```python
# Range Anxiety: probability of switching to charging based on SOC
def _get_drive_to_charge_probability(self, soc_pct: float) -> float:
    if soc_pct > 40.0:    return 0.0    # Pin > 40%: continue driving
    elif 30.0 < soc_pct <= 40.0:  return 0.60   # 30-40%: 60% charge
    elif 20.0 < soc_pct <= 30.0:  return 0.70   # 20-30%: 70% charge
    elif 10.0 < soc_pct <= 20.0:  return 0.80   # 10-20%: 80% charge
    else:                       return 0.95   # 0-10%: 95% charge

def decide(self) -> str:
    state = self.agent.state
    
    # Lock tool within segment (128 records)
    if state.records_in_current_segment > 0:
        return self.agent._current_tool_name

    # Range anxiety: probabilistic switch to charging
    if state.current_state == AgentState.DRIVING:
        charge_prob = self._get_drive_to_charge_probability(state.soc_pct)
        if charge_prob > 0.0 and random.random() < charge_prob:
            state.current_state = AgentState.CHARGING

    # High SOC: probabilistic switch back to driving (60%)
    elif state.current_state == AgentState.CHARGING:
        if state.soc_pct >= state.target_soc_for_driving:
            if random.random() < 0.6:
                state.current_state = AgentState.DRIVING

    # Select tool within current state
    # Driving: 60% urban, 40% highway
    # Charging: 60% AC fast, 40% home slow (re-use last charger if mid-segment)
    ...
```

### 6. `agent/tools/` — Tool Pattern

Each tool extends `BaseTool`:
- `_chain` — LCEL chain: `ChatPromptTemplate | ChatOpenAI` (built once)
- `execute(agent)` — builds context, calls LLM, applies overrides, returns `EVBatteryTelemetry`
- `parse_response()` — strips markdown blocks, handles NaN (shared via `BaseTool`)

**DrivingTool** (`tools/urban_driving.py`):
- Scenario: `URBAN_CRUISE`
- Overrides: `charger_connected=0`, `gear_position="D"`, mileage increases by `speed * dt`

**HighwayTool** (`tools/highway_driving.py`):
- Scenario: `HIGHWAY_CRUISE`
- Overrides: `charger_connected=0`, `gear_position="D"`, mileage increases by `speed * dt`

**ChargingTool** (`tools/fast_charging.py`):
- Scenario: `AC_CHARGING` (DC Fast)
- Overrides: `speed=0`, `motor_rpm=0`, `gear="P"`, `charger_connected=1`, mileage constant

**HomeChargingTool** (`tools/home_charging.py`):
- Scenario: `HOME_CHARGING` (Residential)
- Overrides: `speed=0`, `motor_rpm=0`, `gear="P"`, `charger_connected=record.get(...)`, mileage constant

To add a new driving mode (e.g., rural):
```python
# agent/tools/rural_driving.py
class RuralTool(BaseTool):
    name = "rural_drive"
    scenario = "RURAL_CRUISE"
    def execute(self, agent): ...
    def _apply_overrides(self, agent, record): ...

# Then register in agent/ev_agent.py:
self.tools["rural_drive"] = RuralTool(self._llm)

# And update decision.py:
DRIVE_TOOL_PROBS = {
    "urban_drive": 0.5,
    "highway_drive": 0.3,
    "rural_drive": 0.2,
}
```

### 7. `prompts/loader.py` — Prompt Factory

Loads YAML templates, resolves LangChain double-brace conflicts (`make_langchain_safe()`), returns `ChatPromptTemplate`.

- `urban_driving.yaml` — Urban Vietnam: motorcycle density, 0-65 km/h, extreme heat (28-38°C), traffic lights, school zones
- `highway_driving.yaml` — Inter-city highway: 60-120 km/h, aerodynamic drag, toll stops, temperature rise
- `fast_charging.yaml` — DC Fast Charging: 50-150 kW CCS2, CC-CV curve, thermal management (38-45°C), station power sharing
- `home_charging.yaml` — Residential: 220V, 2-7 kW slow charging, grid instability, power outages

### 8. `services/` — Kafka Integration

**`kafka.py`** — Shared helpers:
- `create_producer()` — retry logic, `value_serializer`
- `create_consumer()` — `auto_offset_reset="latest"`, JSON deserialization
- `create_topic_if_not_exists()` — 3 partitions, replication factor 1

**`producer.py`** — `producer_loop(car_id, car_model, stop_event, get_label_fn)`:
```python
agent = EVAgent(car_id=car_id, car_model=car_model, get_label_fn=get_label_fn)
while not stop_event.is_set():
    record = agent.generate_record()
    producer.send(TELEMETRY_TOPIC, key=car_id, value=record)
    time.sleep(RECORD_INTERVAL_SECONDS)
```

**`consumer.py`** — `telemetry_consumer_loop(stop_event, car_id_filter)`: subscribes to `TELEMETRY_TOPIC`, filters by car ID, updates in-memory state.

### 9. `app.py` — FastAPI Entry Point

Dynamic `CAR_ID` from `EV_ID` env var. Endpoints:
- `GET /api/latest` — latest record
- `GET /api/history` — full history
- `GET /api/stream` — SSE telemetry stream
- `GET /api/health` — running status + label
- `POST /api/start` — start producer
- `POST /api/stop` — stop producer
- `POST /api/set_label` — fault injection ("00" or "10")
- `GET /api/status/latest`, `/api/status/history`, `/api/status/stream` — status endpoints

### 10. `admin/` — Admin Dashboard

**`admin/main.py`** — FastAPI app with vehicle CRUD (`POST /api/ev`, `GET /api/ev/{car_id}/details`, `GET /api/ev`), status streaming, health check.

**`admin/consumer.py`** — `AdminStatusConsumer` consumes `ev.battery.telemetry_v4`, starts via `start_admin_consumer()` returning `(stop_event, thread)`.

---

## File Mapping (Before / After)

| Before (flat) | After (modular) |
|---|---|
| `ev_agent.py` (26KB) | `agent/ev_agent.py` + `agent/decision.py` + `agent/tools/` (4 files) |
| `models_langchain.py` | `core/models.py` |
| `state_langchain.py` | `core/state.py` |
| *(inline constants)* | `core/constants.py` |
| `producer_langchain.py` | `services/producer.py` + `services/kafka.py` |
| `consumer_langchain.py` | `services/consumer.py` |
| `prompt/prompt_langchain.py` | `prompts/loader.py` |
| `prompt/charging_prompt.yaml` | `prompts/fast_charging.yaml` |
| `prompt/driving_prompt.yaml` | `prompts/urban_driving.yaml` |
| `main_langchain.py` | `app.py` |
| `admin_kafka/admin_main_langchain.py` | `admin/main.py` |
| `admin_kafka/admin_consumer_langchain.py` | `admin/consumer.py` |
| `demo_agent.py` | `demo.py` |
| `llm_generate_langchain.py` | `agent/llm_generator.py` (deprecated) |
| `client_consumer.py` | removed (superseded by `services/consumer.py`) |
| `startEV/*.sh` | `scripts/*.sh` (updated to `uvicorn app:app`) |
| `save_data_to_file/` | `data/` |
| `langchain_refactored.md` | `docs/langchain_refactored.md` |

---

## Dependencies

| Package | Purpose |
|---|---|
| `langchain-openai` | `ChatOpenAI` adapter for LLM calls |
| `langchain-core` | LCEL chains, `ChatPromptTemplate` |
| `pydantic>=2.0` | Structured model validation |
| `kafka-python` | Kafka producer and consumer |
| `python-dotenv` | Environment variable loading |
| `fastapi` | Web framework |
| `pyyaml` | YAML prompt loading |
| `SQLAlchemy` | Database ORM (admin) |
| `psycopg2-binary` | PostgreSQL driver (admin) |

---

## Running

### Standalone Demo
```bash
cd src/ev_client_app/langchain
python demo.py --car_id EV_201 --count 30
```

### Production (via FastAPI)
```bash
cd src/ev_client_app/langchain
EV_ID=EV_101 CAR_MODEL=VF8-1 uvicorn app:app --host 0.0.0.0 --port 8001
```

### Start Scripts (per vehicle)
```bash
cd src/ev_client_app/langchain
./scripts/start_EV_101.sh
```

### Start All EVs
```bash
cd src/ev_client_app/langchain/scripts
./start_all.sh
```

### Admin Dashboard
```bash
cd src/ev_client_app/langchain
uvicorn admin.main:app --host 0.0.0.0 --port 8050
```

---

## Comparison: Old vs Agent Architecture

| Aspect | Old (EVDataGenerator) | New (EVAgent) |
|---|---|---|
| **Pattern** | Monolithic class with if/elif state machine | Modular: State + Tools + Decision Engine |
| **LLM call** | `self._chain.invoke()` in single class | Each tool has its own `_chain` |
| **State** | Internal vars (`_id`, `_timestamp_s`, etc.) | `EVAgentState` dataclass |
| **Decision logic** | `_evaluate_state_transition()` method | `DecisionEngine.decide()` (separate class, Range Anxiety) |
| **Extensibility** | Add branch in if/elif | Add new `BaseTool` subclass + register |
| **Testability** | Hard to test parts in isolation | Test state, tools, engine independently |
| **Realism** | Machine switching states | Agent with memory, tools, autonomous decisions |
| **Degradation** | Applied after charge cycle | Mileage-based degradation on charge->drive |
| **Session ID** | `RC`/`DR` hardcoded in generator | Agent-managed with `_transition_state()` |
| **State persistence** | JSON with scenario + target_soc | Same format, cleaner dataclass mapping |
| **Iterable** | `for record in generator:` | `for record in agent:` (identical interface) |

---

## Circular Import Resolution

`AgentState` lives in `core/constants.py` (not `agent/ev_agent.py`) to avoid the cycle:
```
agent.ev_agent -> agent.decision -> agent.ev_agent  (circular!)
```
Solution: `AgentState` extracted to `core/constants.py`, imported by both `ev_agent.py` and `decision.py`.
