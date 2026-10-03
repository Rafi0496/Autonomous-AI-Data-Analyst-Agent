"""Security utilities for password hashing and JWT token management."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import jwt
from backend.app.core.config import settings

ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2 HMAC-SHA256 with a unique salt."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored salt$hash string."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 2:
            return False
        salt_hex, key_hex = parts
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
        return secrets.compare_digest(actual_key, expected_key)
    except Exception:
        return False

def create_access_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None
) -> str:
    """Create a signed JWT access token for a subject (user id or email)."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    if extra_claims:
        payload.update(extra_claims)
    
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except (jwt.PyJWTError, Exception):
        return None
