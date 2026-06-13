"""SQLAlchemy ORM models for the NewsIQ platform.

All tables follow the Backend Schema Document:
- Plural table names
- UUID v7 primary keys
- Timestamp columns without timezone (UTC assumed)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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


# ──────────────────────────────────────────────
# Users & Auth
# ──────────────────────────────────────────────


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
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    # Relationships
    preferences: Mapped["UserPreference | None"] = relationship(
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
    created_at: Mapped[datetime | None] = mapped_column(default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(default=_now, onupdate=_now)

    user: Mapped["User"] = relationship(back_populates="preferences")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    token: Mapped[str] = mapped_column(Text, unique=True)
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="sessions")


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(50))
    provider_account_id: Mapped[str] = mapped_column(Text)
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column()

    user: Mapped["User"] = relationship(back_populates="oauth_accounts")


class UserCategory(Base):
    __tablename__ = "user_categories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), primary_key=True
    )

    user: Mapped["User"] = relationship(back_populates="user_categories")
    category: Mapped["Category"] = relationship()


class UserLocation(Base):
    __tablename__ = "user_locations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    country_code: Mapped[str | None] = mapped_column(String(10))
    state_name: Mapped[str | None] = mapped_column(String(100))
    city_name: Mapped[str | None] = mapped_column(String(100))

    user: Mapped["User"] = relationship(back_populates="user_locations")


# ──────────────────────────────────────────────
# Content: Categories, Sources, Articles
# ──────────────────────────────────────────────


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime | None] = mapped_column(default=_now)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    logo_url: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(String(10))
    rss_url: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    articles: Mapped[list["Article"]] = relationship(back_populates="source")


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"))
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, unique=True, index=True)
    author: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(20))
    image_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(index=True)
    crawled_at: Mapped[datetime | None] = mapped_column()
    embedding_status: Mapped[str | None] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    source: Mapped["Source"] = relationship(back_populates="articles")

    __table_args__ = (
        Index("idx_articles_published", published_at.desc()),
        Index("idx_articles_source", "source_id"),
    )


# ──────────────────────────────────────────────
# Stories & Related
# ──────────────────────────────────────────────


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    headline: Mapped[str | None] = mapped_column(Text)
    one_line_summary: Mapped[str | None] = mapped_column(Text)
    short_summary: Mapped[str | None] = mapped_column(Text)
    detailed_summary: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), index=True
    )
    location_country: Mapped[str | None] = mapped_column(String(100))
    location_state: Mapped[str | None] = mapped_column(String(100))
    location_city: Mapped[str | None] = mapped_column(String(100))
    trend_score: Mapped[float | None] = mapped_column(Numeric(10, 6))
    story_status: Mapped[str | None] = mapped_column(String(30), default="active")
    first_seen_at: Mapped[datetime | None] = mapped_column()
    # created_at is the canonical creation timestamp used for ordering/digest queries
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    updated_at: Mapped[datetime | None] = mapped_column(default=_now, onupdate=_now)

    category: Mapped["Category | None"] = relationship()
    articles: Mapped[list["StoryArticle"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[list["StoryTimelineEvent"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    entities: Mapped[list["StoryEntity"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    source_coverage: Mapped[list["StorySourceCoverage"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    differences: Mapped[list["StoryDifference"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    tags: Mapped[list["StoryTag"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    metrics: Mapped["StoryMetric | None"] = relationship(
        back_populates="story", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_stories_trend", trend_score.desc()),
        Index("idx_stories_updated", updated_at.desc()),
        Index("idx_stories_created", created_at.desc()),
    )


class StoryArticle(Base):
    __tablename__ = "story_articles"

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), primary_key=True
    )

    story: Mapped["Story"] = relationship(back_populates="articles")
    article: Mapped["Article"] = relationship()


class StoryTimelineEvent(Base):
    __tablename__ = "story_timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), index=True
    )
    event_time: Mapped[datetime | None] = mapped_column()
    # Raw date string from AI (e.g. "08:00 AM UTC") stored for display when parsing fails
    event_time_raw: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    story: Mapped["Story"] = relationship(back_populates="timeline_events")


class StorySourceCoverage(Base):
    __tablename__ = "story_source_coverage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"))
    focus_area: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column()

    story: Mapped["Story"] = relationship(back_populates="source_coverage")
    source: Mapped["Source"] = relationship()

    __table_args__ = (
        UniqueConstraint("story_id", "source_id", name="uq_story_source_coverage"),
    )


class StoryDifference(Base):
    __tablename__ = "story_differences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"))
    unique_information: Mapped[str | None] = mapped_column(Text)
    missing_information: Mapped[str | None] = mapped_column(Text)
    contradictions: Mapped[str | None] = mapped_column(Text)

    story: Mapped["Story"] = relationship(back_populates="differences")
    source: Mapped["Source"] = relationship()

    __table_args__ = (
        UniqueConstraint("story_id", "source_id", name="uq_story_difference"),
    )


class StoryTag(Base):
    __tablename__ = "story_tags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), index=True
    )
    tag_name: Mapped[str] = mapped_column(String(100))

    story: Mapped["Story"] = relationship(back_populates="tags")


class StoryEntity(Base):
    __tablename__ = "story_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30))  # PERSON, ORG, LOCATION, EVENT, COUNTRY
    entity_value: Mapped[str] = mapped_column(String(255))

    story: Mapped["Story"] = relationship(back_populates="entities")


class StoryMetric(Base):
    __tablename__ = "story_metrics"

    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), primary_key=True
    )
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    bookmarks: Mapped[int] = mapped_column(BigInteger, default=0)
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)

    story: Mapped["Story"] = relationship(back_populates="metrics")


# ──────────────────────────────────────────────
# User Engagement
# ──────────────────────────────────────────────


class Bookmark(Base):
    __tablename__ = "bookmarks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True, index=True
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), primary_key=True
    )
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="bookmarks")
    story: Mapped["Story"] = relationship()


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    query: Mapped[str | None] = mapped_column(Text)
    searched_at: Mapped[datetime | None] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="search_history")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    title: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    notification_type: Mapped[str | None] = mapped_column(String(50))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="notifications")


class DigestSubscription(Base):
    __tablename__ = "digest_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    frequency: Mapped[str | None] = mapped_column(String(30))
    delivery_channel: Mapped[str | None] = mapped_column(String(30))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="digest_subscriptions")


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), index=True
    )
    event_type: Mapped[str | None] = mapped_column(
        String(50)
    )  # view_story, bookmark_story, share_story, search
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="user_events")
    story: Mapped["Story | None"] = relationship()


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    key_hash: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(String(30))
    expires_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    user: Mapped["User"] = relationship(back_populates="api_keys")
