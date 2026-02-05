import dash
from dash import html, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import create_engine

# Connect to your database
engine = create_engine("sqlite:///cdr_intel.db")  # Replace with your actual DB path

# Load normalized CDR and audit data
cdr_df = pd.read_sql("SELECT * FROM cdr_normalized", engine)
audit_df = pd.read_sql("SELECT * FROM audit_log", engine)

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "CDR Intel Dashboard"

# KPI Cards
total_cdrs = len(cdr_df)
unique_cases = cdr_df['case_id'].nunique()
top_calling = cdr_df['calling'].value_counts().idxmax() if not cdr_df.empty else "N/A"
top_called = cdr_df['called'].value_counts().idxmax() if not cdr_df.empty else "N/A"

kpi_cards = dbc.Row([
    dbc.Col(dbc.Card([dbc.CardHeader("Total CDRs"), dbc.CardBody(html.H4(f"{total_cdrs}"))])),
    dbc.Col(dbc.Card([dbc.CardHeader("Unique Cases"), dbc.CardBody(html.H4(f"{unique_cases}"))])),
    dbc.Col(dbc.Card([dbc.CardHeader("Top Calling Number"), dbc.CardBody(html.H4(f"{top_calling}"))])),
    dbc.Col(dbc.Card([dbc.CardHeader("Top Called Number"), dbc.CardBody(html.H4(f"{top_called}"))])),
], className="mb-4")

# Normalized CDR Table
cdr_table = dash_table.DataTable(
    id='cdr-table',
    columns=[{"name": i, "id": i} for i in cdr_df.columns],
    data=cdr_df.to_dict('records'),
    page_size=10,
    filter_action="native",
    sort_action="native",
    style_table={'overflowX': 'auto'},
)

# Audit Log Table
audit_table = dash_table.DataTable(
    id='audit-table',
    columns=[{"name": i, "id": i} for i in audit_df.columns],
    data=audit_df.to_dict('records'),
    page_size=10,
    filter_action="native",
    sort_action="native",
    style_table={'overflowX': 'auto'},
)

# Layout
app.layout = dbc.Container([
    html.H1("CDR Intel Dashboard", className="text-center my-4"),
    kpi_cards,
    html.H3("Normalized CDR Records"),
    cdr_table,
    html.H3("Audit Logs", className="mt-5"),
    audit_table
], fluid=True)

if __name__ == "__main__":
    app.run(debug=True)

