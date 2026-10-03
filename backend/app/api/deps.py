"""Authentication dependencies and request context for FastAPI endpoints."""
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import decode_access_token
from backend.app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

def get_optional_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Retrieve currently authenticated user if token is provided; otherwise None for demo/public use."""
    if not auth or not auth.credentials:
        return None
    token = auth.credentials
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Retrieve current authenticated user or raise 401 Unauthorized."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"}
        )
    token = auth.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"}
        )
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user
