"""Authentication helpers for password hashing and secure token management."""
import hashlib
import hmac
import os
import time
from typing import Optional

from src.utils.config import settings
from src.utils.crypto import decrypt_value, encrypt_value


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random salt."""
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}:{key.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a PBKDF2 hash."""
    try:
        salt, key_hex = hashed_password.split(":")
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100000,
        )
        return hmac.compare_digest(key.hex(), key_hex)
    except Exception:
        return False


def create_access_token(username: str, expires_in: int = 86400) -> str:
    """Generate an encrypted, tamper-proof access token containing username and expiry."""
    payload = f"{username}:{int(time.time() + expires_in)}"
    return encrypt_value(payload, settings.master_key)


def verify_access_token(token: str) -> Optional[str]:
    """Decrypt and validate an access token, returning the username if valid and unexpired."""
    try:
        payload = decrypt_value(token, settings.master_key)
        username, expires_at_str = payload.split(":")
        if time.time() > int(expires_at_str):
            return None
        return username
    except Exception:
        return None
