from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database import Base, engine

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    role = Column(String)
    email = Column(String)
    phone = Column(String)

class OTP(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    code = Column(String)
    expires_at = Column(DateTime)

Base.metadata.create_all(bind=engine)
print("✅ Tables created")
