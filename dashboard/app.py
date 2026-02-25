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

# Global investigation state
ACTIVE_CASE = {
    "id": None,
    "description": "",
    "targets": []
}

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
def normalize_columns(df):
    # standardize column names
    df.columns = [c.lower().strip() for c in df.columns]

    column_map = {
        "a_number": "caller",
        "b_number": "receiver",
        "calling_number": "caller",
        "called_number": "receiver",
        "calling": "caller",
        "called": "receiver",
        "source": "caller",
        "destination": "receiver",
        "from": "caller",
        "to": "receiver",
        "caller_id": "caller",
        "receiver_id": "receiver",
        "time": "timestamp",
        "date": "timestamp",
        "call_time": "timestamp",
        "start_time": "timestamp",
        "duration_sec": "duration",
        "call_duration": "duration"
    }

    df.rename(columns=column_map, inplace=True)

    # 🚨 CRITICAL FIX → remove duplicate columns AFTER rename
    df = df.loc[:, ~df.columns.duplicated()]

    # Fill missing columns
    if "caller" not in df.columns:
        df["caller"] = "UNKNOWN"

    if "receiver" not in df.columns:
        df["receiver"] = "UNKNOWN"

    if "duration" not in df.columns:
        df["duration"] = 0

    if "timestamp" not in df.columns:
        df["timestamp"] = pd.Timestamp.now()
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    return df

