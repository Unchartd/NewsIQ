"""FastAPI dependencies for authentication, authorization, and DB sessions."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.models import User

# Optional bearer scheme — doesn't force 401 on missing token
optional_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Extract and validate the current user from the access token.

    Returns None for unauthenticated (guest) users.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == uid, User.status == "active"))
    return result.scalar_one_or_none()


async def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    """Require an authenticated user. Raises 401 if not logged in."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_premium(
    user: User = Depends(require_user),
) -> User:
    """Require a premium or admin user. Raises 403 otherwise."""
    if user.role not in ("premium", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required.",
        )
    return user


async def require_admin(
    user: User = Depends(require_user),
) -> User:
    """Require an admin user. Raises 403 otherwise."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    return user


async def require_admin_sse(
    request: Request,
    token: str | None = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Admin authorization for EventSource endpoints.

    The browser's EventSource cannot set an Authorization header, so the admin
    UI appends the access token as a `token` query parameter. It did so against
    endpoints that declared no auth dependency at all: the token was written
    into access logs and never checked, so live pipeline logs and status —
    article URLs, story ids, tracebacks — were readable by anyone who could
    reach the API.

    The query parameter is a real access token and is validated exactly like a
    header one. Header and cookie are preferred when present, so non-browser
    callers need not put a credential in a URL.

    A token in a URL is still logged by proxies. Prefer issuing a short-lived,
    single-use stream ticket if these endpoints are ever exposed beyond the
    admin network.
    """
    raw = None
    if credentials:
        raw = credentials.credentials
    elif "access_token" in request.cookies:
        raw = request.cookies["access_token"]
    elif token:
        raw = token

    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(raw)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token."
        )

    user_id = payload.get("sub")
    try:
        uid = uuid.UUID(user_id) if user_id else None
    except ValueError:
        uid = None
    if uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.")

    user = (
        await db.execute(select(User).where(User.id == uid, User.status == "active"))
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in.")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    return user
