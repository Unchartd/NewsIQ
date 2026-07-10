# NewsIQ AI Pipeline Flow

This document details the end-to-end event-centric AI synthesis pipeline, including stages, LLM invocations, caching layers, database records, and gateway protections.

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
5. Multi-Signal Clustering ──► [Stories Table] (story_status = 'pending')
                               │
                               ├─► 6. Contradiction Detection
                               ├─► 7. Source Comparison
                               ├─► 8. Knowledge Graph Generation
                               │
                               ▼
9. Summary Generation (LLM Synthesis via AIGateway)
                               │
                               ▼
10. Quality Gate (Summary Reflection) ──► [Filter & Promote to 'active']
```

---

## 2. Centralized AI Gateway & Telemetry

All LLM and embedding invocations pass through the `AIGateway` (`app/ai/gateway.py`), which manages reliability, security, cost, and observability:

- **Structured Schema Validation**: Enforces Pydantic response formats.
- **Robust Output Correction**: The `clean_json_for_schema()` utility handles:
  - **Unnesting**: Detects and extracts nested JSON wrappers (e.g. `{"news_summary": {...}}`).
  - **Casing Mapping**: Automatically translates camelCase/PascalCase fields to snake_case.
  - **Summary Promotion**: Promotes generic `summary` values to specific sub-summaries.
  - **Coercion**: Converts string values to `list[str]` where the schema demands a list.
- **Circuit Breakers & Key Rotation**: Handled transparently by `CapabilityRouter` per provider.
- **Cost Budget Guardrails**: Check against daily budgets via `cost_budget_manager`, implementing a circuit-breaker that blocks calls if limits are reached.
- **Prometheus Observability**:
  - `newsiq_ai_gateway_calls_total` (labeled by provider, model, capability, status)
  - `newsiq_ai_gateway_cost_usd` (labeled by provider, model, capability)
  - `newsiq_ai_gateway_latency_seconds` (labeled by provider, model, capability)
  - `newsiq_ai_gateway_cache_total` (labeled by capability, status)
  - `newsiq_ai_gateway_circuit_state` (labeled by provider)

---

## 3. Pipeline Stages

### Stage 1: Ingestion
- **Trigger**: Celery Beat schedules.
- **Task**: Crawl and parse RSS/GNews feeds. Stores raw articles.

### Stage 2: Embedding Generation
- **Model**: Gemini `text-embedding-004` (fallback to `nvidia/llama-3.2-nv-embedqa-4b-v1`).
- **Cache**: Checked against Redis `EmbeddingCache` (`newsiq:embedding:{model}:{text_hash}`) to avoid re-generating embeddings.

### Stage 3: Event Extraction
- **Model**: Routed via `AIGateway` (`capability="event_extraction"`).
- **Cache**: Content-addressed `PipelineCache` key based on prompt and article content hashes.

### Stage 4: Entity Extraction & Linking
- **Model**: Routed via `AIGateway` (`capability="entity_linking"`).
- **Cache**: Checked against database and Redis `newsiq:entity_link:{slug}`.

### Stage 5: Story Clustering & Story Creation
- **Algorithm**: HDBSCAN (for batch clustering) + Multi-Signal Similarity gating.
- **Story Status**: New stories are inserted into the database with `story_status="pending"`. This hides them from clients until synthesis completes successfully.

### Stage 6: Contradiction & Source Comparison
- **Concurrency**: Executed concurrently via `asyncio.gather()`.
- **Cache**: Stage-level caching using story input composite hashes.

### Stage 7: Summary Generation
- **Model**: Routed via `AIGateway` (`capability="summary_generation"`).
- **Inputs**: Grounded on story timeline events, contradictions, source comparisons, and knowledge graph relations.

### Stage 8: Quality Gate (Summary Reflection) & Status Promotion
- **Reflection**: Summary is processed by a reflection prompt checking for hallucinations/errors.
- **Promotion**:
  - Upon successful generation and reflection validation, the story's status is updated to `story_status="active"`, making it visible to clients.
  - If generation fails, the pipeline attempts fallback headline/summary generation. If a valid fallback is constructed, status is updated to `"active"`.
  - If no headline can be produced, status is marked as `"failed"`.

---

## 4. API Query Protections

To guarantee that clients never encounter empty or incomplete news cards:
- **Default Filters**: The `/stories`, `/stories/search`, and personalized feed APIs default to fetching `story_status="active"` and apply strict `IS NOT NULL` and `!= ""` clauses to `headline` and `short_summary` fields.
- **Detail Access**: `GET /stories/{id}` returns `404 Not Found` if a story has a non-active status or contains an empty headline or summary.
