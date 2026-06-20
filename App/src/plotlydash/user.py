import dash
import os
import argparse
from dash import dcc, html, Dash
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd
import requests

# ======================
# --- APP INITIALIZATION ---
# ======================
parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=9001)  
parser.add_argument("--car_id", type=str, default="EV_101", help="The ID of the car")
parser.add_argument("--car_name", type=str, default="Unknown Model", help="The model name of the car")
parser.add_argument("--vin", type=str, default="N/A", help="The Vehicle Identification Number (VIN)")
args = parser.parse_args()

BACKEND_PORT = int(os.getenv("BACKEND_PORT", 8001))
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}/api/latest"

app = Dash(__name__)

# ======================
# --- COLOR & FONT CONFIGURATION ---
# ======================
colors = {
    'background': '#000000',
    'card_bg': '#0f1112',
    'text': '#ffffff',
    'cyan': '#00f2ff',
    'green': '#76c65e',
    'red': '#ff3b3b',
    'red_bg': 'rgba(255, 59, 59, 0.15)',
    'gray_label': '#6e7f8d',
    'border': '#333333'
}

# ======================
# --- INITIAL DATA STATE ---
# ======================
df_trend = pd.DataFrame({'x': [], 'y': []})

# ======================
# --- CHARTING & COMPONENT FUNCTIONS ---
# ======================
def create_speedometer(speed=0):
    fig = go.Figure(go.Indicator(
        mode="gauge", 
        value=speed,
        gauge={
            'axis': {
                'range': [0, 220], 
                'tickwidth': 2, 
                'tickcolor': 'white',
                'tickmode': 'linear', 
                'dtick': 20,
                'tickfont': {'size': 18, 'color': 'white', 'family': 'Arial'}
            },
            'bar': {'color': '#ff3b3b', 'thickness': 1},
            'bgcolor': '#0f1112',
            'borderwidth': 2,
            'bordercolor': '#ffffff',
            'steps': [] 
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        font={'color': 'white', 'family': 'Arial'},
        margin={'l': 25, 'r': 40, 't': 30, 'b': 30},
        height=300
    )
    return fig

def create_trend_chart():
    fig = go.Figure()
    
    if not df_trend.empty:
        fig.add_trace(go.Scatter(
            x=df_trend['x'], 
            y=df_trend['y'],
            mode='lines',
            line=dict(
                color=colors['cyan'], 
                width=3, 
                shape='spline'
            ),
            fill='tozeroy',
            fillcolor='rgba(0, 242, 255, 0.1)',
            hoverinfo='y'
        ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=5, b=0),
        height=80,
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            fixedrange=True
        ),
        yaxis=dict(
            showgrid=False, 
            zeroline=False, 
            showticklabels=False,
            fixedrange=True,
            range=[df_trend['y'].min() - 1, df_trend['y'].max() + 1] if not df_trend.empty else [0, 100]
        ),
        showlegend=False
    )
    return fig

def info_box(label, value, unit, value_id=None):
    return html.Div([
        html.Div([
            html.Span(f"{label}:", style={'color': colors['gray_label'], 'fontSize': '14px'}),
            html.Div([
                html.Span(
                    value,
                    id=value_id,
                    style={
                        'color': colors['text'],
                        'fontWeight': 'bold',
                        'fontSize': '16px',
                        'marginRight': '5px'
                    }
                ),
                html.Span(unit, style={'color': colors['cyan'], 'fontSize': '14px'})
            ])
        ]),
        html.Div(style={
            'height': '3px', 'width': '40px',
            'backgroundColor': colors['cyan'],
            'borderRadius': '2px'
        })
    ], style={
        'backgroundColor': '#141618',
        'borderRadius': '12px',
        'padding': '12px 15px',
        'marginBottom': '12px',
        'border': '1px solid #222'
    })

def battery_visual(percent="0%"):
    return html.Div([
        html.Div([  
             html.Div(style={
                'width': f'{percent}', 'height': '100%', 
                'background': f'linear-gradient(to right, {colors["green"]}, #a8e063)',
                'borderRadius': '2px',
                'transition': 'width 0.3s ease' 
            })
        ], style={
            'width': '70px', 'height': '35px', 
            'border': '2px solid #aaa', 'borderRadius': '6px', 'padding': '2px',
            'display': 'flex'
        }),
        html.Div(style={  
            'width': '4px', 'height': '14px', 'backgroundColor': '#aaa',
            'borderTopRightRadius': '3px', 'borderBottomRightRadius': '3px', 'marginLeft': '1px'
        }),
    ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '20px'})

# ======================
# --- MAIN LAYOUT ---
# ======================
app.layout = html.Div(style={
    'backgroundColor': colors['background'],
    'minHeight': '100vh',
    'display': 'flex',
    'justifyContent': 'center',
    'alignItems': 'center',
    'fontFamily': 'Arial, sans-serif'
}, children=[
    html.Div(style={
        'backgroundColor': colors['card_bg'],
        'width': '1050px',
        'height': '450px',
        'borderRadius': '25px',
        'boxShadow': '0 0 30px rgba(0,0,0,0.9)',
        'padding': '30px',
        'display': 'flex',
        'flexDirection': 'row',
        'border': '1px solid #333',
        'position': 'relative'
    }, children=[

        html.Button("00", id="label-btn", n_clicks=0, style={
            'position': 'absolute','top': '20px','left': '20px',
            'backgroundColor': colors['green'],'color': '#000',
            'border': 'none','borderRadius': '8px','padding': '8px 15px',
            'fontWeight': 'bold','cursor': 'pointer','zIndex': '10'
        }),

        # --- STATUS BOX  ---
        html.Div(id='status-box', style={
            'position': 'absolute', 'top': '20px', 'right': '20px',
            'borderRadius': '5px', 'padding': '8px 20px',
            'zIndex': '10', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
            'border': '1px solid #333',
            'minWidth': '100px' 
        }, children=[
             html.Span("WAITING...", style={'color': 'white'})
        ]),

        # Left Panel (Speedometer)
        html.Div(style={'width': '35%','position': 'relative'}, children=[
            dcc.Graph(id='speedometer', figure=create_speedometer(0), config={'displayModeBar': False}),
            
            # HTML Overlay for Speed Value (Centered)
            html.Div([
                html.Div("0", id='speed-display', style={
                    'fontSize': '90px',
                    'fontWeight': 'bold',
                    'color': 'white',
                    'lineHeight': '1',
                    'textShadow': '0 0 10px rgba(255, 255, 255, 0.5)'
                }),
                html.Div("km/h", style={'fontSize':'20px','color':'#aaa','marginTop':'5px', 'textTransform': 'uppercase'})
            ], style={
                'textAlign': 'center',
                'width': '100%',
                'position': 'absolute',
                'top': '50%',
                'left': '50%',
                'transform': 'translate(-50%, -20%)', 
                'zIndex': '5'
            }),

            html.Div([
                # Car ID
                html.Div([
                    html.Span("Car ID:", style={'color':'#666'}), 
                    html.Span(f" {args.car_id}", style={'color':'#aaa','fontWeight':'bold'})
                ], style={'fontSize':'20px'}),
                
                # Car Name
                html.Div([
                    html.Span("Car Name:", style={'color':'#666'}), 
                    html.Span(f" {args.car_name}", style={'color':'#aaa'})
                ], style={'fontSize':'13px','marginTop':'4px'}),
                
                # VIN
                html.Div([
                    html.Span("VIN:", style={'color':'#666'}), 
                    html.Span(f" {args.vin}", style={'color':'#aaa'})
                ], style={'fontSize':'11px','marginTop':'2px'})
                
            ], style={'position': 'absolute','bottom':'0','left':'10px'})
        ]),

        # Right Panel (Stats & Trend)
        html.Div(style={'width':'65%','paddingLeft':'30px','display':'flex','flexDirection':'column'}, children=[
            html.Div(style={'display':'flex','justifyContent':'space-between','alignItems':'center','marginTop':'100px','paddingBottom':'20px'}, children=[
                html.Div(style={'width':'180px'}, children=[
                    info_box("Voltage", "0", "V", value_id="volt-val"),
                    info_box("Current", "0", "A", value_id="current-val"),
                    info_box("Capacity", "0", "Ah", value_id="capacity-val"),
                ]),
                html.Div(style={'flex':'1','display':'flex','flexDirection':'column','alignItems':'center','justifyContent':'center'}, children=[
                    html.Div(id='battery-container', children=battery_visual("0%")),  
                    html.Div([html.Span("SOC:", style={'color':colors['text'],'fontSize':'35px','marginRight':'20px'}),
                    html.Span("0%", id='soc-val', style={'color':colors['text'],'fontSize':'35px','fontWeight':'bold'})])
                ]),
                html.Div(style={'width':'180px'}, children=[
                    info_box("Max Temp", "0", "°C", value_id="max-temp-val"),
                    info_box("Min Temp", "0", "°C", value_id="min-temp-val"),
                    info_box("Mileage", "0", "km", value_id="mileage-val") 
                ])
            ]),
            html.Div(style={'marginTop':'auto'}, children=[
                html.Div("Voltage Trend", style={'color':'white','fontSize':'14px','fontWeight':'bold','marginBottom':'5px'}),
                dcc.Graph(
                    id='voltage-trend',
                    figure=create_trend_chart(), 
                    config={'displayModeBar': False},
                    style={'width': '100%'}
                ),
                html.Div([html.Div(style={'flex':'1','height':'1px','backgroundColor':colors['cyan']}),
                        html.Div("Timestp: 0.0 minsec", id='timestamp-val', style={'color':'#666','fontSize':'10px','marginLeft':'10px'})],
                        style={'display':'flex','alignItems':'center','marginTop':'-5px'}) 
            ])
        ])
    ]),
    
    dcc.Interval(id='interval-ev', interval=2000, n_intervals=0) # Update interval increased to 2 seconds
])

# ======================
# --- 00/10 CALLBACK ---
# ======================
@app.callback(
    Output("label-btn", "children"),
    Output("label-btn", "style"),
    Input("label-btn", "n_clicks"),
    State("label-btn", "children"),
    State("label-btn", "style"),  
    prevent_initial_call=True
)
def toggle_label(n_clicks, current_text, current_style):
    if current_text == "00":
        new_label = 10
        new_text = "10"
        color = colors['red']
        text_color = '#fff'
    else:
        new_label = 0
        new_text = "00"
        color = colors['green']
        text_color = '#000'

    try:
        requests.post(
            f"http://127.0.0.1:{BACKEND_PORT}/api/set_label",
            json={"label": new_label},
            timeout=0.3
        )
    except Exception as e:
        print(f"[UI -> Backend {BACKEND_PORT}] Label Error: {e}")

    updated_style = current_style.copy()
    updated_style['backgroundColor'] = color
    updated_style['color'] = text_color

    return new_text, updated_style

# ======================
# --- DATA UPDATE CALLBACK ---
# ======================
@app.callback(
    Output('speed-display','children'),
    Output('speedometer','figure'),
    Output('soc-val','children'),
    Output('voltage-trend','figure'),
    Output('timestamp-val','children'),
    Output('mileage-val','children'),

    Output('volt-val','children'),
    Output('current-val','children'),
    Output('capacity-val','children'),
    Output('max-temp-val','children'),
    Output('min-temp-val','children'),
    Output('battery-container','children'), 
    
    Output('status-box', 'style'),
    Output('status-box', 'children'),

    Input('interval-ev','n_intervals')
)
def update_ev_data(n):
    global df_trend

    try:
        r = requests.get(BACKEND_URL, timeout=0.3)
        data = r.json()
    except Exception as e:
        data = {}

    # ---------------------------------------------------------
    # MAPPED ACCORDING TO KAFKA_SCHEMA_FIELDS
    # ---------------------------------------------------------
    try:
        label = int(data.get("label", 0)) 
    except:
        label = 0

    # Fetch data based on actual schema field names
    volt = round(float(data.get("volt_V", 0)), 2)
    current = round(float(data.get("current_A", 0)), 2)
    
    # For capacity, use actual_max_capacity_Ah or nominal_capacity_Ah depending on business logic
    capacity = round(float(data.get("nominal_capacity_Ah", 0)), 2) 
    
    soc = round(float(data.get("soc_pct", 0)), 2)
    max_temp = round(float(data.get("max_temp_C", 0)), 1)
    min_temp = round(float(data.get("min_temp_C", 0)), 1)
    mileage = round(float(data.get("mileage_km", 0)), 2)
    timestamp = data.get("timestamp_s", 0)
    
    # Map speed to avg_speed_kmh
    try:
        speed = round(float(data.get("avg_speed_kmh", 0)), 1)
    except:
        speed = 0

    current_time = pd.Timestamp.now()
    new_row = pd.DataFrame({'x': [current_time], 'y': [volt]})
    
    if df_trend.empty:
        df_trend = new_row
    else:
        df_trend = pd.concat([df_trend, new_row], ignore_index=True)
    
    if len(df_trend) > 50:
        df_trend = df_trend.iloc[-50:]

    fig_trend = create_trend_chart() 
    battery_component = battery_visual(f"{soc}%")

    base_style = {
        'position': 'absolute', 'top': '20px', 'right': '20px',
        'borderRadius': '5px', 'padding': '8px 20px',
        'zIndex': '10', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
        'transition': 'all 0.3s ease',
        'minWidth': '100px'
    }

    if label == 10:
        status_style = {**base_style, 
            'backgroundColor': 'rgba(255, 59, 59, 0.2)',
            'border': f'2px solid {colors["red"]}',
            'boxShadow': f'0 0 15px {colors["red"]}'
        }
        status_content = html.Span("ANOMALY", style={'fontWeight': 'bold', 'color': colors['red'], 'fontSize': '16px', 'letterSpacing': '1px'})
        
    else:
        status_style = {**base_style, 
            'backgroundColor': 'rgba(118, 198, 94, 0.2)',
            'border': f'2px solid {colors["green"]}',
            'boxShadow': f'0 0 10px {colors["green"]}'
        }
        status_content = html.Span("NORMAL", style={'fontWeight': 'bold', 'color': colors['green'], 'fontSize': '16px', 'letterSpacing': '1px'})

    return (
        f"{int(speed)}", 
        create_speedometer(speed),
        f"{soc}%",
        fig_trend,
        f"Timestamp: {timestamp}",
        f"{mileage:,.2f}", # Return raw number, info_box layout handles unit concatenation
        f"{volt}",
        f"{current}",
        f"{capacity}",
        f"{max_temp}",
        f"{min_temp}",
        battery_component,
        status_style,   
        status_content  
    )

# ======================
# --- SERVER EXECUTION ---
# ======================
if __name__ == '__main__':
    app.run_server(host="0.0.0.0", port=args.port, debug=False)