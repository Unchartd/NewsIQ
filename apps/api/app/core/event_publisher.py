"""Event Publisher abstraction for domain events.

Provides an interface for publishing events to an Event Bus (e.g., Redis Streams/Kafka).
Currently implemented as a LoggingEventPublisher until the actual bus is wired in Phase B8.
"""

import logging
import uuid
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class DomainEvent(BaseModel):
    """Base schema for all domain events."""

    event_id: UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: int = 1

    model_config = ConfigDict(from_attributes=True)


class StoryLifecycleChanged(DomainEvent):
    """Event emitted when a story's lifecycle state transitions."""

    story_id: UUID
    canonical_event_id: str | None
    old_state: str
    new_state: str
    reason: str
    story_version: int
    health_metrics: dict[str, Any] | None = None


class EventPublisher:
    """Abstract interface for event publishing."""

    def publish(self, topic: str, event: DomainEvent) -> None:
        raise NotImplementedError


class LoggingEventPublisher(EventPublisher):
    """A publisher that logs events to the standard logger."""

    def publish(self, topic: str, event: DomainEvent) -> None:
        try:
            event_json = event.model_dump_json()
            logger.info(f"EVENT_PUBLISHED [{topic}]: {event_json}")
        except Exception as e:
            logger.error(f"Failed to log event for topic {topic}: {str(e)}")


# Global singleton
event_publisher = LoggingEventPublisher()
