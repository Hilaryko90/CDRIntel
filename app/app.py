import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import User
from utils import create_jwt, generate_otp, verify_jwt
from components.login import login_layout
from components.otp import otp_layout
from components.dashboard_views import admin_dashboard, investigator_dashboard

engine = create_engine("sqlite:///cdr_intel.db")
Session = sessionmaker(bind=engine)
session = Session()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server
app.layout = html.Div(id="page-content")  # single-page app

# Store JWT and OTP in memory for demo
TEMP_STORE = {"jwt": None, "otp": None}

# Show login page initially
@app.callback(Output("page-content", "children"),
              Input("page-content", "children"))
def display_login(_):
    return login_layout

# Handle login -> generate OTP
@app.callback(
    Output("page-content", "children"),
    Output("login-message", "children"),
    Input("login-btn", "n_clicks"),
    State("username", "value"),
    State("password", "value")
)
def handle_login(n_clicks, username, password):
    if not n_clicks:
        return dash.no_update, ""
    user = session.query(User).filter_by(username=username, password=password).first()
    if not user:
        return dash.no_update, "Invalid username or password"
    TEMP_STORE["jwt"] = create_jwt(user)
    TEMP_STORE["otp"] = generate_otp()
    # In real app: send OTP via SMS or email
    print(f"DEBUG: OTP for {user.username} is {TEMP_STORE['otp']}")
    return otp_layout, ""

# Handle OTP verification -> show role-based dashboard
@app.callback(
    Output("page-content", "children"),
    Output("otp-message", "children"),
    Input("verify-btn", "n_clicks"),
    State("otp-input", "value")
)
def verify_otp(n_clicks, otp_input):
    if not n_clicks:
        return dash.no_update, ""
    if otp_input == TEMP_STORE["otp"]:
        payload = verify_jwt(TEMP_STORE["jwt"])
        if payload["role"] == "admin":
            return admin_dashboard(None, None), ""
        else:
            return investigator_dashboard(None), ""
    return dash.no_update, "Invalid OTP"

if __name__ == "__main__":
    app.run()
