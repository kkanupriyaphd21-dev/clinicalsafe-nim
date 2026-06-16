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
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    from src.utils import config
    config.settings = config.Settings(master_key=master_key, nvidia_api_key=None)

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
    res_a = client.post("/keys", json={"name": "A", "key": "nvapi-a-12345"})
    assert res_a.status_code == 200
    res_b = client.post("/keys", json={"name": "B", "key": "nvapi-b-12345"})
    assert res_b.status_code == 200
    res = client.get("/keys")
    assert res.status_code == 200
    assert len(res.json()["keys"]) == 3


def test_keys_authorization(client, monkeypatch):
    from src.utils import config
    monkeypatch.setattr(config.settings, "admin_api_key", "super-secret-admin-token")
    
    # 1. Unauthenticated request should fail with 403
    res = client.get("/keys")
    assert res.status_code == 403
    
    # 2. Request with wrong key should fail with 403
    res = client.get("/keys", headers={"X-Admin-API-Key": "wrong-token"})
    assert res.status_code == 403
    
    # 3. Request with correct key should succeed
    res = client.get("/keys", headers={"X-Admin-API-Key": "super-secret-admin-token"})
    assert res.status_code == 200


def test_auth_endpoints(client):
    # 1. Try to login with wrong credentials
    res = client.post("/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert res.status_code == 401

    # 2. Login with correct seeded credentials (admin/admin)
    res = client.post("/auth/login", json={"username": "admin", "password": "admin"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["username"] == "admin"
    token = data["token"]

    # 3. Retrieve user profile without token -> 401
    res = client.get("/auth/me")
    assert res.status_code == 401

    # 4. Retrieve user profile with correct token -> 200
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    user_data = res.json()
    assert user_data["username"] == "admin"
