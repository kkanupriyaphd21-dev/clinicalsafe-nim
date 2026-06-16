"""Encrypted API key vault with rotation support."""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.database import APIKey
from src.models.schemas import APIKeyCreate, APIKeyPublic, APIKeyUpdate
from src.utils.config import settings
from src.utils.crypto import decrypt_value, encrypt_value


class KeyVaultError(Exception):
    pass


class KeyVault:
    def __init__(self, db: Session):
        self.db = db

    def _mask_key(self, key: str) -> str:
        if len(key) <= 8:
            return "*" * len(key)
        return key[:4] + "..." + key[-4:]

    def _to_public(self, record: APIKey) -> APIKeyPublic:
        decrypted = ""
        try:
            decrypted = decrypt_value(record.encrypted_key, settings.master_key)
        except Exception:
            decrypted = "[encrypted]"
        return APIKeyPublic(
            id=record.id,
            name=record.name,
            masked_key=self._mask_key(decrypted),
            is_active=record.is_active,
            is_default=record.is_default,
            usage_total_tokens=record.usage_total_tokens,
            usage_total_requests=record.usage_total_requests,
            last_used_at=record.last_used_at,
            created_at=record.created_at,
        )

    def list_keys(self, only_active: bool = False) -> List[APIKeyPublic]:
        query = self.db.query(APIKey)
        if only_active:
            query = query.filter(APIKey.is_active == True)
        records = query.order_by(APIKey.created_at.desc()).all()
        return [self._to_public(r) for r in records]

    def get_key(self, key_id: str) -> Optional[APIKeyPublic]:
        record = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if not record:
            return None
        return self._to_public(record)

    def get_decrypted_key(self, key_id: str) -> Optional[str]:
        record = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if not record:
            return None
        return decrypt_value(record.encrypted_key, settings.master_key)

    def get_active_keys(self) -> List[APIKey]:
        return (
            self.db.query(APIKey)
            .filter(APIKey.is_active == True)
            .order_by(APIKey.is_default.desc(), APIKey.created_at.asc())
            .all()
        )

    def get_default_key(self) -> Optional[APIKey]:
        return (
            self.db.query(APIKey)
            .filter(APIKey.is_active == True, APIKey.is_default == True)
            .first()
        )

    def add_key(self, data: APIKeyCreate) -> APIKeyPublic:
        encrypted = encrypt_value(data.key, settings.master_key)

        # If this is the first key or marked default, unset other defaults
        if data.is_default:
            self.db.query(APIKey).update({APIKey.is_default: False})

        record = APIKey(
            name=data.name,
            encrypted_key=encrypted,
            is_active=data.is_active,
            is_default=data.is_default,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._to_public(record)

    def update_key(self, key_id: str, data: APIKeyUpdate) -> Optional[APIKeyPublic]:
        record = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if not record:
            return None

        if data.name is not None:
            record.name = data.name
        if data.is_active is not None:
            record.is_active = data.is_active
        if data.is_default is not None:
            if data.is_default:
                self.db.query(APIKey).update({APIKey.is_default: False})
            record.is_default = data.is_default

        record.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(record)
        return self._to_public(record)

    def delete_key(self, key_id: str) -> bool:
        record = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def record_usage(
        self,
        key_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        record = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if not record:
            return
        record.usage_total_requests += 1
        record.usage_prompt_tokens += prompt_tokens
        record.usage_completion_tokens += completion_tokens
        record.usage_total_tokens += prompt_tokens + completion_tokens
        record.last_used_at = datetime.now(timezone.utc)
        self.db.commit()

    def deactivate_key(self, key_id: str) -> None:
        record = self.db.query(APIKey).filter(APIKey.id == key_id).first()
        if record:
            record.is_active = False
            record.updated_at = datetime.now(timezone.utc)
            self.db.commit()
