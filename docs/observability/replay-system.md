# Replay Execution Engine

This document details the replay system, which allows replaying the intelligence pipeline for existing stories.

## Overview

Instead of re-running the entire end-to-end ingestion pipeline (which would fetch RSS feeds, process embeddings, etc.), developers can trigger localized replays of specific story intelligence stages directly from the admin dashboard.

## Replayable Stages

Only the core AI-based analysis stages are replayable, as they rely on structured database relations rather than incoming feed APIs:

1.  **NLP Analysis** (`entity_extraction`): Re-runs Named Entity Recognition (NER) and links extracted entities to canonical databases.
2.  **Contradiction Engine** (`contradiction_detection`): Re-evaluates claims between sources in the story cluster to flag contradictions.
3.  **Timeline Builder** (`timeline_generation`): Re-builds the chronological event list from article events.
4.  **AI Summarization** (`summary_generation`): Re-synthesizes the story's headline, key facts, and summary text.

## Endpoint & Normalization

Replays are triggered via a POST request:
`POST /api/v1/admin/replay/{story_id}/{stage}`

The API performs upfront validation and normalization on the stage parameter:
*   Frontend stage aliases (e.g. `nlp_analysis`, `summarization`, `contradiction`) are normalized to their canonical backend representations (`entity_extraction`, `summary_generation`, `contradiction_detection`).
*   Invalid or non-replayable stages return a `400 Bad Request` explaining valid choices, preventing Celery task crashes.
