from sqlalchemy import Column, Integer, String, Boolean
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password_hash = Column(String)
    role = Column(String)  # admin | investigator
    email = Column(String)
    phone = Column(String)
    is_verified = Column(Boolean, default=False)
