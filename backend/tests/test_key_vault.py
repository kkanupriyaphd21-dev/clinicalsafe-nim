"""Tests for the encrypted API key vault."""
import os
import tempfile

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, APIKey
from src.models.schemas import APIKeyCreate
from src.services.key_vault import KeyVault
from src.utils.crypto import encrypt_value, decrypt_value


@pytest.fixture
def master_key():
    return Fernet.generate_key().decode()


@pytest.fixture
def db_session(master_key, monkeypatch):
    monkeypatch.setenv("MASTER_KEY", master_key)
    # Re-import settings so it picks up the env var
    from src.utils import config
    config.settings = config.Settings(master_key=master_key)

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    os.unlink(path)


def test_encrypt_decrypt(master_key):
    original = "nvapi-test-secret-key"
    encrypted = encrypt_value(original, master_key)
    assert encrypted != original
    decrypted = decrypt_value(encrypted, master_key)
    assert decrypted == original


def test_key_vault_add_and_list(db_session, master_key):
    vault = KeyVault(db_session)
    key = vault.add_key(APIKeyCreate(name="Test Key", key="nvapi-1234567890", is_default=True))
    assert key.name == "Test Key"
    assert "nvapi" not in key.masked_key
    assert key.is_default is True

    keys = vault.list_keys()
    assert len(keys) == 1
    assert keys[0].name == "Test Key"


def test_key_vault_default_uniqueness(db_session, master_key):
    vault = KeyVault(db_session)
    vault.add_key(APIKeyCreate(name="First", key="nvapi-first-key-123", is_default=True))
    second = vault.add_key(APIKeyCreate(name="Second", key="nvapi-second-key-456", is_default=True))
    assert second.is_default is True

    rows = db_session.query(APIKey).all()
    assert sum(1 for r in rows if r.is_default) == 1


def test_key_vault_usage_tracking(db_session, master_key):
    vault = KeyVault(db_session)
    key = vault.add_key(APIKeyCreate(name="Usage", key="nvapi-usage-key-789"))
    vault.record_usage(key.id, prompt_tokens=10, completion_tokens=20)

    updated = vault.get_key(key.id)
    assert updated.usage_total_requests == 1
    assert updated.usage_total_tokens == 30
