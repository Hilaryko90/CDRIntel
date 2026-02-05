from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base
from datetime import datetime, timedelta

class OTP(Base):
    __tablename__ = "otp"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    code = Column(String)
    expires_at = Column(DateTime)
