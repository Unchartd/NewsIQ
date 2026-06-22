# Current Pipeline Architecture

> Phase 2 — Event-Centric Transformation — June 2026

## Data Flow

```text
RSS Feeds / GNews API
       ↓
  IngestionService / GNewsService
       ↓
  CrawlerService (newspaper4k → trafilatura → readability → BS4)
       ↓
  PostgreSQL (articles table)
       ↓
  EmbeddingService (Gemini text-embedding-004, 768 dims)
       ↓
  Qdrant (vector DB)
       ↓
  EventService — Combined Event + Entity Extraction (single LLM call per article)
  ├── Extracts: event_type, actors, targets, location, event_time, numbers
  ├── Extracts: named entities (PERSON, ORG, COUNTRY, CITY, etc.)
  ├── Links entities to CanonicalEntity (Wikidata + LLM + Redis cache)
  └── Computes event_fingerprint hash for dedup
       ↓
  PostgreSQL (article_events + article_entities tables)
       ↓
  ClusteringService
  ├── Incremental: cosine sim ≥ 0.80 + event similarity ≥ 0.80 → merge
  └── Batch: HDBSCAN + event similarity splitting + entity overlap (10%)
           + fingerprint pre-grouping (incl. single-article clusters)
       ↓
  Story Generation Steps:
  ├── 1. Timeline Builder (processes event times & attributions)
  ├── 2. NER — uses pre-extracted ArticleEntities (fallback: NER v2 LLM)
  ├── 3. Entity Linker (coreference resolving + Wikidata linking)
  ├── 4. Knowledge Graph Builder (serialize event-actor-target relations)
  ├── 5. Contradiction & Source Comparison Engines
  └── 6. AIService Summarizer (KG-grounded generation using graph + contradictions + timeline)
       ↓
  PostgreSQL (stories + sub-tables)
       ↓
  Meilisearch (full-text search index) & Redis cache invalidation
```

## Scheduling (Celery Beat)

| Task | Interval | Purpose |
|:--|:--|:--|
| `ingest_news_task` | Every 5 minutes | RSS feed ingestion |
| `ingest_gnews_task` | Every 30 minutes | GNews API ingestion |
| `cluster_news_task` | Every 10 minutes | Batch HDBSCAN clustering |
| `process_pending_embeddings_task` | On-demand (chained) | Vectorize pending articles |
| `cleanup_expired_sessions_task` | Daily at midnight | Session cleanup |
| `process_hourly_digests_task` | Every hour | Email digest delivery |

## Embedding Pipeline

- **Input**: `title + description + content[:4000]`
- **Model**: Gemini `text-embedding-004` → 768 dimensions
- **Fallback**: OpenAI `text-embedding-3-small` (truncated to 768) → mock
- **Storage**: Qdrant with cosine distance

## Event + Entity Extraction (Per-Article)

A **single combined LLM call** per article extracts both structured events and named entities.
This eliminates redundant LLM calls during story generation.

- **Event fields**: event_type, actors, targets, objects, location, event_time, numbers, confidence
- **Entity fields**: value, type (25+ types), canonical_name
- **Event fingerprint**: SHA-256 hash of `(canonical_type, sorted_actors, sorted_targets, location, event_date)`
  - Articles with identical fingerprints describe the same event → pre-grouped before HDBSCAN
- **Entity linking**: Each entity is linked to a `CanonicalEntity` record (Wikidata ID + aliases) at extraction time
- **Storage**: `article_events` table (events + fingerprint), `article_entities` table (entities + canonical links)
- **Model chain**: gemini-2.5-flash-lite → OpenAI gpt-4o-mini → mock

## Clustering Strategy

### Incremental (Real-time)
1. After structured event extraction is completed for an article, search Qdrant for similar embedded articles with cosine similarity $\ge 0.80$.
2. If a similar article belongs to an existing story, retrieve that story's events.
3. Run multi-signal event similarity verification (actor Jaccard, target Jaccard, location match, taxonomy parent match, and temporal proximity) with a threshold of $\ge 0.80$.
4. If it passes verification, merge the new article into the existing story and regenerate all story content. Otherwise, reject the merge.

