"""SQLAlchemy models for ConsentPreference and ConsentAuditLog."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
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
    from app.models.user import User


class ConsentPreference(Base):
    __tablename__ = "consent_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=True, index=True
    )
    anonymous_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    essential: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    functional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    analytics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marketing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    region: Mapped[str] = mapped_column(String(50), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(50), nullable=False)

    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="consent_preference")


class ConsentAuditLog(Base):
    __tablename__ = "consent_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    anonymous_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    action: Mapped[str] = mapped_column(String(50), nullable=False)  # accept_all, reject_all, update_settings, withdrawn_consent, reset_consent
    
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSONB, nullable=False)

    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)
    consent_version: Mapped[str] = mapped_column(String(50), nullable=False)
