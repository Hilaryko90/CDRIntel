# =====================================================
# IMPORTS
# =====================================================
import os
import io
import base64
import hashlib
import pandas as pd
from flask import Flask, redirect, request
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import dash
from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from sklearn.ensemble import IsolationForest

# =====================================================
# FLASK SERVER
# =====================================================
server = Flask(__name__)
server.secret_key = "cdr-intel-secret-key"

login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "/login"

# =====================================================
# USERS
# =====================================================
USERS = {
    "admin": {"password": hashlib.sha256("admin123".encode()).hexdigest(), "color": "#0d6efd"},
    "analyst": {"password": hashlib.sha256("analyst123".encode()).hexdigest(), "color": "#198754"},
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.color = USERS[username]["color"]

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in USERS else None

# =====================================================
# LOGIN ROUTES
# =====================================================
@server.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in USERS:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            if USERS[username]["password"] == hashed:
                login_user(User(username))
                return redirect("/dashboard/")
        return "Invalid credentials", 401
    return """
    <h2>CDR Intel Login</h2>
    <form method="post">
        <input name="username" placeholder="Username"><br><br>
        <input name="password" type="password" placeholder="Password"><br><br>
        <button type="submit">Login</button>
    </form>
    """

@server.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# =====================================================
# HELPERS
# =====================================================
def normalize_columns(df):
    df.columns = [c.lower().strip() for c in df.columns]

    if "caller" not in df.columns and "calling_number" in df.columns:
        df["caller"] = df["calling_number"]

    if "receiver" not in df.columns and "called_number" in df.columns:
        df["receiver"] = df["called_number"]

    if "duration" not in df.columns:
        df["duration"] = 0

    if "timestamp" not in df.columns:
        df["timestamp"] = pd.Timestamp.now()
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df

# =====================================================
# CDR INGESTION
# =====================================================
def ingest_cdr_files(folder="cdr_files"):
    folder_path = os.path.join(os.getcwd(), folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return pd.DataFrame()
    
    dfs = []
    for f in os.listdir(folder_path):
        path = os.path.join(folder_path, f)
        try:
            if f.endswith(".csv"):
                df = pd.read_csv(path)
            elif f.endswith((".xlsx", ".xls")):
                df = pd.read_excel(path)
            else:
                continue
            df = normalize_columns(df)
            dfs.append(df)
        except Exception as e:
            print("Error reading", f, e)
    
    if not dfs:
        return pd.DataFrame()
    
    return pd.concat(dfs, ignore_index=True)

# =====================================================
# ANALYTICS ENGINE
# =====================================================
def analyze_cdr(df):
    result = {
        "summary": {},
        "insights": [],
        "network_graph": None,
        "timeline": None,
        "geo_map": None,
        "anomalies": pd.DataFrame()
    }

    if df.empty:
        return result

    # Summary
    result["summary"]["total_calls"] = len(df)
    result["summary"]["total_duration"] = df["duration"].sum()
    result["summary"]["avg_duration"] = df["duration"].mean()

    # Top callers
    if "caller" in df.columns:
        top_callers = df["caller"].value_counts().head(5)
        for caller, count in top_callers.items():
            result["insights"].append(f"Top caller: {caller} with {count} calls")

    # Anomaly detection
    clf = IsolationForest(contamination=0.05, random_state=42)
    df["duration_norm"] = df["duration"].fillna(0).values.reshape(-1, 1)
    df["anomaly_score"] = clf.fit_predict(df[["duration_norm"]])
    anomalies = df[df["anomaly_score"] == -1]
    result["anomalies"] = anomalies
    for _, row in anomalies.iterrows():
        result["insights"].append(
            f"⚠️ Anomalous call: {row.get('caller')} → {row.get('receiver')} ({row.get('duration')} sec)"
        )

    # Network graph
    if "caller" in df.columns and "receiver" in df.columns:
        G = nx.from_pandas_edgelist(
            df,
            source="caller",
            target="receiver",
            edge_attr="duration",
            create_using=nx.DiGraph()
        )
        pos = nx.spring_layout(G, k=0.5)
        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]; x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y, line=dict(width=1, color='#888'),
            hoverinfo='none', mode='lines'
        )

        node_x, node_y, node_text, node_color = [], [], [], []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x); node_y.append(y); node_text.append(node)
            node_color.append(
                'red' if df[df['caller'] == node]['anomaly_score'].sum() < 0 else 'blue'
            )
        node_trace = go.Scatter(
            x=node_x, y=node_y, mode='markers+text', text=node_text,
            hoverinfo='text', marker=dict(size=20, color=node_color)
        )
        network_fig = go.Figure(data=[edge_trace, node_trace])
        network_fig.update_layout(title="Call Network Graph", showlegend=False)
        result["network_graph"] = network_fig

    # Timeline
    if "timestamp" in df.columns and not df["timestamp"].isnull().all():
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        timeline = df.groupby(pd.Grouper(key="timestamp", freq="h")).size().reset_index(name="calls")
        result["timeline"] = px.line(timeline, x="timestamp", y="calls", title="Call Timeline (Hourly)")

    # Geo map
    if "lat" in df.columns and "lon" in df.columns:
        result["geo_map"] = px.scatter_mapbox(
            df, lat="lat", lon="lon", hover_name="caller",
            color="duration", size="duration", zoom=5,
            mapbox_style="open-street-map", title="Call Geo Map"
        )

    return result

# =====================================================
# LOAD INITIAL DATA
# =====================================================
cdr_df = ingest_cdr_files()
intel = analyze_cdr(cdr_df)

