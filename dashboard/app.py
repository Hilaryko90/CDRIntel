# dashboard/app.py

from flask import Flask, redirect, url_for, request
from flask_login import (
    LoginManager, UserMixin,
    login_user, logout_user,
    login_required, current_user
)

import dash
from dash import html, dcc, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import pandas as pd
from sqlalchemy import create_engine
import hashlib

# -------------------------------------------------
# FLASK APP (AUTH OWNER)
# -------------------------------------------------
server = Flask(__name__)
server.secret_key = "cdr-intel-secret-key"

login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = "/login"

# -------------------------------------------------
# USERS (STATIC FOR NOW)
# -------------------------------------------------
USERS = {
    "admin": {
        "password": hashlib.sha256("admin123".encode()).hexdigest(),
        "color": "#0d6efd",
    },
    "analyst": {
        "password": hashlib.sha256("analyst123".encode()).hexdigest(),
        "color": "#198754",
    },
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.color = USERS[username]["color"]

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None

# -------------------------------------------------
# LOGIN ROUTE
# -------------------------------------------------
@server.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in USERS:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            if USERS[username]["password"] == hashed:
                login_user(User(username))
                return redirect("/dashboard")

        return "Invalid credentials", 401

    return """
    <h2>CDR Intel Login</h2>
    <form method="post">
        <input name="username" placeholder="Username"><br><br>
        <input name="password" type="password" placeholder="Password"><br><br>
        <button type="submit">Login</button>
    </form>
    """

# -------------------------------------------------
# LOGOUT
# -------------------------------------------------
@server.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

# -------------------------------------------------
# DATABASE
# -------------------------------------------------
engine = create_engine("sqlite:///cdr_intel.db")

try:
    cdr_df = pd.read_sql("SELECT * FROM cdr_normalized", engine)
    audit_df = pd.read_sql("SELECT * FROM audit_log", engine)
except Exception:
    cdr_df = pd.DataFrame()
    audit_df = pd.DataFrame()

# -------------------------------------------------
# DASH APP (MOUNTED ON FLASK)
# -------------------------------------------------
app = dash.Dash(
    __name__,
    server=server,
    url_base_pathname="/dashboard/",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

app.layout = dbc.Container(
    [
        html.H1(
            "📊 CDR Intel Dashboard",
            id="title",
            className="text-center my-4",
        ),

        dbc.Button(
            "Logout",
            href="/logout",
            color="danger",
            className="mb-4"
        ),

        dash_table.DataTable(
            data=cdr_df.to_dict("records"),
            columns=[{"name": i, "id": i} for i in cdr_df.columns],
            page_size=10,
            filter_action="native",
            sort_action="native",
            style_table={"overflowX": "auto"},
        ),
    ],
    fluid=True,
)

# -------------------------------------------------
# DYNAMIC USER COLOR
# -------------------------------------------------
@app.callback(
    Output("title", "style"),
    Input("title", "id")
)
def apply_user_color(_):
    if current_user.is_authenticated:
        return {"color": current_user.color}
    return {"color": "black"}

# -------------------------------------------------
# PROTECT DASH
# -------------------------------------------------
@server.before_request
def protect_dashboard():
    if request.path.startswith("/dashboard"):
        if not current_user.is_authenticated:
            return redirect("/login")

# -------------------------------------------------
# RUN
# -------------------------------------------------
if __name__ == "__main__":
    server.run(debug=True)
