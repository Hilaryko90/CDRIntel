from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import OTP
import random


def generate_otp(user_id: int, expires_in_minutes: int = 5) -> str:
    """
    Generate a 6-digit OTP, store it in the database, and return it.
    """
    otp_code = str(random.randint(100000, 999999))
    expiry_time = datetime.utcnow() + timedelta(minutes=expires_in_minutes)

    db: Session = SessionLocal()
    try:
        otp_entry = OTP(
            user_id=user_id,
            otp_code=otp_code,
            expires_at=expiry_time,
            is_used=False
        )
        db.add(otp_entry)
        db.commit()
        db.refresh(otp_entry)
    finally:
        db.close()

    return otp_code
