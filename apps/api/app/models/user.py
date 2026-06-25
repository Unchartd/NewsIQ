"""SQLAlchemy models for User and UserPreference."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    """Return current UTC time (timezone-naive, consistent with DB storage)."""
    return datetime.now(UTC).replace(tzinfo=None)


def generate_uuid() -> uuid.UUID:
    """Generate a UUID v7 (time-ordered) if uuid7 is available, else v4."""
    try:
        from uuid7 import uuid7

        return uuid7()
    except ImportError:
        return uuid.uuid4()


if TYPE_CHECKING:
    from app.models.consent import ConsentPreference
    from app.models.models import (
        ApiKey,
        Bookmark,
        DigestSubscription,
        Notification,
        OAuthAccount,
        SearchHistory,
        UserCategory,
        UserEvent,
        UserLocation,
    )
    from app.models.session import Session


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    role: Mapped[str] = mapped_column(String(30), default="user")
    subscription_plan: Mapped[str] = mapped_column(String(30), default="free")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    # Failed login protection
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Email verification support
    email_verification_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    email_verification_expiry: Mapped[datetime | None] = mapped_column(nullable=True)

    # Password reset support
    password_reset_token: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    password_reset_expiry: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    preferences: Mapped["UserPreference | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    consent_preference: Mapped["ConsentPreference | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    search_history: Mapped[list["SearchHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    digest_subscriptions: Mapped[list["DigestSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_events: Mapped[list["UserEvent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_categories: Mapped[list["UserCategory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_locations: Mapped[list["UserLocation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    preferred_summary_type: Mapped[str | None] = mapped_column(String(20))
    theme: Mapped[str | None] = mapped_column(String(20))
    language: Mapped[str | None] = mapped_column(String(20))
    digest_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ui_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="preferences")
