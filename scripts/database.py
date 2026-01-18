"""
Database setup and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from models import Base
from config_loader import get_database_path

# Get database path from config
db_path = get_database_path()
# SQLite database file (use absolute path)
DATABASE_URL = f"sqlite:///{db_path.absolute()}"

# Create engine
# Set echo=False for cleaner CLI output (set to True for debugging SQL queries)
# Use connect_args to ensure SQLite commits are immediate
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
