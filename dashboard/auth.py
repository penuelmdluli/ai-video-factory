"""
Simple password-based authentication for the dashboard.
Uses JWT tokens for session management.
"""
import os
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

# Password from env, fallback to "admin" for dev
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "admin")
# Use a stable fallback so tokens survive server restarts during development
JWT_SECRET = os.getenv("JWT_SECRET", "ai-video-factory-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)


def create_token() -> str:
    """Create a JWT token."""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode({"exp": expire, "sub": "dashboard"}, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> bool:
    """Verify a JWT token."""
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except JWTError:
        return False


async def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """FastAPI dependency that requires valid auth."""
    if not credentials or not verify_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True
