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

# Global DataFrame to store cases
# -------------------------------
case_df = pd.DataFrame(columns=["Case ID", "Case Description", "Targets"])

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
# AI INTELLIGENCE SUMMARY
# =====================================================
def generate_intelligence_report(df, intel):
    if df.empty:
        return ["No CDR data available"]

    insights = []

    total_calls = len(df)
    unique_callers = df["caller"].nunique()
    unique_receivers = df["receiver"].nunique()

    insights.append(f"Total calls analyzed: {total_calls}")
    insights.append(f"Unique callers: {unique_callers}")
    insights.append(f"Unique receivers: {unique_receivers}")

    # Suspicious activity detection
    high_freq = df["caller"].value_counts()
    suspicious_numbers = high_freq[high_freq > high_freq.mean() * 3]

    if not suspicious_numbers.empty:
        for number, count in suspicious_numbers.items():
            insights.append(f"⚠️ High activity detected from {number} ({count} calls)")

    # Long duration calls
    long_calls = df[df["duration"] > df["duration"].mean() * 3]
    if not long_calls.empty:
        insights.append(f"⚠️ {len(long_calls)} unusually long calls detected")

    # Night activity pattern
    if "timestamp" in df.columns:
        night_calls = df[df["timestamp"].dt.hour.between(0, 5)]
        if len(night_calls) > total_calls * 0.3:
            insights.append("⚠️ Heavy night-time call activity detected")

    # Risk score
    anomaly_count = len(intel["anomalies"])
    risk_score = min(100, int((anomaly_count / max(total_calls, 1)) * 500))
    insights.append(f"Fraud Risk Score: {risk_score}/100")

    if risk_score > 70:
        insights.append("🚨 HIGH RISK communication pattern detected")
    elif risk_score > 40:
        insights.append("⚠️ MODERATE RISK pattern detected")
    else:
        insights.append("✅ Low risk pattern")

    return insights

html.H3("🕵️ Investigation Assessment"),
html.H4(id="risk-score"),
html.Ul(id="investigation-findings"),


# =====================================================
# INVESTIGATION ENGINE
# =====================================================
def run_investigation(df, intel):
    case = get_active_case()
    report = {
        "risk_score": 0,
        "findings": []
    }

    if df.empty or not case:
        return report

    targets = set(case["targets"])
    risk = 0

    # ---------- TARGET CONTACTS ----------
    for number in targets:
        hits = df[(df["caller"] == number) | (df["receiver"] == number)]
        if not hits.empty:
            text = f"Target activity detected: {number} ({len(hits)} calls)"
            report["findings"].append(text)
            risk += len(hits)

    # ---------- ANOMALIES ----------
    anomalies = intel["anomalies"]
    if not anomalies.empty:
        report["findings"].append(f"{len(anomalies)} anomalous calls detected")
        risk += len(anomalies) * 2

    # ---------- HIGH FREQUENCY LINKS ----------
    pairs = df.groupby(["caller", "receiver"]).size().reset_index(name="count")
    strong = pairs[pairs["count"] > pairs["count"].mean() * 3]
    for _, row in strong.iterrows():
        report["findings"].append(
            f"Strong communication: {row['caller']} ↔ {row['receiver']}"
        )
        risk += 5

    report["risk_score"] = min(100, risk)

    case["risk_score"] = report["risk_score"]
    case["findings"] = report["findings"]

    return report


    # ---------- WATCHLIST ----------
    WATCHLIST = {"99999", "12345", "55555"}  # add real targets here

    for number in WATCHLIST:
        hits = df[(df["caller"] == number) | (df["receiver"] == number)]
        if not hits.empty:
            report["watchlist_hits"].append(f"Watchlist contact detected: {number} ({len(hits)} calls)")

    # ---------- COMMUNICATION CLUSTERS ----------
    if "caller" in df.columns and "receiver" in df.columns:
        pairs = df.groupby(["caller", "receiver"]).size().reset_index(name="count")
        strong_links = pairs[pairs["count"] > pairs["count"].mean() * 3]

        for _, row in strong_links.iterrows():
            report["clusters"].append(
                f"High-frequency link: {row['caller']} ↔ {row['receiver']} ({row['count']} calls)"
            )

    # ---------- SUSPICIOUS TIMELINE ----------
    if "timestamp" in df.columns:
        df["hour"] = df["timestamp"].dt.hour
        night_activity = df[df["hour"].between(0, 5)]
        if len(night_activity) > len(df) * 0.25:
            report["suspicious_timeline"].append("Heavy communication during night hours")

    # ---------- RISK SCORE ----------
    anomaly_count = len(intel["anomalies"])
    watchlist_weight = len(report["watchlist_hits"]) * 15
    cluster_weight = len(report["clusters"]) * 10
    anomaly_weight = anomaly_count * 2

    score = anomaly_weight + watchlist_weight + cluster_weight
    report["risk_score"] = min(100, score)

    # ---------- FINDINGS ----------
    if report["risk_score"] > 70:
        report["findings"].append("🚨 High-risk communication network detected")
    elif report["risk_score"] > 40:
        report["findings"].append("⚠️ Suspicious behavioral patterns detected")
    else:
        report["findings"].append("No critical threats detected")

    report["findings"].extend(report["watchlist_hits"])
    report["findings"].extend(report["clusters"])
    report["findings"].extend(report["suspicious_timeline"])

    return report


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
    html.H3("🧠 AI Intelligence Assessment"),
    html.Ul(id="ai-report"),
    html.Ul([html.Li(text) for text in intel["insights"]]),
    html.Hr(),
    html.Hr(),