### Batch (HDBSCAN)
1. Every 10 minutes, collect all unclustered embedded articles.
2. If only one unclustered article is present, it directly forms a single-article cluster. Otherwise, run HDBSCAN with `min_cluster_size=2`, `min_samples=1`, and `epsilon=0.35`.
3. Outliers (noise labeled as `-1`) are preserved and treated as single-article clusters so they can undergo full AI analysis instead of being ignored.
4. Run multi-signal validation (event similarity + 10% entity overlap threshold $\ge 0.80$) on all groups. If a cluster contains conflicting events, split it into separate sub-clusters (articles lacking events default to 0.0 similarity and form their own clusters).
5. **Fingerprint pre-grouping**: After HDBSCAN splitting, articles sharing identical `event_fingerprint` are merged into the same cluster regardless of HDBSCAN label.
6. Create new Story objects for each verified sub-cluster (including single-article clusters).
7. Generate story content via the KG-grounded pipeline.

### Multi-Signal Similarity Weights

| Signal | Weight | Description |
|:--|:--|:--|
| Actor overlap (Jaccard) | 25% | WHO performed the action |
| Target overlap (Jaccard) | 20% | WHO/WHAT was affected |
| Location match | 20% | WHERE it happened |
| Event type hierarchy | 15% | WHAT happened (taxonomy match) |
| Temporal proximity | 10% | WHEN it happened (decay by days) |
| Entity overlap (canonical IDs) | 10% | Shared canonical entities across articles |

## AI Synthesis

- **Input**: Knowledge Graph (KG) JSON + detected contradictions list + timeline events + source comparisons list. (Raw article texts are NOT directly sent, preventing LLM hallucinations).
- **Prompt**: KG-grounded summarization prompt enforcing strict adherence to the structured graph/timeline facts.
- **Output**: StorySummaryResponse (headline, one_line_summary, short_summary, detailed_summary, key_facts, category)
- **Rate limiting**: Redis-based distributed throttle (8s between calls, ~7.5 RPM) to safeguard Gemini free-tier RPM limits.
- **Model chain**: gemini-2.5-flash-lite → gemini-2.5-flash → gemini-2.0-flash → OpenAI gpt-4o-mini → mock

## NER Pipeline

**Primary path**: Pre-extracted `ArticleEntity` records from the combined event+entity extraction LLM call.
These are aggregated at story generation time, eliminating redundant NER calls.

**Fallback path** (for legacy articles without pre-extracted entities):
- **Primary**: spaCy `en_core_web_sm` (12MB model)
  - Maps: GPE/LOC → LOCATION, PERSON, ORG, EVENT
- **Fallback**: Regex-based capitalized word extraction
  - Uses hardcoded org/location dictionaries
  - Default: PERSON for anything unrecognized

## Database Schema (Story-related)

- `stories` — headline, summaries, key_facts, category, location, trend_score, knowledge_graph
- `story_articles` — many-to-many link
- `story_timeline_events` — event_time, description
- `story_source_coverage` — source focus_area
- `story_differences` — unique_info, missing_info, contradictions per source
- `story_contradictions` — fact_type, description, confidence, source_attribution
- `story_entities` — entity_type (PERSON/ORG/LOCATION/EVENT), entity_value, canonical_entity_id
- `story_tags` — tag_name for search
- `story_metrics` — views, bookmarks, shares, clicks

## Database Schema (Event-Centric, New)

- `article_events` — event_type, actors, targets, objects, location, event_time, numbers, confidence, **event_fingerprint**
- `article_entities` — entity_type, entity_value, canonical_entity_id (per-article entity extraction)
- `canonical_entities` — canonical_name, entity_type, wikidata_id, aliases, metadata