def analyze_cdr(df):
    """
    Analyze CDR dataset to extract summary statistics, anomalies, and visualizations.
    Returns a dictionary with all expected keys for the dashboard.
    """

    # ================= PERFORMANCE GUARD =================
    MAX_ROWS = 50000
    if len(df) > MAX_ROWS:
        df = df.sample(MAX_ROWS, random_state=42).copy()
    # =====================================================

    result = {
        "summary": {},
        "insights": [],
        "network_graph": {},
        "timeline": {},
        "geo_map": {},
        "anomalies": pd.DataFrame()
    }

    if df.empty:
        return result

    # ----------------------------
    # Summary stats
    # ----------------------------
    result["summary"]["total_calls"] = len(df)
    result["summary"]["total_duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0).sum()
    result["summary"]["avg_duration"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0).mean()

    # ----------------------------
    # Top callers insight
    # ----------------------------
    if "caller" in df.columns:
        top_callers = df["caller"].value_counts().head(5)
        for caller, count in top_callers.items():
            result["insights"].append(f"Top caller: {caller} with {count} calls")

    # ----------------------------
    # FAST Anomaly detection
    # ----------------------------
    if "duration" in df.columns:
        df["duration_norm"] = pd.to_numeric(df["duration"], errors="coerce").fillna(0)

        train_df = df.sample(10000, random_state=42) if len(df) > 10000 else df

        clf = IsolationForest(contamination=0.05, random_state=42)
        clf.fit(train_df[["duration_norm"]])

        df["anomaly_score"] = clf.predict(df[["duration_norm"]])
        anomalies = df[df["anomaly_score"] == -1]

        if anomalies.empty:
            threshold = df["duration_norm"].mean() + 3 * df["duration_norm"].std()
            anomalies = df[df["duration_norm"] > threshold]

        result["anomalies"] = anomalies

    # ----------------------------
    # FAST Network graph
    # ----------------------------
    if "caller" in df.columns and "receiver" in df.columns:
        top_df = (
            df.groupby(["caller", "receiver"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(200)
        )

        G = nx.from_pandas_edgelist(top_df, source="caller", target="receiver")
        pos = nx.spring_layout(G, k=0.5)

        edge_x, edge_y = [], []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", hoverinfo="none")

        node_x, node_y, node_text = [], [], []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(str(node))

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            hoverinfo="text"
        )

        network_fig = go.Figure(data=[edge_trace, node_trace])
        network_fig.update_layout(title="Call Network Graph", showlegend=False)
        result["network_graph"] = network_fig

    # ----------------------------
    # Timeline
    # ----------------------------
    if "timestamp" in df.columns and not df["timestamp"].isnull().all():
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        timeline = df.groupby(pd.Grouper(key="timestamp", freq="h")).size().reset_index(name="calls")
        result["timeline"] = px.line(timeline, x="timestamp", y="calls", title="Call Timeline (Hourly)")

    # ----------------------------
    # Geo map (optional)
    # ----------------------------
    if "lat" in df.columns and "lon" in df.columns:
        result["geo_map"] = px.scatter_mapbox(
            df,
            lat="lat",
            lon="lon",
            hover_name="caller",
            size="duration_norm",
            zoom=5,
            mapbox_style="open-street-map",
            title="Call Geo Map"
        )

    return result
# =====================================================
# AI INTELLIGENCE SUMMARY (Aligned with Master Risk Model)
# =====================================================
def generate_intelligence_report(df, intel):
    """
    Generates AI intelligence insights aligned with investigation engine.
    Returns list of strings for Dash rendering.
    """

    if df.empty:
        return ["No CDR data available"]

    insights = []

    total_calls = len(df)
    unique_callers = df["caller"].nunique() if "caller" in df.columns else 0
    unique_receivers = df["receiver"].nunique() if "receiver" in df.columns else 0

    insights.append(f"Total calls analyzed: {total_calls}")
    insights.append(f"Unique callers: {unique_callers}")
    insights.append(f"Unique receivers: {unique_receivers}")

    # ----------------------------
    # High-frequency caller detection
    # ----------------------------
    if "caller" in df.columns:
        freq = df["caller"].value_counts()
        threshold = freq.mean() + 3 * freq.std()
        suspicious = freq[freq > threshold]

        for number, count in suspicious.items():
            insights.append(f"⚠️ High activity detected from {number} ({count} calls)")

    # ----------------------------
    # Long duration calls
    # ----------------------------
    long_calls = 0
    if "duration" in df.columns:
        dur = pd.to_numeric(df["duration"], errors="coerce").fillna(0)
        long_calls = (dur > dur.mean() + 2 * dur.std()).sum()
        if long_calls > 0:
            insights.append(f"⚠️ {long_calls} unusually long calls detected")

    # ----------------------------
    # Night activity pattern
    # ----------------------------
    if "timestamp" in df.columns:
        night_calls = df[df["timestamp"].dt.hour.between(0, 5)]
        if len(night_calls) > total_calls * 0.3:
            insights.append("⚠️ Heavy night-time call activity detected")

    # ----------------------------
    # MASTER RISK SCORE (Unified)
    # ----------------------------
    risk_score = compute_master_risk(df, intel)
    insights.append(f"Fraud Risk Score: {risk_score}/100")

    if risk_score >= 70:
        insights.append("🚨 HIGH RISK communication pattern detected")
    elif risk_score >= 40:
        insights.append("⚠️ MODERATE RISK pattern detected")
    else:
        insights.append("✅ Low risk pattern")

    return insights

# =====================================================
# MASTER RISK MODEL (Unified scoring engine)
# =====================================================
def compute_master_risk(df, intel):
    anomaly_count = len(intel.get("anomalies", []))

    WATCHLIST = {"99999", "12345", "55555"}
    watchlist_hits = df[df["caller"].isin(WATCHLIST) | df["receiver"].isin(WATCHLIST)]

    long_calls = 0
    if "duration" in df.columns:
        dur = pd.to_numeric(df["duration"], errors="coerce").fillna(0)
        long_calls = (dur > dur.mean() + 2 * dur.std()).sum()

    fraud_flags = 0
    if "fraud_type" in df.columns:
        fraud_flags = df["fraud_type"].notna().sum()

    # unified weighted model
    risk_score = (
        anomaly_count * 0.02 +
        len(watchlist_hits) * 5 +
        long_calls * 0.001 +
        fraud_flags * 2
    )

    return min(100, round(risk_score))
# =====================================================
# INVESTIGATION ENGINE (Unified Risk Model)
# =====================================================
def run_investigation(df, intel):

    findings = []

    WATCHLIST = {"99999", "12345", "55555"}
    watchlist_hits = df[df["caller"].isin(WATCHLIST) | df["receiver"].isin(WATCHLIST)]

    anomaly_count = len(intel.get("anomalies", []))

    risk_score = compute_master_risk(df, intel)

    findings.append(f"Dataset size: {len(df)} records")
    findings.append(f"Anomalies detected: {anomaly_count}")
    findings.append(f"Watchlist hits: {len(watchlist_hits)}")

    if risk_score >= 70:
        findings.append("🚨 HIGH RISK communication network detected.")
    elif risk_score >= 40:
        findings.append("⚠️ MODERATE RISK pattern detected.")
    else:
        findings.append("✅ Low risk pattern.")

    return {
        "findings": findings,
        "risk_score": risk_score
    }
# =====================================================
# LOAD INITIAL DATA
# =====================================================
import glob
import os

def ingest_cdr_files(folder="cdr_files"):
    """
    Reads all CSV and Excel files from the given folder,
    normalizes columns, and returns a single DataFrame.
    """
    os.makedirs(folder, exist_ok=True)  # ensure folder exists
    all_files = glob.glob(f"{folder}/*.csv") + glob.glob(f"{folder}/*.xlsx") + glob.glob(f"{folder}/*.xls")
    df_list = []

    for file in all_files:
        try:
            if file.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            df = normalize_columns(df)  # make sure normalize_columns is defined
            df_list.append(df)
        except Exception as e:
            print(f"Error loading {file}: {e}")

    if df_list:
        return pd.concat(df_list, ignore_index=True)
    else:
        # Return empty DataFrame with default columns
        return pd.DataFrame(columns=[
            "caller", "receiver", "duration", "timestamp",
            "cellid", "provincename", "cell2province", "province2cell",
            "caller_id", "receiver_id", "start_time", "call_type",
            "sim_id", "device_id", "location_origin", "country_origin",
            "location_dest", "country_dest", "is_night_call",
            "transaction_status", "fraud_type"
        ])

# Load the CDR data
cdr_df = ingest_cdr_files()
print("CDR rows loaded:", len(cdr_df))
print("Columns:", list(cdr_df.columns))

# Run analytics on initial data
print("Startup complete — analytics will run on demand")
intel = {
    "summary": {},
    "insights": [],
    "network_graph": {},
    "timeline": {},
    "geo_map": {},
    "anomalies": pd.DataFrame()
}

# =====================================================
# DASH APP
# =====================================================
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname="/dashboard/",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True  # allow callbacks for components added later
)

# ================= LAYOUT =================
app.layout = html.Div(
    dbc.Container([

        # ================= HEADER =================
        html.H1("📊 CDR Intel Dashboard", className="text-center my-4"),
        dbc.Button("Logout", href="/logout", color="danger"),
        html.Hr(),

        # ================= INTELLIGENCE SUMMARY =================
        html.H3("📊 Intelligence Summary"),
        html.Ul([html.Li(f"{k}: {v}") for k, v in intel.get("summary", {}).items()]),
        html.Hr(),

        # ================= AI INTELLIGENCE =================
        html.H3("🧠 AI Intelligence Assessment"),
        html.Div(id="active-case-info"),
        html.Div(id="case-risk-score"),
        html.Ul(id="case-findings"),

        html.Div([
            html.H5("Overall Risk Score:", style={"color": "red"}),
            html.H4(id="risk-score", children="N/A"),
            html.H5("Investigation Findings:"),
            html.Ul(id="investigation-findings"),
            html.H5("AI Insights:"),
            html.Ul(id="ai-report"),
        ], style={"marginBottom": "30px"}),
        html.Hr(),

        # ================= ANALYST CASE WORKSPACE =================
        html.H3("📂 Analyst Case Workspace"),
        dbc.Row([
            dbc.Col(dcc.Input(id="case-id-input", placeholder="Case ID", type="text"), width=3),
            dbc.Col(dcc.Input(id="case-desc-input", placeholder="Case Description", type="text"), width=4),
            dbc.Col(dcc.Input(id="case-targets-input", placeholder="Targets (comma-separated)", type="text"), width=3),
            dbc.Col(dbc.Button("Create / Update Case", id="create-case-btn", n_clicks=0, color="primary"), width=2)
        ], className="mb-3"),

        dash_table.DataTable(
            id="case-table",
            columns=[
                {"name": "Case ID", "id": "Case ID"},
                {"name": "Case Description", "id": "Case Description"},
                {"name": "Targets", "id": "Targets"},
            ],
            data=[],
            page_size=5,
            style_table={"overflowX": "auto"}
        ),
        html.Hr(),

        # ================= CDR RECORDS =================
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
            data=cdr_df.to_dict("records") if not cdr_df.empty else [],
            columns=[{"name": i, "id": i} for i in cdr_df.columns],
            page_size=10,
            filter_action="native",
            sort_action="native",
            style_table={"overflowX": "auto"},
        ),
        html.Hr(),

        # ================= VISUALS =================
        html.H3("⏱ Call Timeline"),
        dcc.Graph(id="timeline-graph", figure=intel.get("timeline", {})),
        html.H3("🗺 Call Geo Map"),
        dcc.Graph(id="geo-map", figure=intel.get("geo_map", {})),
        html.H3("📡 Call Network Graph"),
        dcc.Graph(id="network-graph", figure=intel.get("network_graph", {})),
        html.Hr(),

        # ================= FILE ACTIONS =================
        dbc.Row([
            dbc.Col(dcc.Upload(
                id="upload-cdr",
                children=html.Div(["📤 Drag and Drop or ", html.A("Select CDR File")]),
                style={
                    "width": "100%", "height": "60px", "lineHeight": "60px",
                    "borderWidth": "1px", "borderStyle": "dashed",
                    "borderRadius": "5px", "textAlign": "center"
                },
                multiple=True
            ), width=6),
            dbc.Col(dbc.Button("📥 Download Evidence Report", id="download-btn", color="success"), width=6)
        ]),
        dcc.Download(id="download-report"),

    ], fluid=True),
    style={"overflowX": "auto"}
)

