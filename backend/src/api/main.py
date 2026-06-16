"""
ClinicalSafe NIM Backend
Standalone NVIDIA NIM API system with encrypted key vault and usage tracking.
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.api.routers import csr, keys, summarize, auth
from src.models.database import init_db
from src.services.key_vault import KeyVault
from src.utils.config import settings
from src.utils.crypto import EncryptionError

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_default_key()
    _seed_default_user()
    yield


def _seed_default_user():
    """Seed a default admin user if no users exist in database."""
    try:
        from src.models.database import SessionLocal, User
        from src.utils.auth import hash_password

        db = SessionLocal()
        existing = db.query(User).first()
        if not existing:
            admin_user = User(
                username="admin",
                hashed_password=hash_password("admin"),
            )
            db.add(admin_user)
            db.commit()
            logger.info("Seeded default admin user (username: admin, password: admin)")
        db.close()
    except Exception as e:
        logger.warning(f"Failed to seed default user: {e}")


def _seed_default_key():
    """If a NVIDIA_API_KEY env var exists and vault is empty, seed it."""
    default_key = settings.nvidia_api_key or os.environ.get("NVIDIA_API_KEY")
    if not default_key:
        return
    try:
        from src.models.database import SessionLocal

        db = SessionLocal()
        vault = KeyVault(db)
        existing = vault.list_keys()
        if not existing:
            from src.models.schemas import APIKeyCreate
            vault.add_key(
                APIKeyCreate(
                    name="Default ENV Key",
                    key=default_key,
                    is_active=True,
                    is_default=True,
                )
            )
            logger.info("Seeded default NVIDIA API key from environment.")
        db.close()
    except EncryptionError as e:
        logger.warning(f"Could not seed default key: {e}")
    except Exception as e:
        logger.warning(f"Failed to seed default key: {e}")


app = FastAPI(
    title="ClinicalSafe NIM API",
    description="NVIDIA NIM API key vault and clinical summarization backend.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(keys.router)
app.include_router(summarize.router)
app.include_router(csr.router)


@app.get("/health")
async def health_check():
    from src.models.database import SessionLocal

    db = SessionLocal()
    try:
        vault = KeyVault(db)
        total = len(vault.list_keys())
        active = len(vault.list_keys(only_active=True))
        return {
            "status": "healthy",
            "version": "1.0.0",
            "total_keys": total,
            "active_keys": active,
            "default_model": settings.nim_default_model,
        }
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)
