"""
Local token authentication for Command Center.

Simple bearer-token auth suitable for local development.
Token is set via CC_AUTH_TOKEN env var or auto-generated on first run.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

logger = logging.getLogger("cc.auth")

_security = HTTPBearer(auto_error=False)

TOKEN_FILE = settings.nemoclaw_home / "cc-token"


def _resolve_token() -> str:
    """Resolve the active auth token. Priority: env var > file > generate."""
    # 1. Environment variable
    if settings.auth_token:
        return settings.auth_token

    # 2. Token file
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text().strip()
        if token:
            return token

    # 3. Generate new token
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token)
    TOKEN_FILE.chmod(0o600)
    logger.info("Generated new auth token → %s", TOKEN_FILE)
    return token


_active_token: str | None = None


def get_active_token() -> str:
    """Get or initialize the active token."""
    global _active_token
    if _active_token is None:
        _active_token = _resolve_token()
    return _active_token


def _verify(token: str) -> bool:
    """Constant-time token comparison."""
    expected = get_active_token()
    return secrets.compare_digest(token, expected)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> str:
    """FastAPI dependency: require valid bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not _verify(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


async def verify_ws_token(websocket: WebSocket) -> bool:
    """Verify token from WebSocket query param or first message."""
    # Check query parameter
    token = websocket.query_params.get("token")
    if token and _verify(token):
        return True

    # For local dev, allow unauthenticated connections
    # when no token has been explicitly set
    if not settings.auth_token and TOKEN_FILE.exists():
        return True

    return False
