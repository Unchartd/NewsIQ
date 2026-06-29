# NewsIQ AI Pipeline Flow

This document details the end-to-end event-centric AI synthesis pipeline, including stages, LLM invocations, caching layers, and database records.

---

## 1. End-to-End Flow Diagram

The pipeline processes incoming articles, canonicalizes events/entities, builds a story-level knowledge graph, performs difference/contradiction analysis, and synthesizes final summaries.

```
[RSS/GNews Feeds]
       │
       ▼
1. Ingestion (Crawler) ──► [Articles Table]
                               │
                               ▼
2. Vector Embedding ──► [Qdrant Vector DB]
                               │
                               ▼
3. Event Extraction ──► [Article Events Table]
                               │
                               ▼
4. Entity Extraction & Linking ──► [Article Entities Table]
                               │
                               ▼
5. Multi-Signal Clustering ──► [Stories Table]
                               │
                               ├─► 6. Contradiction Detection
                               ├─► 7. Source Comparison
                               ├─► 8. Knowledge Graph Generation
                               │
                               ▼
9. Summary Generation (LLM Synthesis)
                               │
                               ▼
10. Quality Gate (Summary Reflection) ──► [Filtered Stories]
```

---

## 2. Pipeline Stages & Telemetry

Each execution stage is wrapped in a `StageSpan` context manager, which automatically aggregates:
- **Trace IDs** and **Run IDs** for observability.
- **Token counts** (input/output) and **USD Costs**.
- **Execution Latencies** (recorded in Prometheus and Postgres).

### Stage 1: Ingestion
- **Trigger**: Celery Beat schedules.
- **Task**: Crawl and parse RSS feeds. Stores raw articles.

### Stage 2: Embedding Generation
- **Model**: `gemini-embedding-2` (fallback to OpenAI `text-embedding-3-small`).
- **Cache**: Checked against `EmbeddingCache` (`newsiq:embedding:{model}:{text_hash}`) to avoid re-generating embeddings.

### Stage 3: Event Extraction
- **Model**: Routed via `ModelRouter`.
- **Cache**: Content-addressed `PipelineCache` key based on prompt and article content hashes.

### Stage 4: Entity Extraction & Linking
- **Model**: Routed via `ModelRouter` (hybrid resolution: Wikidata search + LLM disambiguation).
- **Cache**: Checked against database and Redis `newsiq:entity_link:{slug}`.

### Stage 5: Story Clustering
- **Algorithm**: HDBSCAN (for batch clustering) + Multi-Signal Similarity gating.
- **Gating**: Uses event overlap (actors, locations, times) and Jaccard entity similarity.

### Stage 6: Contradiction & Source Comparison
- **Concurrency**: Executed concurrently via `asyncio.gather()`.
- **Cache**: Stage-level caching using story input composite hashes.

### Stage 7: Summary & Reflection
- **Trigger**: Signal-based checks (`should_run_reflection`).
- **Flow**: Generates summary from KG, runs Reflection Agent to check for hallucinations, and regenerates if errors are found.
