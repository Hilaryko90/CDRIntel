import random
from datetime import datetime, timedelta

otp_store = {}

def generate_otp(user_id):
    otp = str(random.randint(100000, 999999))
    otp_store[user_id] = {
        "otp": otp,
        "expires": datetime.utcnow() + timedelta(minutes=5)
    }
    return otp

def verify_otp(user_id, otp):
    record = otp_store.get(user_id)
    if not record:
        return False
    if record["expires"] < datetime.utcnow():
        return False
    return record["otp"] == otp