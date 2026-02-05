from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.database import Base
from datetime import datetime

class CDR(Base):
    __tablename__ = "cdr"
    id = Column(Integer, primary_key=True, index=True)
    caller = Column(String, index=True)
    callee = Column(String, index=True)
    timestamp = Column(DateTime)
    duration = Column(Integer)  # seconds
    imei = Column(String)
    imsi = Column(String)
    call_type = Column(String)
    cell_tower = Column(String)
    subscriber_id = Column(String, index=True)

class AnalysisLog(Base):
    __tablename__ = "analysis_log"
    id = Column(Integer, primary_key=True, index=True)
    subscriber_id = Column(String)
    anomaly_type = Column(String)
    details = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
