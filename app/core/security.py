"""Security helpers for encryption and token utilities."""

from __future__ import annotations

import secrets
from typing import Optional

from cryptography.fernet import Fernet
from passlib.context import CryptContext


def generate_key() -> str:
    return Fernet.generate_key().decode()


class EnvelopeEncryptor:
    """Lightweight helper around Fernet encryption."""

    def __init__(self, key: Optional[str] = None) -> None:
        self._key = (key or generate_key()).encode()
        self._fernet = Fernet(self._key)

    @property
    def key(self) -> str:
        return self._key.decode()

    def encrypt(self, data: bytes) -> str:
        return self._fernet.encrypt(data).decode()

    def decrypt(self, token: str) -> bytes:
        return self._fernet.decrypt(token.encode())


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Create a bcrypt hash for the provided password."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify the provided password against the stored hash."""
    try:
        return _pwd_context.verify(password, hashed_password)
    except Exception:
        return False

