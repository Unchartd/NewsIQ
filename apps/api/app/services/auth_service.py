"""Authentication service — business logic for register, login, sessions."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.models import Session as SessionModel, User, UserPreference


class AuthService:
    """Handles user authentication workflows."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self, name: str, email: str, password: str
    ) -> tuple[User, str, str]:
        """Register a new user. Returns (user, access_token, refresh_token).

        Raises ValueError if email already exists.
        """
        # Check for existing user
        result = await self.db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ValueError("An account with this email already exists.")

        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name,
            password_hash=hash_password(password),
            email_verified=False,
            role="user",
            subscription_plan="free",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(user)

        # Create default preferences
        prefs = UserPreference(
            id=uuid.uuid4(),
            user_id=user.id,
            preferred_summary_type="short",
            theme="system",
            language="en",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(prefs)

        await self.db.flush()

        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        return user, access_token, refresh_token

    async def login(
        self, email: str, password: str
    ) -> tuple[User, str, str]:
        """Authenticate user by email/password. Returns (user, access_token, refresh_token).

        Raises ValueError if credentials are invalid.
        """
        result = await self.db.execute(
            select(User).where(User.email == email, User.status == "active")
        )
        user = result.scalar_one_or_none()

        if not user or not user.password_hash:
            raise ValueError("Invalid credentials.")

        if not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials.")

        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        return user, access_token, refresh_token

    async def create_session(
        self,
        user_id: uuid.UUID,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> SessionModel:
        """Create a new session record in the database."""
        from app.core.config import settings

        session = SessionModel(
            id=uuid.uuid4(),
            user_id=user_id,
            token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, User]:
        """Validate refresh token and return a new access token.

        Raises ValueError if refresh token is invalid or expired.
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token.")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid refresh token.")

        # Verify session exists in DB
        result = await self.db.execute(
            select(SessionModel).where(
                SessionModel.token == refresh_token,
                SessionModel.expires_at > datetime.now(timezone.utc),
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError("Session expired or invalid.")

        # Fetch user
        result = await self.db.execute(
            select(User).where(User.id == uuid.UUID(user_id), User.status == "active")
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found.")

        access_token = create_access_token({"sub": str(user.id)})
        return access_token, user

    async def logout(self, refresh_token: str) -> None:
        """Delete the session associated with the refresh token."""
        await self.db.execute(
            delete(SessionModel).where(SessionModel.token == refresh_token)
        )

    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Delete all sessions for a user."""
        await self.db.execute(
            delete(SessionModel).where(SessionModel.user_id == user_id)
        )

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
