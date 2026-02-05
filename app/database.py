# database.py

from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session

# Database URL — replace with your actual DB credentials
SQLALCHEMY_DATABASE_URL = "sqlite:///./cdr_intel.db"
# For PostgreSQL example:
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@localhost/dbname"

# Create the SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}  # needed for SQLite
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()

# Dependency for FastAPI to get a DB session
def get_db() -> Generator[Session, None, None]:
    """
    Yields a SQLAlchemy Session, ensuring it closes after use.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
