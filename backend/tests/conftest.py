"""Pytest configuration: set env vars before any module imports."""
import os
import tempfile
from cryptography.fernet import Fernet

# Generate a master key for tests before any app module is imported.
os.environ.setdefault("MASTER_KEY", Fernet.generate_key().decode())

_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")

# Ensure data directory exists for default SQLite path fallback.
os.makedirs("data", exist_ok=True)
