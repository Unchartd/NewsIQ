# Event Time vs Reporting Time

> Phase 4 — Separating when events happened from when articles were published

## The Problem

The old pipeline used `published_at` (article publication timestamp) for:
- Timeline generation
- Clustering decisions
- Contradiction detection

This is fundamentally wrong. Two articles published at different times can describe the SAME event that happened at the SAME time.

### Example: No Contradiction

| Source | Event Time | Published Time |
|:--|:--|:--|
| BBC | 2:00 PM | 3:00 PM |
| TOI | 2:00 PM | 5:00 PM |

**Same event, same time.** The publication delay is not a contradiction.

### Example: Real Conflict

| Source | Event Time | Published Time |
|:--|:--|:--|
| BBC | 2:00 PM | 3:00 PM |
| TOI | 3:00 PM | 5:00 PM |

**Same event, different reported times.** This is a legitimate `event_time_conflict`.

## Solution

### Database Schema

```sql
-- article_events table
event_time       TIMESTAMP,    -- When the event actually happened (parsed)
event_time_raw   VARCHAR(255), -- Raw time string from LLM extraction
```

### Extraction Prompt

The LLM extraction prompt explicitly states:
```
event_time is WHEN THE EVENT HAPPENED, NOT when the article was published.
The article was published at: {published_at}. Do NOT use this as event_time.
```

### Time Conflict Detection

```python
async def detect_event_time_conflict(
    self, events: list[ExtractedEvent]
) -> bool:
    """Check if multiple articles' events have conflicting event times."""
    times = [e.event_time for e in events if e.event_time]
    unique_times = set(times)
    return len(unique_times) > 1
```

## Pipeline Integration

- `event_time` is extracted during the Event Extraction step
- `published_at` remains on the Article model (used for recency scoring only)
- Timeline generation will use `event_time`, not `published_at` (Phase 11)
- Clustering ignores `published_at` differences (Phase 8)