# =====================================================
# MANAGE CASES CALLBACK 
# =====================================================
@app.callback(
    Output("case-table", "data"),
    Output("case-id-input", "value"),
    Output("case-desc-input", "value"),
    Output("case-targets-input", "value"),
    Input("create-case-btn", "n_clicks"),
    State("case-id-input", "value"),
    State("case-desc-input", "value"),
    State("case-targets-input", "value"),
    prevent_initial_call=True
)
def manage_cases(create_click, case_id, desc, targets):
    """
    Handles creation / update of cases safely.
    """
    global case_df, CASES, ACTIVE_CASE

    # Ensure globals exist
    if "CASES" not in globals():
        CASES = {}
    if "ACTIVE_CASE" not in globals():
        ACTIVE_CASE = {}

    try:
        # Only proceed if button clicked and mandatory fields provided
        if create_click and case_id and desc:
            # Normalize targets list
            targets_list = [t.strip() for t in (targets or "").split(",") if t.strip()]

            # Update CASES dictionary
            CASES[case_id] = {"description": desc.strip(), "targets": targets_list}

            # Set ACTIVE_CASE
            ACTIVE_CASE = {"id": case_id.strip(), "description": desc.strip(), "targets": targets_list}

            # Prepare row for DataTable
            new_case_row = {
                "Case ID": case_id.strip(),
                "Case Description": desc.strip(),
                "Targets": ", ".join(targets_list)
            }

            # Update existing row if exists, else append
            if case_id in case_df["Case ID"].values:
                case_df.loc[case_df["Case ID"] == case_id, ["Case Description", "Targets"]] = desc.strip(), ", ".join(targets_list)
            else:
                case_df = pd.concat([case_df, pd.DataFrame([new_case_row])], ignore_index=True)

            # Return updated table and clear inputs
            return case_df.to_dict("records"), "", "", ""

        # If no creation, return current state
        return case_df.to_dict("records"), case_id, desc, targets

    except Exception as e:
        # Catch unexpected errors to prevent callback failure
        print("Error in manage_cases callback:", e)
        return case_df.to_dict("records"), "", "", ""

