# Replay Execution Engine

This document details the replay system, which allows replaying the intelligence pipeline for existing stories.

---

## 1. Localized Stage Replays

Instead of re-running the entire end-to-end ingestion pipeline (which would fetch RSS feeds, process embeddings, etc.), developers can trigger localized replays of specific story intelligence stages directly from the admin dashboard.

The system supports the following isolated stages:
*   **RSS Ingestion** (`ingestion_rss`): Re-fetches the feed XML and forces a raw parsing cycle.
*   **Event Extraction** (`event_extraction`): Re-runs the LLM event parsing schema on the raw article text.
*   **Entity Extraction** (`entity_extraction`): Re-runs Named Entity Recognition (NER) and Wikidata resolution.
*   **Clustering** (`clustering`): Re-evaluates similarity indices and groups articles into story clusters.
*   **Summarization** (`summary_generation`): Re-synthesizes the headlines and bullet-point summaries.
*   **Reflection** (`reflection`): Re-evaluates the output against criteria like contradiction checks.

---

## 2. Replay Execution Logic

A replay runs inside a specialized `PipelineRun` block with `is_replay=True`:

```python
# From replay_service.py:
async def trigger_stage_replay(story_id: uuid.UUID, stage: str, session: AsyncSession) -> uuid.UUID:
    """Triggers an out-of-band Celery worker task to replay a specific stage of a story."""
    
    # 1. Fetch original inputs from DB
    story = await session.get(Story, story_id)
    if not story:
        raise ValueError("Story not found")
        
    # 2. Initialize Replay Run
    run = PipelineRunModel(
        trace_id=uuid.uuid4(),
        trigger="manual",
        pipeline_type="replay",
        is_replay=True,
        status="running"
    )
    session.add(run)
    await session.commit()
    
    # 3. Dispatch specific worker task
    if stage == "summary_generation":
        generate_summary_task.delay(story_id=story.id, run_id=run.id, trace_id=run.trace_id)
    elif stage == "entity_extraction":
        extract_entities_task.delay(story_id=story.id, run_id=run.id, trace_id=run.trace_id)
        
    return run.id
```

---

## 3. Side-by-Side Comparison UI

The replay system provides a side-by-side comparison interface under `/admin/replay` where developers can inspect the changes before applying them:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🔄 REPLAY OUT-OF-BAND COMPARATOR                                                       │
├───────────────────────────────────────┬────────────────────────────────────────────────┤
│ 📄 ORIGINAL SYNTHESIS                 │ 🔄 REPLAYED SYNTHESIS (Draft)                  │
├───────────────────────────────────────┼────────────────────────────────────────────────┤
│ Headline: "Election called for July"  │ Headline: "PM Declares Parliament Dissolution" │
│ Summary: The PM announced election... │ Summary: Rishi Sunak has called a surprise...  │
│ Latency: 640ms                        │ Latency: 420ms (Improved)                      │
│ Cost: $0.00021                        │ Cost: $0.00011 (Saved 47%)                     │
├───────────────────────────────────────┴────────────────────────────────────────────────┤
│ [ ❌ Discard Replay Draft ]                                  [ ✔️ Accept & Publish ]   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
When `Accept & Publish` is clicked, the draft is committed to the main `stories` database table, Meilisearch cache is invalidated, and the new results are served to the user-facing web client.