# =====================================================
# DASH APP
# =====================================================
app = dash.Dash(
    __name__, server=server, url_base_pathname="/dashboard/",
    external_stylesheets=[dbc.themes.BOOTSTRAP]
)

app.layout = dbc.Container([
    html.H1("📊 CDR Intel Dashboard", className="text-center my-4"),
    dbc.Button("Logout", href="/logout", color="danger"),
    html.Hr(),
    html.H3("📊 Intelligence Summary"),
    html.Ul([html.Li(f"{k}: {v}") for k,v in intel["summary"].items()]),
    html.H4("🚨 Actionable Intelligence"),
    html.Ul([html.Li(text) for text in intel["insights"]]),
    html.Hr(),
    html.H3("📁 CDR Records"),
    dbc.Row([
        dbc.Col(dcc.Input(id="filter-caller", placeholder="Filter by Caller", type="text"), width=3),
        dbc.Col(dcc.Input(id="filter-receiver", placeholder="Filter by Receiver", type="text"), width=3),
        dbc.Col(dcc.DatePickerRange(
            id="filter-date",
            start_date=cdr_df["timestamp"].min() if not cdr_df.empty else None,
            end_date=cdr_df["timestamp"].max() if not cdr_df.empty else None
        ), width=6)
    ], className="mb-3"),
    dash_table.DataTable(
        id="cdr-table",
        data=cdr_df.to_dict("records"),
        columns=[{"name": i, "id": i} for i in cdr_df.columns],
        page_size=10, filter_action="native", sort_action="native",
        style_table={"overflowX": "auto"},
    ),
    html.Hr(),
    html.H3("⏱ Call Timeline"),
    dcc.Graph(id="timeline-graph", figure=intel["timeline"] if intel["timeline"] else {}),
    html.H3("🗺 Call Geo Map"),
    dcc.Graph(id="geo-map", figure=intel["geo_map"] if intel["geo_map"] else {}),
    html.H3("📡 Call Network Graph"),
    dcc.Graph(id="network-graph", figure=intel["network_graph"] if intel["network_graph"] else {}),
    html.Hr(),
    dbc.Row([
        dbc.Col(dcc.Upload(
            id='upload-cdr',
            children=html.Div(['📤 Drag and Drop or ', html.A('Select CDR File')]),
            style={
                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                'textAlign': 'center'
            },
            multiple=True
        ), width=6),
        dbc.Col(dbc.Button("📥 Download Evidence Report", id="download-btn", color="success"), width=6)
    ]),
    dcc.Download(id="download-report")
], fluid=True)

# =====================================================
# DASH CALLBACKS
# =====================================================
@app.callback(
    Output("cdr-table", "data"),
    Output("timeline-graph", "figure"),
    Output("geo-map", "figure"),
    Output("network-graph", "figure"),
    Input("filter-caller", "value"),
    Input("filter-receiver", "value"),
    Input("filter-date", "start_date"),
    Input("filter-date", "end_date"),
    Input("upload-cdr", "contents"),
    State("upload-cdr", "filename")
)
def update_dashboard(caller, receiver, start_date, end_date, uploaded_contents, filenames):
    global cdr_df

    # Handle file upload
    if uploaded_contents is not None:
        os.makedirs("cdr_files", exist_ok=True)
        for content, name in zip(uploaded_contents, filenames):
            content_type, content_string = content.split(',')
            decoded_bytes = base64.b64decode(content_string)
            with open(f"cdr_files/{name}", "wb") as f:
                f.write(decoded_bytes)
            data = io.BytesIO(decoded_bytes)
            if name.endswith(".csv"):
                df_new = pd.read_csv(data)
            elif name.endswith((".xlsx", ".xls")):
                df_new = pd.read_excel(data)
            else:
                continue
            df_new = normalize_columns(df_new)
            cdr_df = pd.concat([cdr_df, df_new], ignore_index=True)
        print("CDR records loaded:", len(cdr_df))

    intel_updated = analyze_cdr(cdr_df)

    df_filtered = cdr_df.copy()
    if caller: df_filtered = df_filtered[df_filtered["caller"].str.contains(caller, case=False, na=False)]
    if receiver: df_filtered = df_filtered[df_filtered["receiver"].str.contains(receiver, case=False, na=False)]
    if start_date: df_filtered = df_filtered[df_filtered["timestamp"] >= pd.to_datetime(start_date)]
    if end_date: df_filtered = df_filtered[df_filtered["timestamp"] <= pd.to_datetime(end_date)]

    return (
        df_filtered.to_dict("records"),
        intel_updated["timeline"] if intel_updated["timeline"] else {},
        intel_updated["geo_map"] if intel_updated["geo_map"] else {},
        intel_updated["network_graph"] if intel_updated["network_graph"] else {}
    )

@app.callback(
    Output("download-report", "data"),
    Input("download-btn", "n_clicks"),
    prevent_initial_call=True
)
def generate_report(n_clicks):
    buffer = io.StringIO()
    cdr_df.to_csv(buffer, index=False)
    buffer.seek(0)
    return dcc.send_string(buffer.getvalue(), "cdr_evidence_report.csv")

# =====================================================
# PROTECT DASHBOARD
# =====================================================
@server.before_request
def protect_dashboard():
    if request.path.startswith("/dashboard") and not current_user.is_authenticated:
        return redirect("/login")

# =====================================================
# RUN SERVER
# =====================================================
if __name__ == "__main__":
    server.run(debug=True)