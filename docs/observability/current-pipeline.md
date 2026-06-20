# NewsIQ Pipeline — Observability Audit

> **Generated**: 2026-06-20
> **Purpose**: Map every pipeline stage, its current instrumentation, and observability gaps.

---

## Pipeline Overview

```
RSS Feeds / GNews API
        ↓
  [1] Ingestion (ingest_news_task / ingest_gnews_task)
        ↓
  [2] Crawling (crawler_service — multi-tier fallback)
        ↓
  [3] Deduplication (URL canonical + DB unique constraint + semantic)
        ↓
  [4] Embedding (process_pending_embeddings_task → Gemini/OpenAI → Qdrant)
        ↓
  [5] Event Extraction (extract_events_task → Gemini structured output)
        ↓
  [6] Incremental Merge (add_article_to_existing_story_if_similar)
        ↓
  [7] Batch Clustering (cluster_news_task → HDBSCAN)
        ↓
  [8] Entity Extraction (NER v2 → spaCy + heuristics)
        ↓
  [9] Entity Linking (entity_linker → Wikidata resolution)
        ↓
 [10] Knowledge Graph (build_story_knowledge_graph)
        ↓
 [11] Contradiction Detection (contradiction_service → LLM)
        ↓
 [12] Source Comparison (source_comparison_service → LLM)
        ↓
 [13] KG-Grounded Summarization (ai_service.summarize_story_from_kg → LLM)
        ↓
 [14] Meilisearch Indexing + Redis Cache Invalidation
        ↓
 [15] API Delivery (FastAPI → Next.js)
```

---

## Stage-by-Stage Audit

### Stage 1: Ingestion (RSS + GNews)

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Task** | `ingest_news_task` (every 5m), `ingest_gnews_task` (every 30m) |  |
| **Logging** | `logger.info("RSS: ingested %d new articles")` | No trace_id, no per-source breakdown, no latency |
| **Error Handling** | httpx timeouts (15s feeds, 10s crawl), Redis rate-limit locks | Errors logged but not counted as metrics |
| **Metrics** | None | Missing: articles_ingested_total, ingestion_latency, source_health |
| **Tracing** | None | No run_id to correlate ingestion → embedding → clustering |
| **Failure Modes** | GNews 429, RSS parse failure, Redis down | No dead-letter, no alerting |

### Stage 2: Crawling

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Task** | Inline within ingestion (asyncio.Semaphore(5)) |  |
| **Logging** | Fallback stack logged on failure | No per-URL latency, no success rate |
| **Error Handling** | 4-tier fallback: newspaper4k → trafilatura → readability-lxml → BS4 | Fallback choice not recorded |
| **Metrics** | None | Missing: crawl_success_rate, fallback_usage, paywall_hits |

### Stage 3: Deduplication

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Method** | URL canonicalization + DB unique + semantic title sim (>0.92) |  |
| **Logging** | Skip logged on URL match | Semantic dedup not logged, no count of duplicates |
| **Metrics** | None | Missing: duplicates_detected_total, dedup_method_breakdown |

### Stage 4: Embedding

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Task** | `process_pending_embeddings_task` (batch of 50) |  |
| **Provider** | Gemini text-embedding-004 → OpenAI fallback → mock |  |
| **Logging** | Count logged | No per-article latency, no token count, no cost |
| **Error Handling** | Per-article try/catch, status → "failed" | No retry count, no error classification |
| **Metrics** | None | Missing: embedding_latency, tokens_used, provider_fallback_count |

### Stage 5: Event Extraction

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Task** | `extract_events_task` (batch of 20) |  |
| **Provider** | Gemini structured output → OpenAI → mock |  |
| **Logging** | Success count logged | **No LLM call details**: prompt, response, tokens, cost, latency |
| **Error Handling** | Per-article try/catch, status → "failed" | No prompt capture on failure |
| **Rate Limiting** | Shared Redis rate limiter with synthesis | No visibility into wait times |

### Stage 6: Incremental Merge

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Trigger** | After each embedding, before batch clustering |  |
| **Logic** | Qdrant similarity search (>0.80) + multi-signal event similarity |  |
| **Logging** | Merge/reject logged with similarity score | No aggregate merge stats |
| **Metrics** | None | Missing: merge_rate, similarity_score_distribution |

### Stage 7: Batch Clustering (HDBSCAN)

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Task** | `cluster_news_task` (every 10m) |  |
| **Algorithm** | HDBSCAN (min_cluster_size=2, epsilon=0.35) |  |
| **Logging** | Stories created count | No cluster quality metrics, no outlier count |
| **Metrics** | None | Missing: clusters_created, outlier_rate, cluster_size_distribution |

### Stage 8-9: Entity Extraction + Linking

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **NER** | `ner_service_v2` (spaCy + custom rules) |  |
| **Linking** | `entity_linker` → Wikidata API + local coreference |  |
| **Logging** | Entity count per story | No confidence distribution, no link success rate |
| **Metrics** | None | Missing: entities_per_story, link_rate, wikidata_api_latency |

### Stage 10: Knowledge Graph

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Builder** | `build_story_knowledge_graph()` |  |
| **Storage** | JSONB column on Story model |  |
| **Logging** | Success/failure logged | No graph size metrics (nodes, edges) |

### Stage 11-12: Contradiction + Source Comparison

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Provider** | LLM-based (Gemini → OpenAI → mock) |  |
| **Logging** | Success/failure logged | **No LLM call capture**: prompt, tokens, cost, latency |
| **Metrics** | None | Missing: contradictions_per_story, comparison_latency |

### Stage 13: KG-Grounded Summarization

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Provider** | Gemini → OpenAI → mock with model fallback chain |  |
| **Rate Limiting** | Redis distributed limiter (8s interval) |  |
| **Logging** | Model fallback logged | **No token/cost tracking**, no prompt versioning |
| **Metrics** | None | Missing: summary_latency, tokens_per_summary, cost_per_story |

### Stage 14: Indexing + Cache

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **Meilisearch** | Story document indexed |  |
| **Redis** | Story cache + trending cache invalidated |  |
| **Logging** | Failure logged as warning | No indexing latency |

### Stage 15: API + Frontend

| Aspect | Current State | Gap |
|--------|--------------|-----|
| **API** | FastAPI with request_id middleware |  |
| **Sentry** | Initialized with DSN, traces_sample_rate=1.0 | No custom breadcrumbs, no trace_id attachment |
| **Frontend** | Next.js 15 | No error boundary instrumentation |

---

## Critical Blind Spots Summary

1. **No end-to-end trace correlation** — Cannot follow a single article from RSS → story
2. **Zero LLM cost tracking** — ~6 LLM calls per story with no token/cost capture
3. **No queue visibility** — Celery task health is invisible
4. **No pipeline DAG view** — Cannot see what's running/pending/failed
5. **No replay capability** — Cannot re-run any stage for debugging
6. **No prompt versioning** — Prompts embedded in code with no history
7. **No real-time monitoring** — Must check logs after the fact
8. **No human review loop** — No way to correct AI outputs
