# NewsIQ Pipeline Architecture

> End-to-end data flow — from raw RSS to the API response consumed by the frontend.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                      │
│   RSS Sources → feedparser → crawl_article → fingerprint   │
│   → PostgreSQL (Article) → Bloom Filter (Redis)            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                     EMBEDDING LAYER                         │
│   EmbeddingService → Gemini text-embedding-004 (768-dim)   │
│   → Redis embedding cache → Qdrant upsert                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                     AI ENRICHMENT LAYER                     │
│   NER (ner_service_v2) → Event Extraction (event_service)  │
│   → Stage A Validation (deterministic)                     │
│   → Stage B Validation (Qdrant anchors)                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    CLUSTERING LAYER                         │
│   Qdrant similarity(0.80) → Reflection Agent (LLM)         │
│   → Judge Agent (disagreement arbitration)                 │
│   → StoryMerge or NewStory decision                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    SYNTHESIS LAYER                          │
│   Knowledge Graph → Timeline → StorySummaryResponse        │
│   (ai_service.summarize_story_from_kg via gemini-2.5-pro)  │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                      SERVING LAYER                          │
│   PostgreSQL (Story) → Meilisearch index → Redis cache     │
│   → FastAPI → StoryDetailResponse → React frontend         │
└─────────────────────────────────────────────────────────────┘
```

---

## Stage 1 — Ingestion

**Workers:** `apps/api/app/workers/ingestion_worker.py`  
**Celery Task:** `ingest_feeds`  
**Beat Schedule:** Every 5 minutes

| Step | Function | File |
|------|----------|------|
| Load sources | `SELECT * FROM sources WHERE rss_url IS NOT NULL` | `models/models.py` |
| Parse RSS | `feedparser.parse(rss_url)` | stdlib |
| Canonicalize URL | `canonicalize_url(url)` | `core/utils.py` |
| Bloom filter check | `url_bloom_filter.is_seen(url)` | `core/bloom_filter.py` |
| Discovery scoring | `IngestionService.calculate_discovery_score(...)` | `services/ingestion_service.py` |
| Crawl article | `ExtractionManager.crawl_article(url)` | `services/extraction_manager.py` |
| Compute fingerprints | `compute_fingerprints(url, title, body)` | `core/fingerprint.py` |
| Persist Article | `session.add(Article(...))` | `models/models.py` |

**Key Variables (Notebook):** `rss_sources`, `selected_entry`, `raw_crawl_result`, `fingerprints`, `article`, `article_id`

---

## Stage 2 — Embedding

**Service:** `apps/api/app/services/embedding_service.py`  
**Model:** `text-embedding-004` (768 dimensions, Google AI)  
**Cache:** Redis key `embed:<sha256(model:text)>`, TTL 24h  

| Step | Description |
|------|-------------|
| Prepare text | `title + summary + content[:4000]` |
| Cache check | Redis lookup on text hash |
| Generate vector | `embedding_service.get_embeddings([text])` |
| Store vector | `vector_service.upsert_article(article_id, vector, payload)` |

**Qdrant payload** stored alongside every vector:
```json
{
  "article_id": "uuid",
  "title": "...",
  "source_id": "uuid",
  "source_name": "Reuters",
  "published_at": "ISO-8601",
  "url": "https://...",
  "url_hash": "sha256hex"
}
```

**Key Variables (Notebook):** `embedding_text`, `embedding_vector`, `qdrant_upsert_result`

---

## Stage 3 — NER (Named Entity Recognition)

**Service:** `apps/api/app/services/ner_service_v2.py`  
**Prompt:** `entity_extraction` (versioned in `app/ai/prompts/`)  
**LLM:** gemini-flash (fast, cost-efficient)

Entities extracted: `PERSON`, `ORGANIZATION`, `LOCATION`, `EVENT`, `DATE`, `NUMBER`, `PRODUCT`, `LAW`

Each entity has:
- `type` — entity category
- `value` — canonical text form
- `confidence` — 0.0–1.0 float

**Key Variables (Notebook):** `entity_manifest`, `entities`

---

## Stage 4 — Event Extraction

**Service:** `apps/api/app/services/event_service.py`  
**Prompt:** `event_extraction`  
**Output schema:** `ArticleEventResponse`

```python
class ArticleEventResponse:
    primary_event: EventModel      # most significant event in the article
    secondary_events: list[EventModel]
    entities: list[EntityRef]

class EventModel:
    event_type: str       # POLITICAL, ECONOMIC, MILITARY, NATURAL, SOCIAL, CRIME, SPORTS, TECH
    actors: list[str]     # who performed the action
    targets: list[str]    # who/what was affected
    objects: list[str]    # physical objects involved
    location: str
    event_time: str       # ISO-8601 string or relative expression
    numbers: list[str]    # numeric facts mentioned
    confidence: float
