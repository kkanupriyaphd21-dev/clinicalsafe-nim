"""FastAPI dependencies."""
from fastapi import Depends
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.services.key_vault import KeyVault
from src.services.nim_client import NIMClient
from src.services.usage_tracker import UsageTracker


def get_key_vault(db: Session = Depends(get_db)) -> KeyVault:
    return KeyVault(db)


def get_nim_client(db: Session = Depends(get_db)) -> NIMClient:
    return NIMClient(db)


def get_usage_tracker(db: Session = Depends(get_db)) -> UsageTracker:
    return UsageTracker(db)
