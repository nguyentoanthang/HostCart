"""
Security primitives for HostCart: bcrypt password hashing and PyJWT token management.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from src.core.config import get_settings


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt with configured salt rounds."""
    settings = get_settings()
    rounds = settings.security.bcrypt_rounds
    salt = bcrypt.gensalt(rounds=rounds)
    hashed_bytes = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed_bytes.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt-hashed string."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    secret_key: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> str:
    """Generate a signed JWT access token containing arbitrary payload data and expiration."""
    settings = get_settings()
    key = secret_key or settings.security.secret_key
    alg = algorithm or settings.security.algorithm

    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now_utc + expires_delta
    else:
        expire = now_utc + timedelta(
            minutes=settings.security.access_token_expire_minutes
        )

    to_encode.update({"exp": expire, "iat": now_utc})
    encoded_jwt = jwt.encode(to_encode, key, algorithm=alg)
    return encoded_jwt


def decode_access_token(
    token: str,
    secret_key: Optional[str] = None,
    algorithm: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Decode and validate a signed JWT token. Returns payload dict or None if invalid or expired."""
    if not token:
        return None

    settings = get_settings()
    key = secret_key or settings.security.secret_key
    alg = algorithm or settings.security.algorithm

    try:
        payload = jwt.decode(token, key, algorithms=[alg])
        return payload
    except jwt.PyJWTError:
        return None
    except Exception:
        return None