# ================= Analyst Case Workspace =================
html.H3("📂 Analyst Case Workspace"),
dbc.Row([
    dbc.Col(dcc.Input(id="case-id-input", placeholder="Case ID"), width=3),
    dbc.Col(dcc.Input(id="case-desc-input", placeholder="Case Description"), width=4),
    dbc.Col(dcc.Input(id="case-targets-input", placeholder="Targets (comma-separated)"), width=3),
    dbc.Col(dbc.Button("Create Case", id="create-case-btn", n_clicks=0, color="primary"), width=2)
], className="mb-3"),
dash_table.DataTable(
    id="case-table",
    columns=[
        {"name": "Case ID", "id": "Case ID"},
        {"name": "Case Description", "id": "Case Description"},
        {"name": "Targets", "id": "Targets"}
    ],
    data=[],
    page_size=5,
    style_table={"overflowX": "auto"}
),
html.Hr(),

html.H3("📁 CDR Records"),

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
# CASE MANAGEMENT
# =====================================================
CASES = {}
ACTIVE_CASE = {"id": None}

def create_case(case_id, description, targets):
    CASES[case_id] = {
        "description": description,
        "targets": targets,
        "findings": [],
        "risk_score": 0
    }
    ACTIVE_CASE["id"] = case_id

def get_active_case():
    cid = ACTIVE_CASE["id"]
    return CASES.get(cid) if cid else None

# =====================================================
# DASH CALLBACKS
# =====================================================
from dash import ctx

# -------------------------------
# CREATE NEW CASE
# -------------------------------
@app.callback(
    Output("case-table", "data"),
    Input("create-case-btn", "n_clicks"),
    State("case-id-input", "value"),
    State("case-desc-input", "value"),
    State("case-targets-input", "value"),
    prevent_initial_call=True
)
def create_new_case(n_clicks, case_id, description, targets):
    global case_df
    if n_clicks:
        if not case_id or not description:
            return dash.no_update
        new_case = {
            "Case ID": case_id.strip(),
            "Case Description": description.strip(),
            "Targets": targets.strip() if targets else ""
        }
        case_df = pd.concat([case_df, pd.DataFrame([new_case])], ignore_index=True)
        return case_df.to_dict("records")
    return dash.no_update

