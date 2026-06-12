"""Pydantic schemas for news sources."""

from datetime import datetime
import uuid
from pydantic import BaseModel, Field, HttpUrl


class SourceBase(BaseModel):
    """Base news source payload."""
    name: str = Field(..., min_length=1, max_length=255)
    website_url: str | None = Field(None, max_length=2000)
    logo_url: str | None = Field(None, max_length=2000)
    country_code: str | None = Field(None, min_length=2, max_length=10)
    rss_url: str | None = Field(None, max_length=2000)
    active: bool = True


class SourceCreate(SourceBase):
    """Payload for creating a news source."""
    slug: str = Field(..., min_length=1, max_length=255)


class SourceUpdate(BaseModel):
    """Payload for updating a news source."""
    name: str | None = Field(None, min_length=1, max_length=255)
    website_url: str | None = Field(None, max_length=2000)
    logo_url: str | None = Field(None, max_length=2000)
    country_code: str | None = Field(None, min_length=2, max_length=10)
    rss_url: str | None = Field(None, max_length=2000)
    active: bool | None = None


class SourceResponse(SourceBase):
    """Response payload for news source."""
    id: uuid.UUID
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True
