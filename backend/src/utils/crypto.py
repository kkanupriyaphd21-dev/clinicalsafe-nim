"""Encryption helpers for the API key vault."""
from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    pass


def get_fernet(master_key: str | None) -> Fernet:
    if not master_key:
        raise EncryptionError("MASTER_KEY is required to encrypt/decrypt API keys")
    # Fernet keys must be 32 url-safe base64-encoded bytes
    try:
        return Fernet(master_key.encode())
    except Exception as exc:
        raise EncryptionError(f"Invalid MASTER_KEY format: {exc}") from exc


def encrypt_value(value: str, master_key: str | None) -> str:
    f = get_fernet(master_key)
    return f.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value: str, master_key: str | None) -> str:
    f = get_fernet(master_key)
    try:
        return f.decrypt(encrypted_value.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionError("Could not decrypt API key (invalid MASTER_KEY?)") from exc
