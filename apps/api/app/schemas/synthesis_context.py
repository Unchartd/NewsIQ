import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SourceContext:
    id: uuid.UUID
    name: str
    website_url: str | None
    country_code: str | None


@dataclass(frozen=True)
class ArticleContext:
    id: uuid.UUID
    source_id: uuid.UUID | None
    title: str | None
    description: str | None
    content: str | None
    url: str | None
    published_at: datetime | None


@dataclass(frozen=True)
class EventContext:
    id: uuid.UUID
    article_id: uuid.UUID | None
    event_type: str | None
    event_type_canonical: str | None
    location: str | None
    event_time: datetime | None
    event_time_raw: str | None
    confidence: float | None
    numbers: dict[str, Any] | None
    actors: list[str] | None
    targets: list[str] | None
    event_fingerprint: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class EntityContext:
    id: uuid.UUID
    story_id: uuid.UUID
    canonical_entity_id: uuid.UUID | None
    entity_type: str
    entity_value: str
    canonical_name: str | None
    wikidata_id: str | None
    aliases: list[str] | None
    description: str | None


@dataclass(frozen=True)
class StoryContext:
    id: uuid.UUID
    category_id: uuid.UUID | None
    category_slug: str
    headline: str | None
    story_status: str | None
    first_seen_at: datetime | None
    created_at: datetime | None
