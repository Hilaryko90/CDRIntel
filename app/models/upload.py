from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base
from datetime import datetime

class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    sha256 = Column(String, nullable=False, unique=True)
    uploader = Column(String, nullable=False)
    case_id = Column(String, nullable=False)
    purpose = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
