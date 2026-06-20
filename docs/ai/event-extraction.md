# Event Extraction Engine

> Phase 2 — Structured event parsing from news articles

## Overview

The Event Extraction Engine runs per-article (not per-story) and extracts structured event data BEFORE clustering. This is the foundation of the event-centric architecture — the system now understands WHAT happened before deciding which articles are about the same event.

## Schema

```python
class ExtractedEvent(BaseModel):
    event_type: str           # Canonical type: ATTACK, ELECTION, MERGER, etc.
    actors: list[str]         # WHO performed the action
    targets: list[str]        # WHO/WHAT was affected
    objects: list[str]        # KEY THINGS involved
    location: str             # WHERE it happened
    event_time: str | None    # WHEN it happened (NOT publication time)
    numbers: dict[str, Any]   # Key numerical data
    confidence: float         # 0.0-1.0 extraction confidence
```

## Pipeline Position

```text
Articles → Embedding → EVENT EXTRACTION → Clustering → AI Summary
                        ↑ NEW STEP
```

## Implementation

- **Service**: `app/services/event_service.py`
- **Model**: `ArticleEvent` in `app/models/models.py`
- **Table**: `article_events` (created via Alembic migration)
- **Task**: `extract_events_task` in Celery workers

## LLM Prompt Design

The extraction prompt is specifically designed to:
1. Separate event time from publication time
2. Identify actors and targets (not just entities)
3. Extract key numbers (casualties, amounts, counts)
4. Rate extraction confidence

The prompt explicitly warns: "event_time is WHEN THE EVENT HAPPENED, NOT when the article was published."

## Rate Limiting

Shares the same distributed Redis rate limiter as the AI synthesis service to avoid Gemini quota exhaustion.
