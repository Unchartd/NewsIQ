"""Session repository for database access."""

import uuid
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import Session


class SessionRepository:
    """Handles data access patterns for Session model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: uuid.UUID) -> Session | None:
        """Fetch a Session by ID."""
        result = await self.db.execute(select(Session).where(Session.id == session_id))
        return result.scalar_one_or_none()

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        """Fetch a Session by token hash, eagerly loading the user to prevent N+1 queries."""
        result = await self.db.execute(
            select(Session)
            .options(selectinload(Session.user))
            .where(Session.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_active_by_user_id(self, user_id: uuid.UUID, now: datetime) -> list[Session]:
        """Fetch all active sessions for a user, ordered by last used time."""
        result = await self.db.execute(
            select(Session)
            .where(Session.user_id == user_id, Session.expires_at > now)
            .order_by(Session.last_used_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, session: Session) -> Session:
        """Add a new Session to the database."""
        self.db.add(session)
        return session

    async def delete(self, session: Session) -> None:
        """Remove a Session."""
        await self.db.delete(session)

    async def delete_by_token_hash(self, token_hash: str) -> None:
        """Remove a Session by its token hash."""
        result = await self.db.execute(
            select(Session).where(Session.token_hash == token_hash)
        )
        session = result.scalar_one_or_none()
        if session:
            await self.db.delete(session)

    async def delete_all_by_user_id(self, user_id: uuid.UUID) -> None:
        """Remove all Sessions for a user."""
        await self.db.execute(
            delete(Session).where(Session.user_id == user_id)
        )

    async def delete_expired_sessions(self, now: datetime) -> int:
        """Remove expired sessions and return the count of deleted sessions."""
        result = await self.db.execute(
            delete(Session).where(Session.expires_at < now)
        )
        return result.rowcount
