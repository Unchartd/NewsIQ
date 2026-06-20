# Current Pipeline Architecture

> Phase 1 Audit — June 2026

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
  ClusteringService
  ├── Incremental: cosine similarity ≥ 0.80 → merge into existing story
  └── Batch: HDBSCAN every 10 minutes → create new stories
       ↓
  AIService (Gemini gemini-2.5-flash → OpenAI gpt-4o-mini → mock)
  ├── Generates: headline, summaries, key_facts, timeline, differences
  └── Single LLM call per story cluster
       ↓
  NERService (spaCy en_core_web_sm → regex fallback)
  ├── Extracts: PERSON, ORG, LOCATION, EVENT
  └── Top 15 entities stored, top 5 as tags
       ↓
  PostgreSQL (stories + sub-tables)
       ↓
  Meilisearch (full-text search index)
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

- **Input**: `title + description` (content body is NOT included)
- **Model**: Gemini `text-embedding-004` → 768 dimensions
- **Fallback**: OpenAI `text-embedding-3-small` (truncated to 768) → mock
- **Storage**: Qdrant with cosine distance

## Clustering Strategy

### Incremental (Real-time)
1. After embedding, search Qdrant for neighbors with cosine ≥ 0.80
2. If a neighbor belongs to an existing story, merge the new article
3. Regenerate all story content (summary, timeline, differences, entities)

### Batch (HDBSCAN)
1. Every 10 minutes, collect all unclustered embedded articles
2. Run HDBSCAN with `min_cluster_size=2`, `min_samples=1`, `epsilon=0.35`
3. Create new Story objects for each cluster
4. Generate story content via AI + NER

## AI Synthesis

- **Prompt**: Raw article text (first 3000 chars per article) + metadata
- **Output**: StoryAIResponse (headline, summaries, key_facts, category, timeline, differences)
- **Rate limiting**: Redis-based distributed throttle (8s between calls)
- **Model chain**: gemini-2.5-flash-lite → gemini-2.5-flash → gemini-2.0-flash → OpenAI → mock

## NER Pipeline

- **Primary**: spaCy `en_core_web_sm` (12MB model)
  - Maps: GPE/LOC → LOCATION, PERSON, ORG, EVENT
- **Fallback**: Regex-based capitalized word extraction
  - Uses hardcoded org/location dictionaries
  - Default: PERSON for anything unrecognized

## Database Schema (Story-related)

- `stories` — headline, summaries, key_facts, category, location, trend_score
- `story_articles` — many-to-many link
- `story_timeline_events` — event_time, description
- `story_source_coverage` — source focus_area
- `story_differences` — unique_info, missing_info, contradictions per source
- `story_entities` — entity_type (PERSON/ORG/LOCATION/EVENT), entity_value
- `story_tags` — tag_name for search
- `story_metrics` — views, bookmarks, shares, clicks
