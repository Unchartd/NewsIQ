"""Pydantic schemas for story endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field

def _ensure_utc(v: Any) -> Any:
    if isinstance(v, datetime) and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v

UTCDateTime = Annotated[datetime, BeforeValidator(_ensure_utc)]

# ──────────────────────────────────────────────
# Story Sub-schemas
# ──────────────────────────────────────────────


class CategoryInStory(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    icon: str | None = None

    class Config:
        from_attributes = True


class SourceInStory(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    website_url: str | None = None
    logo_url: str | None = None
    country_code: str | None = None

    class Config:
        from_attributes = True


class StoryArticleResponse(BaseModel):
    id: uuid.UUID
    title: str | None = None
    description: str | None = None
    url: str
    author: str | None = None
    image_url: str | None = None
    published_at: UTCDateTime | None = None
    source: SourceInStory

    class Config:
        from_attributes = True


class StoryTimelineEventResponse(BaseModel):
    id: uuid.UUID
    event_time: UTCDateTime | None = None
    event_time_raw: str | None = None  # Raw AI string (e.g. "08:00 AM UTC") for display fallback
    description: str | None = None

    class Config:
        from_attributes = True


class StorySourceCoverageResponse(BaseModel):
    id: uuid.UUID
    source: SourceInStory
    focus_area: str | None = None
    published_at: UTCDateTime | None = None

    class Config:
        from_attributes = True


class StoryDifferenceResponse(BaseModel):
    id: uuid.UUID
    source: SourceInStory
    unique_information: str | None = None
    missing_information: str | None = None
    contradictions: str | None = None

    class Config:
        from_attributes = True


class StoryTagResponse(BaseModel):
    id: uuid.UUID
    tag_name: str

    class Config:
        from_attributes = True


class StoryEntityResponse(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_value: str

    class Config:
        from_attributes = True


class StoryMetricResponse(BaseModel):
    views: int
    bookmarks: int
    shares: int
    clicks: int

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Main Story Schemas
# ──────────────────────────────────────────────


class StoryListResponse(BaseModel):
    """Schema for listing stories in the feed."""

    id: uuid.UUID
    headline: str | None = None
    one_line_summary: str | None = None
    short_summary: str | None = None
    location_country: str | None = None
    location_state: str | None = None
    location_city: str | None = None
    trend_score: float | None = None
    first_seen_at: UTCDateTime | None = None
    updated_at: UTCDateTime | None = None
    category: CategoryInStory | None = None
    article_count: int = Field(0, description="Total count of articles covering this story")
    source_count: int = Field(0, description="Number of unique sources covering this story")
    source_logos: list[str] = Field(
        default_factory=list, description="URLs of logos for reporting sources"
    )
    story_status: str | None = "active"

    class Config:
        from_attributes = True


class StoryDetailResponse(BaseModel):
    """Schema for detailed story page."""

    id: uuid.UUID
    headline: str | None = None
    one_line_summary: str | None = None
    short_summary: str | None = None
    detailed_summary: str | None = None
    # key_facts: ordered bullet points extracted by Gemini
    key_facts: list[str] = Field(default_factory=list, description="Key factual bullet points")
    location_country: str | None = None
    location_state: str | None = None
    location_city: str | None = None
    trend_score: float | None = None
    first_seen_at: UTCDateTime | None = None
    updated_at: UTCDateTime | None = None
    category: CategoryInStory | None = None
    source_count: int = Field(0, description="Number of unique sources covering this story")

    # Associated items
    timeline_events: list[StoryTimelineEventResponse] = []
    source_coverage: list[StorySourceCoverageResponse] = []
    differences: list[StoryDifferenceResponse] = []
    tags: list[StoryTagResponse] = []
    entities: list[StoryEntityResponse] = []
    metrics: StoryMetricResponse | None = None

    # Linked articles
    articles: list[StoryArticleResponse] = []

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Widget Response Schemas
# ──────────────────────────────────────────────


class TrendingTopicWidget(BaseModel):
    topic: str
    count: str
    category: str


class PopularSourceWidget(BaseModel):
    name: str
    slug: str
    rating: str


class TrendingWidgetsResponse(BaseModel):
    trending_topics: list[TrendingTopicWidget]
    popular_sources: list[PopularSourceWidget]


class SearchResultResponse(BaseModel):
    """Lightweight story result for search."""

    id: uuid.UUID
    headline: str | None = None
    one_line_summary: str | None = None
    category: CategoryInStory | None = None
    trend_score: float | None = None
    updated_at: UTCDateTime | None = None
    article_count: int = 0
    source_count: int = 0

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    """Public category schema."""

    id: uuid.UUID
    slug: str
    name: str
    icon: str | None = None

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Source Comparison Schema
# ──────────────────────────────────────────────


class SourceComparisonItem(BaseModel):
    """Per-source analysis for the comparison view."""

    source: SourceInStory
    focus_area: str | None = None          # Short label: what this source focused on
    unique_information: str | None = None  # Details only this source reported
    missing_information: str | None = None # Key facts this source omitted
    contradictions: str | None = None      # Claims that conflict with other sources

    class Config:
        from_attributes = True


class StoryComparisonResponse(BaseModel):
    """Response schema for GET /stories/{id}/comparison."""

    story_id: uuid.UUID
    headline: str | None = None
    source_count: int = 0
    sources: list[SourceComparisonItem] = []
    source_coverage: list[StorySourceCoverageResponse] = []

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# Internal Admin Trigger Schemas
# ──────────────────────────────────────────────


class FetchNewsRequest(BaseModel):
    """Body for POST /internal/fetch-news."""

    gnews: bool = Field(True, description="Include GNews API fetch")
    rss: bool = Field(True, description="Include RSS feed fetch")


class FetchNewsResponse(BaseModel):
    """Response for POST /internal/fetch-news."""

    gnews_articles: int = 0
    rss_articles: int = 0
    total_articles: int = 0
    embedding_triggered: bool = False


class ProcessStoryResponse(BaseModel):
    """Response for POST /internal/process-story."""

    stories_created: int = 0
    articles_clustered: int = 0
    message: str = ""