# =====================================================
# UPDATE DASHBOARD CALLBACK (STABLE)
# =====================================================
# =====================================================
# DASHBOARD UPDATE CALLBACK (STABLE)
# =====================================================
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
)
def update_dashboard(caller, receiver, start_date, end_date):

    global cdr_df, ACTIVE_CASE

    if "ACTIVE_CASE" not in globals():
     ACTIVE_CASE = {
        "id": None,
        "description": "",
        "targets": []
    }

    try:
        # -------------------------------
        # 1️⃣ Base dataset
        # -------------------------------
        if cdr_df.empty:
            return [], {}, {}, {}, [html.Li("No CDR data loaded")], "N/A", [html.Li("No investigation possible")], "Active Case: None", "N/A", []

        df_filtered = cdr_df.copy()
        
        # -------------------------------
        # 2️⃣ Apply filters safely
        # -------------------------------
        if caller:
            df_filtered = df_filtered[df_filtered["caller"].astype(str).str.contains(caller, case=False, na=False)]

        if receiver:
            df_filtered = df_filtered[df_filtered["receiver"].astype(str).str.contains(receiver, case=False, na=False)]

        if start_date:
            df_filtered = df_filtered[df_filtered["timestamp"] >= pd.to_datetime(start_date)]

        if end_date:
            df_filtered = df_filtered[df_filtered["timestamp"] <= pd.to_datetime(end_date)]

        # -------------------------------
        # 3️⃣ Apply Active Case filter
        # -------------------------------
        active_case_info = "Active Case: None"
        if ACTIVE_CASE.get("id"):
            targets = ACTIVE_CASE.get("targets", [])
            if targets:
                df_filtered = df_filtered[
                    df_filtered["caller"].isin(targets) |
                    df_filtered["receiver"].isin(targets)
                ]
            active_case_info = f"Active Case: {ACTIVE_CASE['id']} — {ACTIVE_CASE.get('description','')}"

        # -------------------------------
        # 4️⃣ CRITICAL: Never analyze empty DF
        # -------------------------------
        df_to_analyze = df_filtered if not df_filtered.empty else cdr_df.copy()

        # -------------------------------
        # 5️⃣ Run analytics engine
        # -------------------------------
        intel = analyze_cdr(df_to_analyze)

        # -------------------------------
        # 6️⃣ AI Intelligence Summary
        # -------------------------------
        insights = generate_intelligence_report(df_to_analyze, intel)
        if not insights:
            insights = ["Dataset analyzed successfully", "No immediate threats detected"]
        ai_report_elements = [html.Li(x) for x in insights]

        # -------------------------------
        # 7️⃣ Investigation Engine
        # -------------------------------
        investigation = run_investigation(df_to_analyze, intel)

        findings = investigation.get("findings", [])
        investigation_findings_elements = [html.Li(x) for x in findings] if findings else [html.Li("No suspicious activity detected")]

        # -------------------------------
        # 8️⃣ Risk Score
        # -------------------------------
        risk_val = investigation.get("risk_score", 0)
        risk_score_str = f"{risk_val}/100" if risk_val is not None else "0/100"
        
        case_risk = risk_score_str if ACTIVE_CASE.get("id") else "N/A"
        case_findings_elements = investigation_findings_elements if ACTIVE_CASE.get("id") else []

        # -------------------------------
        # 9️⃣ Return UI outputs
        # -------------------------------
        return (
            df_filtered.to_dict("records"),
            intel.get("timeline", {}),
            intel.get("geo_map", {}),
            intel.get("network_graph", {}),
            ai_report_elements,
            risk_score_str,
            investigation_findings_elements,
            active_case_info,
            case_risk,
            case_findings_elements
        )

    except Exception as e:
        print("Dashboard error:", e)
        return (
            [],
            {},
            {},
            {},
            [html.Li("System error during analysis")],
            "N/A",
            [html.Li("Investigation failed")],
            "Active Case: None",
            "N/A",
            []
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
    print("Starting Dash server...")
    app.run(debug=True, host="127.0.0.1", port=8050)
    # =====================================================