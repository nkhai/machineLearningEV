import dash
from dash import Dash, html, dcc, Input, Output, State, ALL, ctx, no_update
import dash_bootstrap_components as dbc
import dash_daq as daq
import json
import requests
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate

# --- CONFIG ---
API_BASE_URL = "http://localhost:8050"

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="EV Status Monitor", update_title=None)

# --- CSS STYLES ---
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { background-color: #f8f9fa; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
            
            /* Sidebar */
            .sidebar {
                background-color: #ffffff;
                border-right: 1px solid #dee2e6;
                height: 100vh;
                display: flex;
                flex-direction: column;
                padding: 20px;
                position: fixed;
                width: 16.66667%;
                z-index: 1000;
            }
            .vehicle-list-wrapper { flex-grow: 1; overflow-y: auto; margin-bottom: 15px; }
            .vehicle-btn {
                text-align: left; margin-bottom: 8px; border: 1px solid #e9ecef;
                background-color: #fff; color: #495057; width: 100%;
                padding: 10px 15px; border-radius: 6px; transition: all 0.2s;
                display: flex; justify-content: space-between; align-items: center;
            }
            .vehicle-btn:hover { background-color: #f1f3f5; transform: translateX(3px); }
            .vehicle-btn.active { background-color: #e7f5ff; border-color: #1890ff; color: #0050b3; font-weight: 600; }
            
            /* Main Content */
            .main-content { margin-left: 16.66667%; padding: 30px; }
            
            /* Cards */
            .kpi-card {
                border-radius: 8px; color: white; padding: 15px; height: 90px;
                display: flex; flex-direction: column; justify-content: center;
                align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
            .bg-status { background-color: #00c853; } 
            .bg-soc { background-color: #00b0ff; }    
            .bg-capacity { background-color: #ffab00; } 
            .bg-mileage { background-color: #000000; }  
            
            .kpi-title { font-size: 12px; font-weight: 600; text-transform: uppercase; opacity: 0.9; margin-bottom: 4px; }
            .kpi-value { font-size: 24px; font-weight: bold; }
            .kpi-unit { font-size: 12px; font-weight: normal; margin-left: 2px; }

            .content-card {
                background: white; border: 1px solid #e0e0e0; border-radius: 8px;
                padding: 15px; height: 100%; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
            }
            .card-header-custom {
                font-size: 13px; font-weight: 700; color: #555; text-transform: uppercase;
                margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 8px;
            }
            
            /* Info Rows */
            .info-row { padding: 8px 0; border-bottom: 1px solid #f0f0f0; font-size: 14px; min-height: 38px; }
            .info-label { font-weight: 600; color: #6c757d; }
            .info-value { font-weight: 500; color: #212529; text-align: right; }

            /* Scrollbar */
            #log-content::-webkit-scrollbar { width: 6px; }
            #log-content::-webkit-scrollbar-track { background: #f1f1f1; }
            #log-content::-webkit-scrollbar-thumb { background: #ccc; border-radius: 3px; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>
'''

# --- HELPER FUNCTIONS ---
def get_ev_details(car_id):
    try:
        response = requests.get(f"{API_BASE_URL}/api/ev/{car_id}/details", timeout=3)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {}

def get_all_vehicles():
    try:
        response = requests.get(f"{API_BASE_URL}/api/ev", timeout=3)
        if response.status_code == 200:
            return response.json()  
    except Exception as e:
        print("Error fetching vehicles:", str(e))
    return []

# --- LAYOUT COMPONENTS ---
def create_sidebar():
    return html.Div([
        html.H5("VEHICLE LIST", className="mb-4", style={"fontWeight": "800", "color": "#212529"}),
        html.Div(id="vehicle-list-container", className="vehicle-list-wrapper"),
        html.Button([
            html.I(className="fa fa-plus me-2"), "+ New EV"
        ], id="btn-open-register", className="btn btn-outline-dark w-100 mt-auto", style={"fontWeight": "600"})
    ], className="sidebar")

def create_kpi_card(title, id_val, unit, bg_class):
    return html.Div([
        html.Div(title, className="kpi-title"),
        html.Div([
            html.Span(id=id_val, className="kpi-value"),
            html.Span(unit, className="kpi-unit")
        ])
    ], className=f"kpi-card {bg_class}")

def create_registration_modal():
    return dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Register New Vehicle")),
        dbc.ModalBody([
            dbc.Label("Car ID (System ID) *"),
            dbc.Input(id="reg-car-id", type="text", placeholder="Enter unique ID (e.g., EV_101)", className="mb-3"),
            
            dbc.Label("Vehicle Name"),
            dbc.Input(id="reg-car-name", placeholder="e.g., VF8-1", className="mb-3"),
            dbc.Label("VIN Number"),
            dbc.Input(id="reg-vin", placeholder="Enter VIN", className="mb-3"),
            dbc.Label("License Plate"),
            dbc.Input(id="reg-license", placeholder="e.g., 29A-123.45", className="mb-3"),
            dbc.Label("Battery Serial"),
            dbc.Input(id="reg-battery", placeholder="Enter Battery Serial", className="mb-3"),
            dbc.Label("Motor Serial"),
            dbc.Input(id="reg-motor", placeholder="Enter Motor Serial", className="mb-3"),
            dbc.Label("User ID *"),
            dbc.Input(id="reg-user-id", placeholder="Enter user ID", className="mb-3"),
            html.Div(id="reg-feedback", className="text-danger small mt-2")
        ]),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="btn-cancel-reg", color="secondary", className="me-2"),
            dbc.Button("Save Vehicle", id="btn-submit-reg", color="primary"),
        ])
    ], id="modal-register-ev", is_open=False, centered=True)


# --- MAIN APP LAYOUT (DYNAMIC) ---
def serve_layout():
    # Call API to fetch vehicles on page load
    initial_vehicles = get_all_vehicles()
    
    return html.Div([
        dcc.Store(id="selected-car-store", data=None), 
        dcc.Store(id="log-level-store", data="INFO"), 
        dcc.Store(id="refresh-list-trigger", data=0), 
        dcc.Store(id="vehicle-list-store", data=initial_vehicles), # Load data into Store immediately
        
        html.Div(id='sse-data-hidden', style={'display': 'none'}),
        
        create_registration_modal(),

        dbc.Row([
            # SIDEBAR
            dbc.Col(create_sidebar(), width=2, className="p-0"),

            # MAIN CONTENT
            dbc.Col([
                # 1. Header
                dbc.Row([
                    dbc.Col([
                        html.H4("ELECTRIC VEHICLE STATUS", className="m-0", style={"fontWeight": "800"}),
                    ], width=6),
                    
                    dbc.Col([
                        html.Div([
                            html.Span("Current State: ", className="text-muted me-2 small"),
                            html.Span(id="top-status-text", className="fw-bold me-4", style={"fontSize": "15px"}),
                        ], className="d-flex align-items-center justify-content-end h-100")
                    ], width=6)
                ], className="mb-4 align-items-center"),

                # 2. KPI Cards
                dbc.Row([
                    dbc.Col(create_kpi_card("STATUS", "status-val", "", "bg-status"), width=3),
                    dbc.Col(create_kpi_card("SOC", "soc-val", "%", "bg-soc"), width=3),
                    dbc.Col(create_kpi_card("CAPACITY", "capacity-val", "Ah", "bg-capacity"), width=3),
                    dbc.Col(create_kpi_card("MILEAGE", "mileage-val", "km", "bg-mileage"), width=3),
                ], className="g-3 mb-3"),

                # 3. DETAILS ROW 
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div("CELL VOLTAGE HEALTH", className="card-header-custom mb-1"),
                            dbc.Row([
                                dbc.Col([
                                    html.Div("Max Single", className="text-secondary", style={"fontSize": "11px"}),
                                    html.Div(id="max-cell-val", className="fw-bold text-danger", style={"fontSize": "22px"})
                                ], className="text-center border-end"),
                                dbc.Col([
                                    html.Div("Min Single", className="text-secondary", style={"fontSize": "11px"}),
                                    html.Div(id="min-cell-val", className="fw-bold text-primary", style={"fontSize": "22px"})
                                ], className="text-center border-end"),
                                dbc.Col([
                                    html.Div("Diff (Imb)", className="text-secondary", style={"fontSize": "11px"}),
                                    html.Div(id="diff-cell-val", className="fw-bold text-dark", style={"fontSize": "22px"})
                                ], className="text-center"),
                            ], className="align-items-center h-75 mt-2") 
                        ], className="content-card p-3", style={"height": "200px"}) 
                    ], width=5),

                    dbc.Col([
                        html.Div([
                            html.Div("THERMAL & POWER", className="card-header-custom mb-1"),
                            html.Div([
                                html.Div([
                                    html.Span("Temp:", className="text-muted"), 
                                    html.Span(id="temp-range-val", className="float-end fw-bold", style={"fontSize": "18px"})
                                ], className="mb-3 border-bottom pb-2"),
                                html.Div([
                                    html.Span("Power:", className="text-muted"), 
                                    html.Span(id="power-val", className="float-end fw-bold", style={"fontSize": "18px"})
                                ], className="mb-0"),
                            ], className="d-flex flex-column justify-content-center pt-3")
                        ], className="content-card p-3", style={"height": "200px"}) 
                    ], width=3),

                    dbc.Col([
                        html.Div([
                            html.Div("SPEED", className="card-header-custom text-center mb-0", style={"borderBottom": "none"}),
                            html.Div([
                                daq.Gauge(
                                    id='speed-gauge', min=0, max=240, value=0, size=110, 
                                    units="km/h", showCurrentValue=True,
                                    color={"gradient":True,"ranges":{"#56a64b":[0,80],"#f2994a":[80,140],"#e02f44":[140,240]}},
                                    style={'marginBottom': '-15px', 'marginTop': '-10px'}
                                )
                            ], className="d-flex flex-column align-items-center justify-content-center")
                        ], className="content-card p-2", style={"height": "200px"}) 
                    ], width=4),
                ], className="g-3 mb-4 mt-3"), 

                # 4. BOTTOM ROW: VEHICLE INFO & LOGS 
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div("VEHICLE INFORMATION", className="card-header-custom"),
                            html.Div(id='vehicle-info-content', className="p-2")
                        ], className="content-card p-3", style={"height": "270px", "overflowY": "auto"})
                    ], width=6),

                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.B("SYSTEM LOGS", style={"fontSize": "11px"}),
                                dbc.ButtonGroup([
                                    dbc.Button("INFO", id="btn-log-info", size="sm", outline=True, color="success"),
                                    dbc.Button("DEBUG", id="btn-log-debug", size="sm", outline=True, color="secondary"),
                                ], size="sm", className="ms-2"),
                                html.Span(id="log-timestamp", className="ms-auto text-muted", style={"fontSize": "10px"})
                            ], className="d-flex align-items-center mb-2 border-bottom pb-1"),

                            html.Div(id="log-content", className="font-monospace", style={"fontSize": "11px", "whiteSpace": "pre-wrap", "overflowY": "auto", "height": "210px"})
                        ], className="content-card p-3", style={"height": "270px"})
                    ], width=6)
                ], className="g-3 mb-3"),

                # 5. HDFS HISTORICAL CHART
                dbc.Row([
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Div("HDFS HISTORICAL DATA", className="card-header-custom mb-0",
                                         style={"borderBottom": "none", "display": "inline"}),
                                dcc.Dropdown(
                                    id="hdfs-metric-dropdown",
                                    options=[
                                        {"label": "SOC (%)", "value": "soc_pct"},
                                        {"label": "Voltage (V)", "value": "volt_V"},
                                        {"label": "Current (A)", "value": "current_A"},
                                        {"label": "Temp Max (°C)", "value": "max_temp_C"},
                                        {"label": "Speed (km/h)", "value": "avg_speed_kmh"},
                                        {"label": "Capacity (Ah)", "value": "actual_max_capacity_Ah"},
                                    ],
                                    value="soc_pct",
                                    clearable=False,
                                    style={"width": "180px", "fontSize": "12px"},
                                ),
                                html.Button("Load from HDFS", id="btn-load-hdfs",
                                            className="btn btn-sm btn-outline-primary"),
                                html.Span(id="hdfs-status-text", className="text-muted",
                                          style={"fontSize": "11px"}),
                            ], className="d-flex align-items-center gap-2 border-bottom pb-2 mb-2"),
                            dcc.Graph(id="hdfs-history-chart",
                                      figure=go.Figure(layout=dict(
                                          paper_bgcolor="rgba(0,0,0,0)",
                                          plot_bgcolor="rgba(0,0,0,0)",
                                          margin=dict(l=40, r=20, t=10, b=40),
                                          height=240,
                                          annotations=[dict(text="Select a vehicle and click \"Load from HDFS\"",
                                                           xref="paper", yref="paper",
                                                           x=0.5, y=0.5, showarrow=False,
                                                           font=dict(size=13, color="#aaa"))]
                                      )),
                                      config={"displayModeBar": False},
                                      style={"height": "260px"}),
                        ], className="content-card p-3")
                    ], width=12)
                ], className="g-3 mb-3"),
            ], width=10, className="main-content")
        ])
    ])

# Assign function to layout
app.layout = serve_layout

# --- CLIENT-SIDE: SSE CONNECTION ---
app.clientside_callback(
    """
    function(car_id) {
        if (!car_id) return window.dash_clientside.no_update;
        const url = "http://localhost:8050/api/status/stream/" + car_id;
        if (window.evtSource && window.evtSource.readyState !== 2) {
            window.evtSource.close();
        }
        window.evtSource = new EventSource(url);
        window.evtSource.onmessage = function(event) {
            dash_clientside.set_props("sse-data-hidden", {children: event.data});
        };
        window.evtSource.onerror = function(err) { window.evtSource.close(); };
        return window.dash_clientside.no_update;
    }
    """,
    Output('sse-data-hidden', 'style'), 
    Input('selected-car-store', 'data')
)

# --- CALLBACKS ---

# 1. Registration Modal & Submission
@app.callback(
    [Output("modal-register-ev", "is_open"),
     Output("refresh-list-trigger", "data"),
     Output("selected-car-store", "data"),
     Output("reg-feedback", "children"),
     Output("vehicle-list-store", "data"),
    Output("reg-car-id", "value"),
    Output("reg-car-name", "value"),
    Output("reg-vin", "value"),
    Output("reg-license", "value"),
    Output("reg-battery", "value"),
    Output("reg-motor", "value"),
    Output("reg-user-id", "value")],
    [Input("btn-open-register", "n_clicks"),
     Input("btn-cancel-reg", "n_clicks"),
     Input("btn-submit-reg", "n_clicks")],
    [State("modal-register-ev", "is_open"),
     State("reg-car-id", "value"),
     State("reg-car-name", "value"),
     State("reg-vin", "value"),
     State("reg-license", "value"),
     State("reg-battery", "value"),
     State("reg-motor", "value"),
     State("reg-user-id", "value"),
     State("refresh-list-trigger", "data"),
     State("selected-car-store", "data"),
     State("vehicle-list-store", "data")],
    prevent_initial_call=True
)
def handle_registration(
    open_clicks, cancel_clicks, submit_clicks, is_open, 
    car_id_input, name, vin, license_pl, battery, motor, user_id, 
    refresh_count, current_car, current_list
):
    ctx_id = ctx.triggered_id

    if ctx_id == "btn-open-register" or ctx_id == "btn-cancel-reg":
        return not is_open, no_update, no_update, "", current_list, "", "", "", "", "", "", ""

    if ctx_id == "btn-submit-reg":
        if not car_id_input:
            return is_open, no_update, no_update, "Error: Car ID is required.", current_list, no_update, no_update, no_update, no_update, no_update, no_update, no_update
        if not user_id or user_id.strip() == "":
            return is_open, no_update, no_update, "Error: User ID is required.", current_list, no_update, no_update, no_update, no_update, no_update, no_update, no_update

        payload = {
            "car_id": car_id_input,
            "car_name": name,
            "vin_number": vin,
            "license_plate": license_pl,
            "battery_serial": battery,
            "motor_serial": motor,
            "user_id": user_id.strip()
        }

        try:
            response = requests.post(f"{API_BASE_URL}/api/ev", json=payload, timeout=10)

            if response.status_code in [200, 201]:
                resp_json = response.json()
                new_car_id = resp_json.get("car_id", car_id_input)
                new_car_name = name  

                new_list = list(current_list) if current_list else []
                found = False
                for v in new_list:
                    if v["car_id"] == new_car_id:
                        v["car_name"] = new_car_name 
                        v["user_id"] = user_id.strip()
                        found = True
                        break
                if not found:
                    new_list.append({"car_id": new_car_id, "car_name": new_car_name, "user_id": user_id.strip()})

                return (
                    False, refresh_count + 1, new_car_id, "", new_list, 
                    "", "", "", "", "", "", ""
                )
            else:
                return is_open, no_update, no_update, f"Error: {response.text}", current_list, no_update, no_update, no_update, no_update, no_update, no_update, no_update

        except Exception as e:
            return is_open, no_update, no_update, f"Connection Error: {str(e)}", current_list, no_update, no_update, no_update, no_update, no_update, no_update, no_update

    return is_open, no_update, no_update, "", current_list, no_update, no_update, no_update, no_update, no_update, no_update, no_update

# 2. Manage Vehicle List
@app.callback(
    Output("vehicle-list-container", "children"),
    [Input("vehicle-list-store", "data"),
     Input("selected-car-store", "data")]
)
def update_sidebar(vehicle_list, current_car_id):
    if not vehicle_list:
        return html.Div(
            "No vehicles registered in this session.", 
            className="p-3 text-muted text-center", 
            style={"fontSize": "12px", "fontStyle": "italic"}
        )

    buttons = []
    for v in vehicle_list:
        car_id = v.get("car_id")
        active_cls = "active" if str(car_id) == str(current_car_id) else ""
        
        btn = html.Button([
            html.Div([
                html.I(className="fa fa-car me-2", style={"opacity": 0.5}),
                html.Span(str(car_id), style={"fontWeight": "bold", "fontSize": "15px"})
            ])
        ], id={"type": "car-select-btn", "index": str(car_id)}, className=f"vehicle-btn {active_cls}")
        
        buttons.append(btn)

    return buttons


@app.callback(
    Output("selected-car-store", "data", allow_duplicate=True),
    Input({"type": "car-select-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True
)
def select_vehicle(n_clicks):
    if not ctx.triggered or all(click is None for click in n_clicks):
        raise PreventUpdate

    trigger_id = ctx.triggered_id
    
    if trigger_id and isinstance(trigger_id, dict):
        selected_car = trigger_id["index"]
        return selected_car
        
    raise PreventUpdate


# 3. Fetch Vehicle Static Details
@app.callback(
    Output("vehicle-info-content", "children"),
    Input("selected-car-store", "data")
)
def update_vehicle_static_info(car_id):
    if not car_id:
        return html.Div("No vehicle selected.", className="mt-4 text-muted")
    
    details = get_ev_details(car_id)
    
    def get_val(key):
        val = details.get(key)
        return val if val else "N/A"

    def create_row(label, value):
        return dbc.Row([
            dbc.Col(label, width=4, className="info-label"),
            dbc.Col(value, width=8, className="info-value")
        ], className="info-row")

    return html.Div([
        create_row("Car ID", f"{car_id}"),
        create_row("Vehicle Name", get_val("car_name")),
        create_row("VIN Number", get_val("vin_number")),
        create_row("License Plate", get_val("license_plate")),
        create_row("Battery Serial", get_val("battery_serial")),
        create_row("Motor Serial", get_val("motor_serial")),
        create_row("User ID", get_val("user_id")),
    ])

# --- LOG CACHE ---
log_cache_info = {}    
log_cache_debug = {}  
MAX_LOG_LINES = 50

# 4. Main Real-time Update (SSE)
@app.callback(
    [Output('status-val', 'children'), Output('soc-val', 'children'), Output('capacity-val', 'children'),
     Output('mileage-val', 'children'), Output('max-cell-val', 'children'), Output('min-cell-val', 'children'),
     Output('diff-cell-val', 'children'), Output('temp-range-val', 'children'), Output('power-val', 'children'),
     Output('speed-gauge', 'value'), Output('log-content', 'children'), Output('log-timestamp', 'children'),
     Output('top-status-text', 'children'), Output('top-status-text', 'className'), Output('log-level-store', 'data')],
    [Input('sse-data-hidden', 'children'), Input('btn-log-info', 'n_clicks'), Input('btn-log-debug', 'n_clicks')],
    [State('selected-car-store', 'data'), State('log-level-store', 'data')]
)
def update_dashboard_sse(json_data, btn_info, btn_debug, current_car_id, current_log_level):
    ctx_id = ctx.triggered_id
    if ctx_id == 'btn-log-info': current_log_level = 'INFO'
    elif ctx_id == 'btn-log-debug': current_log_level = 'DEBUG'

    if not json_data:
        return (no_update, no_update, no_update, no_update, no_update, no_update, no_update,
                no_update, no_update, no_update, no_update, no_update, no_update, no_update, current_log_level)

    try:
        data = json.loads(json_data)
    except Exception as e:
        logs = log_cache_debug.setdefault(current_car_id, [])
        logs.append(f"[DEBUG] JSON decode error: {str(e)}")
        log_cache_debug[current_car_id] = logs[-MAX_LOG_LINES:]
        return (no_update, no_update, no_update, no_update, no_update, no_update, no_update,
                no_update, no_update, no_update, no_update, no_update, no_update, no_update, current_log_level)

    if str(data.get("car_id")) != str(current_car_id):
        return (no_update, no_update, no_update, no_update, no_update, no_update, no_update,
                no_update, no_update, no_update, no_update, no_update, no_update, no_update, current_log_level)

    volt = data.get("volt_V", 0)
    current_val = data.get("current_A", 0)
    speed = data.get("avg_speed_kmh", 0)
    soc = data.get("soc_pct", 0)
    capacity = data.get("actual_max_capacity_Ah", 0)
    mileage = data.get("mileage_km", 0)
    max_single_volt = data.get("max_single_volt_V", 0)
    min_single_volt = data.get("min_single_volt_V", 0)
    min_temp = data.get("min_temp_C", 0)
    max_temp = data.get("max_temp_C", 0)
    timestamp = data.get("timestamp_s", 0)
    
    if speed > 0:
        status, cls, ui_stat, log_type = "RUNNING", "text-success fw-bold me-4", "NORMAL", "INFO"
    elif current_val < -1:
        status, cls, ui_stat, log_type = "CHARGING", "text-warning fw-bold me-4", "CHARGING", "INFO"
    else:
        status, cls, ui_stat, log_type = "STOPPED", "text-danger fw-bold me-4", "IDLE", "INFO"

    log_msg = f"EV-{current_car_id} status: {status}, data received"

    target_cache = log_cache_info if log_type == "INFO" else log_cache_debug
    logs = target_cache.setdefault(current_car_id, [])
    logs.append(f"[{timestamp}] [{log_type}] {log_msg}")
    target_cache[current_car_id] = logs[-MAX_LOG_LINES:]

    display_logs = log_cache_info.get(current_car_id, []) if current_log_level == "INFO" else log_cache_debug.get(current_car_id, [])

    return (
        ui_stat, 
        f"{soc}", 
        f"{capacity}", 
        f"{mileage:,.1f}",
        f"{max_single_volt:.3f}", 
        f"{min_single_volt:.3f}",
        f"{(max_single_volt - min_single_volt):.3f}",
        f"{min_temp} - {max_temp}°C", 
        f"{volt * current_val / 1000:.1f} kW", 
        speed, 
        html.Pre("\n".join(display_logs), style={"whiteSpace": "pre-wrap", "fontSize": "11px"}),
        f"Last update: {timestamp}", 
        status, 
        cls, 
        current_log_level
    )

# 5. HDFS Historical Chart
METRIC_LABELS = {
    "soc_pct": "SOC (%)",
    "volt_V": "Voltage (V)",
    "current_A": "Current (A)",
    "max_temp_C": "Temp Max (°C)",
    "avg_speed_kmh": "Speed (km/h)",
    "actual_max_capacity_Ah": "Capacity (Ah)",
}

@app.callback(
    [Output("hdfs-history-chart", "figure"),
     Output("hdfs-status-text", "children")],
    [Input("btn-load-hdfs", "n_clicks")],
    [State("selected-car-store", "data"),
     State("hdfs-metric-dropdown", "value")],
    prevent_initial_call=True
)
def load_hdfs_history(n_clicks, car_id, metric):
    if not car_id or not metric:
        raise PreventUpdate

    empty_fig = go.Figure(layout=dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=10, b=40), height=240,
    ))

    try:
        resp = requests.get(
            f"{API_BASE_URL}/api/hdfs/history/{car_id}",
            params={"metric": metric, "limit": 1000},
            timeout=30,
        )
    except Exception as e:
        return empty_fig, f"Connection error: {str(e)}"

    if resp.status_code != 200:
        return empty_fig, f"Server error {resp.status_code}: {resp.text[:120]}"

    data = resp.json()
    error = data.get("error")
    if error:
        return empty_fig, f"HDFS: {error}"

    timestamps = data.get("timestamps", [])
    values = data.get("values", [])

    if not timestamps:
        return empty_fig, "No data returned from HDFS."

    label = METRIC_LABELS.get(metric, metric)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=values,
        mode="lines",
        line=dict(color="#1890ff", width=2),
        fill="tozeroy",
        fillcolor="rgba(24,144,255,0.08)",
        name=label,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=10, b=40),
        height=240,
        xaxis=dict(title="Timestamp (s)", showgrid=True, gridcolor="#eee", tickfont=dict(size=10)),
        yaxis=dict(title=label, showgrid=True, gridcolor="#eee", tickfont=dict(size=10)),
        showlegend=False,
    )

    file_name = data.get("file", "")
    rows = data.get("rows", 0)
    return fig, f"Loaded {rows} points from {file_name}"


if __name__ == '__main__':
    app.run_server(debug=True, port=9050)