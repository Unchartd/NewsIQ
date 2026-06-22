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
from app.models.session import Session as Session  # noqa: F401
from app.models.user import User as User  # noqa: F401
from app.models.user import UserPreference as UserPreference  # noqa: F401


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
    events: Mapped[list["ArticleEvent"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    article_entities: Mapped[list["ArticleEntity"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    # Track event extraction pipeline status
    event_extraction_status: Mapped[str | None] = mapped_column(
        String(30), default="pending"
    )

    __table_args__ = (
        Index("idx_articles_published", published_at.desc()),
        Index("idx_articles_source", "source_id"),
    )


# ──────────────────────────────────────────────
# Article Events (Event Extraction Pipeline)
# ──────────────────────────────────────────────


class ArticleEvent(Base):
    """Structured event extracted from a single article.

    Stores WHO did WHAT to WHOM, WHERE, WHEN — extracted by EventService
    before clustering. This is the foundation for event-centric clustering.
    """

    __tablename__ = "article_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    event_type: Mapped[str] = mapped_column(String(100))
    event_type_canonical: Mapped[str | None] = mapped_column(String(100))
    actors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    targets: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    objects: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255))
    event_time: Mapped[datetime | None] = mapped_column()
    event_time_raw: Mapped[str | None] = mapped_column(String(255))
    numbers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    event_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    article: Mapped["Article"] = relationship(back_populates="events")

    __table_args__ = (
        Index("idx_article_events_type", "event_type_canonical"),
        Index("idx_article_events_article", "article_id"),
        Index("idx_article_events_fingerprint", "event_fingerprint"),
    )


# ──────────────────────────────────────────────
# Article Entities (Per-Article Entity Extraction)
# ──────────────────────────────────────────────


class ArticleEntity(Base):
    """Named entity extracted from a single article during event extraction.

    Stores per-article entities before clustering, enabling entity overlap
    as a clustering signal. Linked to CanonicalEntity for global dedup.
    """

    __tablename__ = "article_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    canonical_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_entities.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_value: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(default=_now)

    article: Mapped["Article"] = relationship(back_populates="article_entities")
    canonical_entity: Mapped["CanonicalEntity | None"] = relationship()

    __table_args__ = (
        Index("idx_article_entities_article", "article_id"),
        Index("idx_article_entities_canonical", "canonical_entity_id"),
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
    # key_facts: ordered list of bullet-point facts extracted by Gemini
    # Stored as JSONB array of strings, e.g. ["Fact 1.", "Fact 2.", ...]
    key_facts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
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
    knowledge_graph: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

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
    contradictions: Mapped[list["StoryContradiction"]] = relationship(
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


class StoryContradiction(Base):
    __tablename__ = "story_contradictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )
    fact_type: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4))
    source_attribution: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    story: Mapped["Story"] = relationship(back_populates="contradictions")


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
        UUID(as_uuid=True), ForeignKey("stories.id", ondelete="CASCADE"), index=True
    )
    canonical_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("canonical_entities.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_value: Mapped[str] = mapped_column(String(255))

    story: Mapped["Story"] = relationship(back_populates="entities")
    canonical_entity: Mapped["CanonicalEntity | None"] = relationship()


class CanonicalEntity(Base):
    __tablename__ = "canonical_entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    canonical_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    wikidata_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    aliases: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # JSONB array of strings
    metadata_payload: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)


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
