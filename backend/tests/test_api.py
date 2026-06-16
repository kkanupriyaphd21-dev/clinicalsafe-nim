"""Smoke tests for FastAPI endpoints."""
import os
import tempfile

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


@pytest.fixture
def master_key():
    return Fernet.generate_key().decode()


@pytest.fixture
def client(monkeypatch, master_key):
    monkeypatch.setenv("MASTER_KEY", master_key)
    from src.utils import config
    config.settings = config.Settings(master_key=master_key)

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    config.settings.database_url = f"sqlite:///{path}"

    from src.models.database import Base, engine
    Base.metadata.create_all(engine)

    from src.api.main import app
    with TestClient(app) as c:
        yield c

    os.unlink(path)


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["active_keys"] == 0


def test_add_key(client):
    res = client.post("/keys", json={
        "name": "Test Key",
        "key": "nvapi-test-key-12345",
        "is_default": True,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Test Key"
    assert "nvapi" not in data["masked_key"]

    health = client.get("/health").json()
    assert health["active_keys"] == 1
    assert health["total_keys"] == 1


def test_list_keys(client):
    client.post("/keys", json={"name": "A", "key": "nvapi-a"})
    client.post("/keys", json={"name": "B", "key": "nvapi-b"})
    res = client.get("/keys")
    assert res.status_code == 200
    assert len(res.json()["keys"]) == 2
