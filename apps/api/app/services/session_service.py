"""Session service containing session logic and User-Agent parsing."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.session import Session
from app.repositories.session_repository import SessionRepository


def parse_user_agent(user_agent: str | None) -> str:
    """Parse User-Agent to return a user-friendly browser and OS string."""
    if not user_agent:
        return "Unknown Device"

    ua = user_agent.lower()

    # OS detection
    os_name = "Unknown OS"
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "linux" in ua:
        os_name = "Linux"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"

    # Browser detection
    browser_name = "Unknown Browser"
    if "chrome" in ua or "crios" in ua:
        browser_name = "Chrome"
    elif "firefox" in ua or "fxios" in ua:
        browser_name = "Firefox"
    elif "safari" in ua and "chrome" not in ua and "chromium" not in ua:
        browser_name = "Safari"
    elif "edge" in ua or "edg" in ua:
        browser_name = "Edge"

    return f"{browser_name} on {os_name}"


class SessionService:
    """Orchestrates business logic for device sessions and refresh tokens."""

    def __init__(self, db: AsyncSession):
        self.repo = SessionRepository(db)

    def hash_token(self, token: str) -> str:
        """Hash a token using SHA256."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_session(
        self,
        user_id: uuid.UUID,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        """Create a new session record in the database."""
        token_hash = self.hash_token(refresh_token)
        now = datetime.now(UTC).replace(tzinfo=None)
        expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        device_name = parse_user_agent(user_agent)

        session = Session(
            user_id=user_id,
            token_hash=token_hash,
            device_name=device_name,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            created_at=now,
            last_used_at=now,
        )
        await self.repo.create(session)
        return session

    async def get_active_sessions(self, user_id: uuid.UUID) -> list[Session]:
        """Fetch all currently active sessions for a user."""
        now = datetime.now(UTC).replace(tzinfo=None)
        return await self.repo.get_active_by_user_id(user_id, now)

    async def revoke_session(self, session_id: uuid.UUID) -> None:
        """Revoke a specific session by ID."""
        session = await self.repo.get_by_id(session_id)
        if session:
            await self.repo.delete(session)

    async def logout(self, refresh_token: str) -> None:
        """Delete the session associated with the refresh token."""
        token_hash = self.hash_token(refresh_token)
        await self.repo.delete_by_token_hash(token_hash)

    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Delete all sessions belonging to the user."""
        await self.repo.delete_all_by_user_id(user_id)

    async def cleanup_expired_sessions(self) -> int:
        """Delete expired sessions. Suitable for background cron jobs."""
        now = datetime.now(UTC).replace(tzinfo=None)
        return await self.repo.delete_expired_sessions(now)
