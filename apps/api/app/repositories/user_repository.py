import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Handles data access patterns for User model."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a User by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a User by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_verification_token(self, token: str) -> User | None:
        """Fetch a User by email verification token."""
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        result = await self.db.execute(
            select(User).where(User.email_verification_token == hashed_token)
        )
        return result.scalar_one_or_none()

    async def get_by_password_reset_token(self, token: str) -> User | None:
        """Fetch a User by password reset token."""
        hashed_token = hashlib.sha256(token.encode()).hexdigest()
        result = await self.db.execute(
            select(User).where(User.password_reset_token == hashed_token)
        )
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """Add a new User to the session."""
        self.db.add(user)
        return user

    async def save(self, user: User) -> User:
        """Flush changes to the database and return user."""
        await self.db.flush()
        return user
