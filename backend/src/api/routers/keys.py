"""API key vault routes."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.schemas import APIKeyCreate, APIKeyList, APIKeyPublic, APIKeyUpdate
from src.services.key_vault import KeyVault

from src.api.dependencies import verify_admin_key

router = APIRouter(
    prefix="/keys",
    tags=["API Keys"],
    dependencies=[Depends(verify_admin_key)]
)


def _vault(db: Session = Depends(get_db)) -> KeyVault:
    return KeyVault(db)


@router.post("", response_model=APIKeyPublic)
async def create_key(data: APIKeyCreate, vault: KeyVault = Depends(_vault)):
    return vault.add_key(data)


@router.get("", response_model=APIKeyList)
async def list_keys(only_active: bool = False, vault: KeyVault = Depends(_vault)):
    return APIKeyList(keys=vault.list_keys(only_active=only_active))


@router.get("/{key_id}", response_model=APIKeyPublic)
async def get_key(key_id: str, vault: KeyVault = Depends(_vault)):
    key = vault.get_key(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key


@router.patch("/{key_id}", response_model=APIKeyPublic)
async def update_key(key_id: str, data: APIKeyUpdate, vault: KeyVault = Depends(_vault)):
    updated = vault.update_key(key_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="API key not found")
    return updated


@router.delete("/{key_id}")
async def delete_key(key_id: str, vault: KeyVault = Depends(_vault)):
    if not vault.delete_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "deleted", "id": key_id}


@router.get("/{key_id}/usage")
async def get_key_usage(
    key_id: str,
    days: Optional[int] = 30,
    vault: KeyVault = Depends(_vault),
):
    key = vault.get_key(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    from src.services.usage_tracker import UsageTracker
    from src.models.database import get_db
    from fastapi import Depends

    # Note: usage tracker dependency injected inline to keep router simple
    def _get_tracker(db: Session = Depends(get_db)):
        return UsageTracker(db)

    tracker = UsageTracker(vault.db)
    start = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    events = tracker.get_usage_for_key(key_id, start=start)
    aggregates = tracker.get_aggregates_for_key(key_id)
    return {
        "key_id": key_id,
        "days": days,
        "aggregates": aggregates,
        "events": events,
    }
