"""SQLAlchemy ORM models for the NewsIQ platform.

All tables follow the Backend Schema Document:
- Plural table names
- UUID v7 primary keys
- Timestamp columns without timezone (UTC assumed)
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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


class DiscoveryState(enum.StrEnum):
    PENDING = "discovery_pending"
    GROUPING = "discovery_grouping"
    READY = "discovery_ready"
    CLUSTER_CREATED = "cluster_created"
    EXPIRED = "expired"


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


class DiscoveryQueue(Base):
    __tablename__ = "discovery_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), unique=True
    )
    state: Mapped[DiscoveryState] = mapped_column(
        String(50), default=DiscoveryState.PENDING, index=True
    )
    cluster_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_retry_reason: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column()

    created_at: Mapped[datetime | None] = mapped_column(default=_now)
    updated_at: Mapped[datetime | None] = mapped_column(default=_now, onupdate=_now)
    expires_at: Mapped[datetime | None] = mapped_column(index=True)

    article: Mapped["Article"] = relationship()


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

    # Phase B2: Deduplication and Fingerprinting
    url_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    semantic_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fingerprint_version: Mapped[int] = mapped_column(Integer, default=1)
    duplicate_of_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    source: Mapped["Source"] = relationship(back_populates="articles")
    events: Mapped[list["ArticleEvent"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    article_entities: Mapped[list["ArticleEntity"]] = relationship(
        back_populates="article", cascade="all, delete-orphan"
    )
    # Track event extraction pipeline status
    event_extraction_status: Mapped[str | None] = mapped_column(String(30), default="pending")

    __table_args__ = (
        Index("idx_articles_published", published_at.desc()),
        Index("idx_articles_source", "source_id"),
        Index("idx_articles_content_hash", "content_hash"),
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


class EventAlias(Base):
    """Tracks merged or redirected canonical event IDs to preserve history."""

    __tablename__ = "event_aliases"

    alias_event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    canonical_event_id: Mapped[str] = mapped_column(String(100), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)


class StoryLifecycleState(enum.StrEnum):
    EMERGING = "emerging"
    DEVELOPING = "developing"
    MONITORING = "monitoring"
    STABLE = "stable"
    ARCHIVED = "archived"


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

    # Lifecycle State
    lifecycle_state: Mapped[str] = mapped_column(
        String(30), default=StoryLifecycleState.EMERGING, index=True
    )
    canonical_event_id: Mapped[str | None] = mapped_column(String(100), index=True)
    canonical_event_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("story_versions.id", use_alter=True, name="fk_stories_current_version_id"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    transition_reason: Mapped[str | None] = mapped_column(Text)

    # Lifecycle Timestamps
    lifecycle_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
    last_discovery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_significant_update_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Health Metrics
    confidence_score: Mapped[float | None] = mapped_column(Float, index=True)
    freshness_score: Mapped[float | None] = mapped_column(Float, index=True)
    source_diversity_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    contradiction_score: Mapped[float | None] = mapped_column(Float, index=True)

    category: Mapped["Category | None"] = relationship()
    articles: Mapped[list["StoryArticle"]] = relationship(
        back_populates="story", cascade="all, delete-orphan"
    )
    versions: Mapped[list["StoryVersion"]] = relationship(
        back_populates="story", cascade="all, delete-orphan", foreign_keys="[StoryVersion.story_id]"
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

    __table_args__ = (UniqueConstraint("story_id", "source_id", name="uq_story_source_coverage"),)


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

    __table_args__ = (UniqueConstraint("story_id", "source_id", name="uq_story_difference"),)


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


class SynthesisArtifact(Base):
    __tablename__ = "synthesis_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id"))
    artifact_type: Mapped[str] = mapped_column(
        String(50)
    )  # summary, timeline, knowledge_graph, source_comparison, contradictions
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    __table_args__ = (
        UniqueConstraint("story_id", "artifact_type", "content_hash"),
        Index("idx_synthesis_artifacts_hash", "story_id", "artifact_type", "content_hash"),
    )


class StoryVersion(Base):
    __tablename__ = "story_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    pipeline_version: Mapped[str] = mapped_column(String(20))

    summary_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthesis_artifacts.id")
    )
    timeline_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthesis_artifacts.id")
    )
    kg_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthesis_artifacts.id")
    )
    source_comparison_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthesis_artifacts.id")
    )
    contradiction_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("synthesis_artifacts.id")
    )

    llm_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    trigger: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(default=_now)

    story: Mapped["Story"] = relationship(back_populates="versions", foreign_keys=[story_id])
    __table_args__ = (
        UniqueConstraint("story_id", "version_number"),
        Index("idx_story_versions_story", "story_id", "version_number"),
    )


class StoryReview(Base):
    __tablename__ = "story_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id"))
    story_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("story_versions.id")
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    summary_quality: Mapped[int] = mapped_column(Integer)
    hallucination_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_facts_count: Mapped[int] = mapped_column(Integer, default=0)
    contradiction_accuracy: Mapped[int] = mapped_column(Integer)
    source_coverage_score: Mapped[int] = mapped_column(Integer)
    source_diversity_score: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(default=_now)


# ──────────────────────────────────────────────
# Story-First Pipeline: StoryCandidate
# ──────────────────────────────────────────────


class StoryCandidateState(enum.StrEnum):
    """Lifecycle states for a StoryCandidate.

    Transitions:
        COLLECTING → DISCOVERING (on early dispatch threshold OR collect_until timeout)
        DISCOVERING → DISCOVERED (on successful search)
        DISCOVERED  → CRAWLING   (on CrawlTask creation)
        CRAWLING    → READY      (when all CrawlTasks complete)
        READY       → CLUSTERED  (when assigned to a Story)
        Any         → EXPIRED    (on timeout / budget exceeded)
    """

    COLLECTING  = "collecting"   # Buffering RSS sources; waiting for collection window
    DISCOVERING = "discovering"  # Search task dispatched; waiting for results
    DISCOVERED  = "discovered"   # Search complete; CrawlTasks created
    CRAWLING    = "crawling"     # At least one CrawlTask in progress
    READY       = "ready"        # All CrawlTasks done; articles persisted
    CLUSTERED   = "clustered"    # Story record created and linked
    EXPIRED     = "expired"      # Timed out or budget exceeded


class StoryCandidate(Base):
    """Central orchestration object for the Story-First ingestion pipeline.

    A StoryCandidate is created from RSS metadata *before* any article is crawled.
    Multiple RSS sources covering the same story attach to a single StoryCandidate
    (deduplicated by query_hash + date_bucket via a Redis SETNX guard).

    Relationships:
        story_candidate → 1:many → discovery_tasks
        story_candidate → 1:many → crawl_tasks  (direct shortcut, avoids JOIN)
    """

    __tablename__ = "story_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )

    # ── Query & Deduplication ──────────────────────────────────────────────────
    normalized_query: Mapped[str] = mapped_column(Text)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    date_bucket: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    headline: Mapped[str] = mapped_column(Text)            # Best headline observed
    discovery_provider: Mapped[str] = mapped_column(String(50), default="google_rss")

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(30), default=StoryCandidateState.COLLECTING, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    priority_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── RSS Source Aggregation ─────────────────────────────────────────────────
    # JSONB list of {source_name, url, published_at, score} dicts.
    # Appended each time a new RSS source attaches to this candidate.
    rss_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    rss_source_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── Collection Window ─────────────────────────────────────────────────────
    # dispatch_story_candidate_task fires via apply_async(eta=collect_until).
    # If rss_source_count reaches STORY_FIRST_EARLY_DISPATCH_THRESHOLD before
    # collect_until, an immediate .delay() fires and the ETA task becomes a no-op
    # (it checks status != COLLECTING and returns early).
    collect_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )
    search_dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    search_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # ── End-to-End Funnel Metrics ─────────────────────────────────────────────
    urls_found: Mapped[int] = mapped_column(Integer, default=0)
    urls_crawled: Mapped[int] = mapped_column(Integer, default=0)
    articles_persisted: Mapped[int] = mapped_column(Integer, default=0)
    articles_clustered: Mapped[int] = mapped_column(Integer, default=0)

    # ── Story Linkage ─────────────────────────────────────────────────────────
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    discovery_tasks: Mapped[list["DiscoveryTask"]] = relationship(
        back_populates="story_candidate",
        cascade="all, delete-orphan",
        foreign_keys="DiscoveryTask.story_candidate_id",
    )
    crawl_tasks: Mapped[list["CrawlTask"]] = relationship(
        back_populates="story_candidate",
        foreign_keys="CrawlTask.story_candidate_id",
    )

    __table_args__ = (
        UniqueConstraint("query_hash", "date_bucket", name="uq_story_candidate_query_date"),
        Index("idx_story_candidates_status", "status"),
        Index("idx_story_candidates_collect_until", "collect_until"),
        Index("idx_story_candidates_created", "created_at"),
        Index("idx_story_candidates_priority", "priority", "created_at"),
    )


# ──────────────────────────────────────────────
# Discovery & Crawl Task Infrastructure
# ──────────────────────────────────────────────


class DiscoveryTaskState(enum.StrEnum):
    PENDING = "pending"
    SEARCHING = "searching"
    URLS_FOUND = "urls_found"
    CRAWLING = "crawling"
    COMPLETE = "complete"
    SEARCH_FAILED = "search_failed"
    CRAWL_FAILED = "crawl_failed"
    EXPIRED = "expired"


class CrawlTaskState(enum.StrEnum):
    PENDING = "pending"
    CRAWLING = "crawling"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class DiscoveryTask(Base):
    """Represents a single search execution within the discovery pipeline.

    Story-First pipeline: story_candidate_id is the primary parent reference.
    Legacy pipeline: article_id is set (nullable for backward compat).
    """

    __tablename__ = "discovery_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )

    # ── Story-First parent reference (new) ────────────────────────────────────
    story_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("story_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Legacy parent reference (kept nullable for backward compat) ───────────
    # Populated by the old Article-First pipeline. New tasks leave this NULL.
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    query: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50))
    priority: Mapped[int] = mapped_column(Integer, default=50, index=True)
    priority_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=DiscoveryTaskState.PENDING, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_version: Mapped[int] = mapped_column(Integer, default=2)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    search_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    search_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    story_candidate: Mapped["StoryCandidate | None"] = relationship(
        back_populates="discovery_tasks",
        foreign_keys=[story_candidate_id],
    )
    article: Mapped["Article | None"] = relationship(foreign_keys=[article_id])
    crawl_tasks: Mapped[list["CrawlTask"]] = relationship(
        back_populates="discovery_task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_discovery_tasks_status", "status"),
        Index("idx_discovery_tasks_created", "created_at"),
        Index("idx_discovery_tasks_priority", "priority", "created_at"),
    )


class CrawlTask(Base):
    """Represents a single HTTP crawl of a discovered URL.

    story_candidate_id provides a direct shortcut to the parent StoryCandidate
    for completion tracking and funnel metrics (avoids an extra JOIN through
    discovery_tasks).

    tier indicates crawl priority:
        1 = Tier-1 trusted publishers (Reuters, AP, Bloomberg, BBC, Guardian)
        2 = Tier-2 standard publishers (CNN, NYT, WaPo, Fox, DW, France24)
        3 = Everything else (blogs, regional, unknown)
    CrawlTasks are created and dispatched in ascending tier order so that
    the highest-quality content is persisted first.
    """

    __tablename__ = "crawl_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    discovery_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discovery_tasks.id", ondelete="CASCADE"), index=True
    )

    # ── Direct shortcut to StoryCandidate (Story-First pipeline) ──────────────
    story_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("story_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default=CrawlTaskState.PENDING, index=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_version: Mapped[int] = mapped_column(Integer, default=2)

    # Publisher tier (1=highest quality, 3=default). Controls crawl dispatch order.
    tier: Mapped[int] = mapped_column(Integer, default=3)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=_now, index=True)
    crawl_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    discovery_task: Mapped["DiscoveryTask"] = relationship(back_populates="crawl_tasks")
    story_candidate: Mapped["StoryCandidate | None"] = relationship(
        back_populates="crawl_tasks",
        foreign_keys=[story_candidate_id],
    )
    persisted_article: Mapped["Article | None"] = relationship(foreign_keys=[article_id])

    __table_args__ = (
        Index("idx_crawl_tasks_status_outcome", "status", "outcome"),
        Index("idx_crawl_tasks_story_candidate", "story_candidate_id"),
        Index("idx_crawl_tasks_tier", "tier"),
    )


class DomainExtractionPolicy(Base):
    __tablename__ = "domain_extraction_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    local_success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tavily_success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    firecrawl_success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    average_latency: Mapped[float] = mapped_column(Float, default=0.0)
    average_content_length: Mapped[float] = mapped_column(Float, default=0.0)
    last_success_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)
