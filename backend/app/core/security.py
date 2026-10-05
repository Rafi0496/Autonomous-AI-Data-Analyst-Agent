"""Security utilities for password hashing and JWT token management."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import jwt
from backend.app.core.config import settings

ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    """Hash a plaintext password using PBKDF2 HMAC-SHA256 with per-user salt and >= 600,000 iterations."""
    salt = os.urandom(16)
    iterations = getattr(settings, "PBKDF2_ITERATIONS", 600_000)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{salt.hex()}${iterations}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored hash using hmac.compare_digest."""
    try:
        parts = hashed_password.split("$")
        if len(parts) == 3:
            salt_hex, iter_str, key_hex = parts
            iterations = int(iter_str)
        elif len(parts) == 2:
            salt_hex, key_hex = parts
            iterations = 100_000  # legacy hash support
        else:
            return False
            
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        actual_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_key, expected_key)
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

