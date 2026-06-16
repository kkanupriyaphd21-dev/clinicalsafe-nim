"""FastAPI dependencies."""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from src.models.database import get_db, User
from src.services.key_vault import KeyVault
from src.services.nim_client import NIMClient
from src.services.usage_tracker import UsageTracker
from src.utils import config
from src.utils.auth import verify_access_token

API_KEY_HEADER = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)
SECURITY_BEARER = HTTPBearer(auto_error=False)


def get_key_vault(db: Session = Depends(get_db)) -> KeyVault:
    return KeyVault(db)


def get_nim_client(db: Session = Depends(get_db)) -> NIMClient:
    return NIMClient(db)


def get_usage_tracker(db: Session = Depends(get_db)) -> UsageTracker:
    return UsageTracker(db)


def verify_admin_key(api_key: str | None = Security(API_KEY_HEADER)) -> None:
    """Validate X-Admin-API-Key header against config setting, if configured."""
    expected_key = config.settings.admin_api_key
    if not expected_key:
        return
    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-API-Key header",
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(SECURITY_BEARER),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate bearer token and return active User database object."""
    from typing import Optional
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = credentials.credentials
    username = verify_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
