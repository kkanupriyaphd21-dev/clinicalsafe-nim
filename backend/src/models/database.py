"""SQLAlchemy models for the NIM API key vault and usage tracking."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Boolean, Text, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from src.utils.config import settings

Base = declarative_base()


def _sqlite_pragma(dbapi_conn, _):
    """Enable foreign keys and WAL for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
event.listen(engine, "connect", _sqlite_pragma)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    encrypted_key = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    usage_total_tokens = Column(Integer, default=0, nullable=False)
    usage_total_requests = Column(Integer, default=0, nullable=False)
    usage_prompt_tokens = Column(Integer, default=0, nullable=False)
    usage_completion_tokens = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    cooldown_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String(36), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    model = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False)  # success, error, rate_limited
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CSRTask(Base):
    __tablename__ = "csr_tasks"

    id = Column(String(36), primary_key=True)
    status = Column(String(50), nullable=False)  # processing, complete, error
    stage = Column(String(50), nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    current = Column(Integer, default=0, nullable=False)
    total = Column(Integer, default=0, nullable=False)
    message = Column(Text, nullable=True)
    result_data = Column(Text, nullable=True)  # JSON-encoded result dict
    error_message = Column(Text, nullable=True)
    elapsed_seconds = Column(Float, default=0.0, nullable=False)
    eta_seconds = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
