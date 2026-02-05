from dash import html

def admin_view():
    return html.Div([
        html.H2("Admin Dashboard"),
        html.P("User management, audits, system control")
    ])

def investigator_view():
    return html.Div([
        html.H2("Investigator Dashboard"),
        html.P("CDR analysis, case intelligence")
    ])
