from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Simple user store (replace with DB later)
users = {
    "hilary": {
        "password": pwd_context.hash("Password123"),
        "theme": "dark",        # bootstrap theme
        "primary_color": "#e74c3c"
    },
    "analyst": {
        "password": pwd_context.hash("Analyst123"),
        "theme": "flatly",
        "primary_color": "#2ecc71"
    }
}

def verify_user(username, password):
    user = users.get(username)
    if not user:
        return None
    if not pwd_context.verify(password, user["password"]):
        return None
    return user