```

**Fingerprinting:** SHA-256 of `event_type|sorted(actors)|sorted(targets)|location|date`  
Prevents duplicate events from multiple articles covering the same story.

**Key Variables (Notebook):** `event_manifest`, `events`, `raw_event_response`, `event_fingerprint`

---

## Stage 5 — Event Validation

**Service:** `apps/api/app/services/event_validation_service.py`

### Stage A — Deterministic Rules
No LLM, no network. Checks:
- `event_type` is a known enum value
- At least one actor present
- `confidence` ≥ threshold
- Not a duplicate fingerprint in DB

### Stage B — Vector Anchor Verification
Compares the new event's embedding against existing story anchors in Qdrant.  
Only runs if Stage A passes.

**Outcomes:** `PASS`, `FAIL`, `REVIEW`

**Key Variables (Notebook):** `stage_a_result`, `validated_events`

---

## Stage 6 — Story Clustering

**Service:** `apps/api/app/services/clustering_service.py`  
**Threshold:** `SIMILARITY_THRESHOLD = 0.80` (cosine similarity)

| Step | Description |
|------|-------------|
| Qdrant search | Find top-20 articles with score ≥ 0.80 |
| Load candidates | PostgreSQL `SELECT WHERE id IN (...)` |
| Reflection Agent | LLM verifies same real-world event |
| Judge Agent | Resolves provider disagreements |
| Decision | Merge into existing story OR create new story |

### Reflection Agent
**Prompt:** `cluster_verification`  
**Model:** gemini-flash  
**Input:** Article A text, Article B text, cosine similarity score  
**Output:** `{same_event: bool, confidence: float, reasoning: str}`

### Judge Agent
**File:** `apps/api/app/agents/judge_agent.py`  
**Framework:** Agno multi-agent framework  
Invoked when two providers disagree on `same_event`.  
Returns `{final_decision, chosen_provider, explanation}`.

**Key Variables (Notebook):** `qdrant_candidates`, `candidate_clusters`, `raw_reflection_response`, `reflection_result`, `judge_result`

---

## Stage 7 — Story Synthesis

**Service:** `apps/api/app/services/ai_service.py`  
**Function:** `summarize_story_from_kg(kg, contradictions, timeline, source_comparisons)`  
**Prompt:** `summary_generation`  
**Model:** `gemini-2.5-pro` (highest quality, most expensive)

### Inputs to LLM
```
knowledge_graph     JSONB graph (nodes: article, source, entity, event; edges: relations)
timeline            chronological event list
contradictions      conflicting facts across sources
source_comparisons  coverage analysis per source
```

### Outputs (StorySummaryResponse)
```python
class StorySummaryResponse:
    headline: str
    one_line_summary: str
    short_summary: str        # 2-3 paragraphs
    detailed_summary: str     # full analytical summary
    key_facts: list[str]      # 5-8 bullet facts
    category: str             # e.g. "politics", "economy", "technology"
```

**Timeline Construction:** All events (primary + secondary) sorted by `event_time`.  
**Knowledge Graph:** Nodes = articles, sources, entities, events; Edges = typed relations.

**Key Variables (Notebook):** `timeline`, `knowledge_graph`, `kg_dict`, `synthesis_manifest`, `raw_synthesis_response`, `story_summary`

---

## Stage 8 — Serving

### PostgreSQL (persistent store)
Tables written: `stories`, `story_articles`, `story_entities`, `story_timeline_events`, `story_metrics`

### Meilisearch (full-text search)
Document indexed: `id`, `headline`, `one_line_summary`, `category`, `entity_names`, `source_names`

### Redis (fast cache)
Key: `story:<story_id>`, TTL: `TTL_STORY` seconds  
Populated after story persistence; read on every API hit.

### FastAPI (API layer)
Route: `GET /api/v1/stories/{story_id}`  
Serializes via `StoryDetailResponse.model_validate(story_orm)`

**Key Variables (Notebook):** `saved_story`, `meili_document`, `redis_key`, `api_response`, `api_response_json`

---

## Gateway: All LLM Calls Flow Through `ai_gateway.generate_stage()`

**File:** `apps/api/app/ai/gateway.py`

```python
async def generate_stage(
    stage: str,                    # prompt key in repository
    prompt_variables: dict,        # template fill variables
    schema: type[BaseModel] | None # Pydantic response schema
) -> GatewayResponse:
    # 1. Resolve prompt manifest from PromptRepository
    # 2. Render system + user prompts
    # 3. Check semantic cache (Redis)
    # 4. Call provider (Gemini / DeepSeek / Anthropic)
    # 5. Parse structured output
    # 6. Track cost + latency
    # 7. Return GatewayResponse
```

**GatewayResponse fields:** `provider`, `model`, `content`, `parsed`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `error`

---

## Database Schema (Key Tables)

```
articles            — one row per crawled article
  id, url, url_hash, content_hash, title, content
  source_id → sources
  embedding_status, event_status, cluster_status

stories             — one row per clustered story
  id, headline, one_line_summary, short_summary, detailed_summary
  key_facts (JSONB), knowledge_graph (JSONB)
  story_status, cluster_confidence

story_articles      — N:M between stories and articles
story_entities      — entities extracted for a story
story_timeline_events — chronological events for a story
story_metrics       — views, clicks, bookmarks, shares

sources             — configured RSS news sources
  id, name, rss_url, country_code
```

---

## Prompt Versioning

All prompts live in `apps/api/app/ai/prompts/` as YAML files:

```yaml
stage: event_extraction
version: "1.3.0"
lifecycle: production
model_config:
  model: gemini-2.0-flash
  temperature: 0.1
  max_tokens: 2048
system: |
  You are an event extraction system...
template: |
  Article title: {title}
  Source: {source_name}
  Published: {published_at}
  Content: {content}
```

Loaded at startup by `PromptLoader → PromptCompiler → PromptRepository`.
