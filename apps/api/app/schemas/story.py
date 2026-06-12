"""Pydantic schemas for story endpoints."""

from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Story Sub-schemas
# ──────────────────────────────────────────────

class CategoryInStory(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    icon: Optional[str] = None

    class Config:
        from_attributes = True


class SourceInStory(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    website_url: Optional[str] = None
    logo_url: Optional[str] = None
    country_code: Optional[str] = None

    class Config:
        from_attributes = True


class StoryArticleResponse(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    description: Optional[str] = None
    url: str
    author: Optional[str] = None
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    source: SourceInStory

    class Config:
        from_attributes = True


class StoryTimelineEventResponse(BaseModel):
    id: uuid.UUID
    event_time: Optional[datetime] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class StorySourceCoverageResponse(BaseModel):
    id: uuid.UUID
    source: SourceInStory
    focus_area: Optional[str] = None
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StoryDifferenceResponse(BaseModel):
    id: uuid.UUID
    source: SourceInStory
    unique_information: Optional[str] = None
    missing_information: Optional[str] = None
    contradictions: Optional[str] = None

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
    headline: Optional[str] = None
    one_line_summary: Optional[str] = None
    short_summary: Optional[str] = None
    location_country: Optional[str] = None
    location_state: Optional[str] = None
    location_city: Optional[str] = None
    trend_score: Optional[float] = None
    first_seen_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    category: Optional[CategoryInStory] = None
    article_count: int = Field(0, description="Total count of articles covering this story")
    source_logos: List[str] = Field(default_factory=list, description="URLs of logos for reporting sources")

    class Config:
        from_attributes = True


class StoryDetailResponse(BaseModel):
    """Schema for detailed story page."""
    id: uuid.UUID
    headline: Optional[str] = None
    one_line_summary: Optional[str] = None
    short_summary: Optional[str] = None
    detailed_summary: Optional[str] = None
    location_country: Optional[str] = None
    location_state: Optional[str] = None
    location_city: Optional[str] = None
    trend_score: Optional[float] = None
    first_seen_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    category: Optional[CategoryInStory] = None
    
    # Associated items
    timeline_events: List[StoryTimelineEventResponse] = []
    source_coverage: List[StorySourceCoverageResponse] = []
    differences: List[StoryDifferenceResponse] = []
    tags: List[StoryTagResponse] = []
    entities: List[StoryEntityResponse] = []
    metrics: Optional[StoryMetricResponse] = None
    
    # Linked articles
    articles: List[StoryArticleResponse] = []

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
    trending_topics: List[TrendingTopicWidget]
    popular_sources: List[PopularSourceWidget]