# -------------------------------
# UPDATE DASHBOARD BASED ON FILTERS & UPLOADS
# -------------------------------
@app.callback(
    Output("cdr-table", "data"),
    Output("timeline-graph", "figure"),
    Output("geo-map", "figure"),
    Output("network-graph", "figure"),
    Output("ai-report", "children"),
    Output("risk-score", "children"),
    Output("investigation-findings", "children"),
    Output("active-case-info", "children"),
    Output("case-risk-score", "children"),
    Output("case-findings", "children"),
    Input("filter-caller", "value"),
    Input("filter-receiver", "value"),
    Input("filter-date", "start_date"),
    Input("filter-date", "end_date"),
    Input("upload-cdr", "contents"),
    Input("create-case-btn", "n_clicks"),
    State("case-id-input", "value"),
    State("case-desc-input", "value"),
    State("case-targets-input", "value"),
    State("upload-cdr", "filename")
)
def update_dashboard_case(caller, receiver, start_date, end_date, uploaded_contents, n_clicks,
                          case_id, case_desc, case_targets, filenames):
    global cdr_df, case_df

    # ---- Handle uploaded CDR files ----
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

    # ---- Create new case if button pressed ----
    active_case_info = ""
    case_risk_score = ""
    case_findings = []

    if ctx.triggered_id == "create-case-btn" and case_id:
        targets_list = [t.strip() for t in case_targets.split(",")] if case_targets else []
        new_case = {
            "Case ID": case_id.strip(),
            "Case Description": case_desc.strip() if case_desc else "",
            "Targets": ", ".join(targets_list)
        }
        case_df = pd.concat([case_df, pd.DataFrame([new_case])], ignore_index=True)
        active_case_info = f"Active Case: {case_id} — {case_desc}"

    # ---- Filter CDRs based on inputs ----
    df_filtered = cdr_df.copy()
    if caller:
        df_filtered = df_filtered[df_filtered["caller"].str.contains(caller, case=False, na=False)]
    if receiver:
        df_filtered = df_filtered[df_filtered["receiver"].str.contains(receiver, case=False, na=False)]
    if start_date:
        df_filtered = df_filtered[df_filtered["timestamp"] >= pd.to_datetime(start_date)]
    if end_date:
        df_filtered = df_filtered[df_filtered["timestamp"] <= pd.to_datetime(end_date)]

    # ---- Apply active case filter if targets exist ----
    if ctx.triggered_id == "create-case-btn" and case_targets:
        targets = [t.strip() for t in case_targets.split(",")]
        df_filtered = df_filtered[df_filtered["caller"].isin(targets) | df_filtered["receiver"].isin(targets)]

    # ---- Analytics ----
    intel_updated = analyze_cdr(df_filtered)
    ai_report = generate_intelligence_report(df_filtered, intel_updated)
    investigation = run_investigation(df_filtered, intel_updated)

    # ---- Prepare outputs ----
    return (
        df_filtered.to_dict("records"),                       # CDR table
        intel_updated["timeline"] if intel_updated["timeline"] else {},  # Timeline graph
        intel_updated["geo_map"] if intel_updated["geo_map"] else {},    # Geo map
        intel_updated["network_graph"] if intel_updated["network_graph"] else {},  # Network graph
        [html.Li(text) for text in ai_report],               # AI report
        f"Risk Score: {investigation['risk_score']}/100",    # Risk score
        [html.Li(text) for text in investigation["findings"]],  # Investigation findings
        active_case_info,                                     # Active case info
        f"Risk Score: {investigation['risk_score']}/100",    # Case risk score
        [html.Li(text) for text in investigation["findings"]]  # Case findings
    )

# -------------------------------
# GENERATE INVESTIGATION REPORT
# -------------------------------
@app.callback(
    Output("download-report", "data"),
    Input("download-btn", "n_clicks"),
    prevent_initial_call=True
)
def generate_report(n_clicks):
    intel_local = analyze_cdr(cdr_df)
    inv = run_investigation(cdr_df, intel_local)

    report_text = []
    report_text.append("CDR INTELLIGENCE EVIDENCE REPORT\n")
    report_text.append("=" * 40)
    report_text.append(f"Total Records: {len(cdr_df)}")
    report_text.append(f"Risk Score: {inv['risk_score']}/100\n")
    report_text.append("FINDINGS:")
    for f in inv["findings"]:
        report_text.append(f"- {f}")

    buffer = io.StringIO("\n".join(report_text))
    return dcc.send_string(buffer.getvalue(), "cdr_investigation_report.txt")

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
    # =====================================================
# RUN SERVER
# =====================================================
if __name__ == "__main__":
    server.run(host="127.0.0.1", port=5000, debug=True)
