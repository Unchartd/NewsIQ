# 📖 The Journey of a News Story: Inside the NewsIQ Production Pipeline

> **A Step-by-Step Execution Narrative of the Production Backend (`apps/api/app`)**  
> *From RSS Ingestion to Pre-Crawler Deduplication, Hybrid Micro-Clustering, Story Synthesis, and REST API Response.*

---

## 🌟 Introduction: The Real-World Scenario

Imagine **Apple** announces a massive **$30 billion semiconductor partnership with Broadcom** to expand U.S. chip manufacturing. 

Within minutes, news outlets across the globe—Reuters, CNBC, Bloomberg, WSJ, TechCrunch, and Nikkei—publish articles covering different angles of the story.

Below is the exact step-by-step journey of how the **NewsIQ Production Codebase** ingests, deduplicates, clusters, synthesizes, and serves this news event to end users.

---

## 📍 CHAPTER 1: The Ingestion Spark & Candidate Seeding
**Primary Service**: [`app/services/ingestion_service.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/ingestion_service.py)  
**Celery Task**: `ingest_news_task` ([`app/workers/tasks.py:168`](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/tasks.py#L168))

```text
[Celery Beat Scheduler]
       │
       ▼
ingest_news_task() (app/workers/tasks.py:168)
       │
       ▼
IngestionService.ingest_all_active_sources() (app/services/ingestion_service.py:369)
```

1. **Trigger**: Every 5 minutes, Celery Beat triggers `ingest_news_task`.
2. **RSS Ingestion**: `IngestionService` queries active news feeds from the PostgreSQL `Source` catalog table.
3. **Feed Parsing**: `feedparser` parses the Reuters RSS feed and discovers a headline:
   > *"Apple commits $30 billion to Broadcom for U.S. chipmaking push"*
4. **Metadata Scoring**: `IngestionService.calculate_discovery_score()` evaluates headline freshness, title length, domain authority, and trust score (Reuters weight: `1.0`).
5. **Story Candidate Seeding**: `IngestionService._upsert_story_candidate()` creates a `StoryCandidate` DB record in status `COLLECTING` and dispatches `dispatch_story_candidate_task` with an early-dispatch safety window.

---

## 📍 CHAPTER 2: Google Discovery & Pre-Crawler Decision Engine
**Primary Service**: [`app/ingestion/pre_crawler_engine.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/ingestion/pre_crawler_engine.py)  
**Celery Task**: `dispatch_story_candidate_task` ([`app/workers/tasks.py:1002`](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/tasks.py#L1002))

```text
Google Search Query ("Apple Broadcom 30 billion chipmaking")
       │
       ▼
GoogleRSSDiscoveryProvider.search() (10 Redirect URLs)
       │
       ▼
[PreCrawlerDecisionEngine] (Stages 06–13 Gatekeeper)
  ├── 06. Decode Google Redirect URL (googlenewsdecoder)
  ├── 07–09. Canonicalize URL & Strip Marketing Params (utm_*)
  ├── 10. Compute 64-char Hex SHA256 Hash
  ├── 11. Query Redis Bloom Filter (url_bloom_filter.exists)
  ├── 12. Query PostgreSQL Article url_hash Index
  └── 13. Evaluate PreCrawlerDecision Gate
```

1. **Discovery Search**: `dispatch_story_candidate_task` calls `GoogleRSSDiscoveryProvider.search("Apple Broadcom 30 billion chipmaking", max_results=30)`. Google returns 10 redirect URLs.
2. **URL Decoding (Stage 06)**: `GoogleRSSDiscoveryProvider.resolve_url()` decodes masked URLs:
   - Raw: `https://news.google.com/rss/articles/CBMiW...`
   - Decoded: `https://www.cnbc.com/2026/07/08/apple-broadcom-deal.html?utm_source=rssfeed&gclid=xyz123`
3. **Canonicalization & Normalization (Stages 07–09)**: `canonicalize_url()` strips tracking parameters (`utm_source`, `gclid`), lowercases, and normalizes the string to `https://cnbc.com/2026/07/08/apple-broadcom-deal.html`.
4. **SHA256 Hashing (Stage 10)**: Generates SHA256 `url_hash`: `a3b8e9f12c...`.
5. **Bloom & DB Lookup (Stages 11–12)**: `PreCrawlerDecisionEngine` queries Redis Bloom Filter and PostgreSQL `articles` table.
   - *Result for CNBC URL*: `NEW_URL` $\rightarrow$ `should_crawl = True`.
   - *Result for Duplicate Reuters URL*: `FOUND_IN_DATABASE` $\rightarrow$ `should_crawl = False` (Crawling skipped!).
6. **Crawl Gate (Stage 13)**: Out of 10 discovered URLs, 8 new URLs pass the gate and receive `CrawlTask` records.

---

## 📍 CHAPTER 3: Multi-Provider Crawling & Feature Extraction
**Primary Service**: [`app/services/extraction_manager.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/extraction_manager.py)  
**Celery Task**: `discovery_crawl_task` ([`app/workers/tasks.py:820`](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/tasks.py#L820))

```text
CrawlTask (CNBC URL)
       │
       ▼
ExtractionManager.crawl_article() (Trafilatura → Newspaper3k → Playwright)
       │
       ├── Stage 15–18: HTML OpenGraph Parsing & NFKC Text Cleaning
       ├── Stage 19–21: Gemini 768d Dense Embeddings & Redis Vector Cache
       ├── Stage 22–23: Qdrant Collection Upsert (newsiq_articles)
       ├── Stage 24–25: SpaCy/LLM NER & Wikidata Canonical Entity Linking
       └── Stage 26–28: Subject-Action-Object Event Extraction & Validation
```

1. **Multi-Provider Scraping**: `ExtractionManager.crawl_article()` downloads full HTML text using a fallback chain: Trafilatura $\rightarrow$ Newspaper3k $\rightarrow$ Playwright browser rendering.
2. **Cleaning & Fingerprinting**: Cleans boilerplate HTML, converts text to NFKC unicode format, and computes `content_hash`.
3. **Dense Vector Embeddings (768d)**: `EmbeddingService.get_embeddings()` checks Redis vector cache `embed:<content_hash>`. On cache miss, it calls Gemini Embeddings API generating 768-dimensional dense vector `[0.012, -0.045, 0.881, ...]`.
4. **Qdrant Vector Storage**: `VectorService.upsert_article()` writes vector payload to Qdrant collection `newsiq_articles`.
5. **Named Entity Recognition (NER)**: `NerServiceV2.extract_entities()` identifies entities:
   - `ORG: Apple`, `ORG: Broadcom`, `MONEY: $30 Billion`, `GPE: United States`.
6. **Entity Linking**: `EntityLinker.link_entity()` maps entities to canonical IDs:
   - `Apple` $\rightarrow$ Wikidata `Q312`
   - `Broadcom` $\rightarrow$ Wikidata `Q4972144`
7. **Event Extraction & Validation**: `EventService.extract_events()` extracts triple:
   - `Subject: Apple` $\rightarrow$ `Action: commits $30B` $\rightarrow$ `Target: Broadcom`.
   - `EventValidationService` passes Stage A (bounds check) and Stage B (grounding check) producing `ValidatedArticle`.

---

## 📍 CHAPTER 4: Stage 29 Hybrid Internal Micro-Clustering
**Primary Service**: [`app/services/micro_cluster_service.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/micro_cluster_service.py)

```text
8 Validated Articles (Batch)
       │
       ▼
MicroClusterService.partition_micro_clusters()
       │
       ├── Compute Pairwise 5-Factor PairScore Matrix:
       │     PairScore = 0.45*Embedding + 0.25*Event + 0.15*Entity + 0.10*Time + 0.05*Source
       │
       ▼
Partition into 3 Distinct Micro-Clusters:
  ├── Cluster 1 (5 Arts): Main Event ("Apple commits $30B to Broadcom")
  ├── Cluster 2 (2 Arts): Market Reaction ("Broadcom stock jumps 12%")
  └── Cluster 3 (1 Art) : Political Response ("White House praises deal")
```

1. **Batch Execution**: `MicroClusterService.partition_micro_clusters(articles)` takes the 8 crawled articles from the discovery batch.
2. **PairScore Matrix Calculation**: For every pair of articles $(A_i, A_j)$, the engine calculates a 5-factor pairwise score:
   $$\text{PairScore} = 0.45 \cdot \text{EmbeddingSim} + 0.25 \cdot \text{EventSim} + 0.15 \cdot \text{EntityOverlap} + 0.10 \cdot \text{TemporalSim} + 0.05 \cdot \text{SourceTypeSim}$$
3. **Partitioning**:
   - **Cluster 1 (5 articles)**: Main deal coverage (Reuters, CNBC, Bloomberg, WSJ, TechCrunch). PairScore = `0.94` $\ge 0.70$.
   - **Cluster 2 (2 articles)**: Stock market impact (*"Broadcom stock jumps 12%"*). PairScore = `0.88` $\ge 0.70$.
   - **Cluster 3 (1 article)**: White House statement. PairScore = `0.62` $< 0.70$ (Kept as separate cluster).
4. **Metadata Extraction**: Constructs `MicroCluster` objects containing `centroid_vector`, `representative_article`, dominant event `ECONOMIC_INVESTMENT`, and top entities `['Apple', 'Broadcom']`.

---

## 📍 CHAPTER 5: Story Candidate Search, Reflection & Judge Gate
**Primary Service**: [`app/services/clustering_service.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/clustering_service.py)  
**Agent Engine**: [`app/agents/reflection_agent.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/agents/reflection_agent.py) & [`app/agents/judge_agent.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/agents/judge_agent.py)

```text
MicroCluster 1 (Main Event)
       │
       ▼
ClusteringService.find_or_create_story() (48h DB & Qdrant Search)
       │
       ▼
ReflectionAgent.reflect_on_summary() (Audits concise cluster summary against target story)
       │
       ▼
JudgeAgent.resolve_disagreement()
       ├── IF Merge Approved  → Merge into Existing Story ID 3a4b5806-232d...
       └── IF Merge Rejected  → Create NEW Story Record
```

1. **48-Hour Search Window**: `ClusteringService` queries existing active stories in PostgreSQL and Qdrant within a 48-hour time window using Cluster 1's centroid vector.
2. **Concise Reflection Audit**: `ReflectionAgent.reflect_on_summary()` evaluates whether Cluster 1 belongs in target Story ID `3a4b5806-232d...`.
   - Prompt contains ONLY concise cluster summary: *Representative Article + Dominant Event + Dominant Entities + Centroid Metadata*. (Token cost reduced by 85%).
3. **Judge Decision Gate**: `JudgeAgent.resolve_disagreement()` approves the merge (`MERGE` decision gate).
4. **Story Assignment**: Cluster 1 is merged into Story ID `3a4b5806-232d...`. Cluster 2 (Stock market) creates a separate related story thread.

---

## 📍 CHAPTER 6: Timeline, Knowledge Graph & Multi-Tier Summary Synthesis
**Primary Service**: [`app/services/story_synthesis_orchestrator.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/story_synthesis_orchestrator.py)

```text
Merged Story (5 Articles)
       │
       ├── Stage 34: TimelineService.build_timeline()
       ├── Stage 35: KnowledgeGraphBuilder.build_graph()
       ├── Stage 36: ContradictionService.detect_contradictions()
       ├── Stage 37: SourceComparisonService.compare_sources()
       │
       ▼
StorySynthesisOrchestrator.run_summary_stage() (Gemini 2.5-Flash Multi-Tier)
       │
       ▼
ReflectionAgent.verify_summary_claims() (Zero-Hallucination Audit)
```

1. **Timeline Assembly**: `TimelineService.build_timeline()` orders all verified article events chronologically.
2. **Knowledge Graph Build**: `KnowledgeGraphBuilder.build_graph()` generates JSON nodes (`Apple`, `Broadcom`, `U.S. Manufacturing`) and edges (`COMMITTED_INVESTMENT`, `AMOUNT: $30B`).
3. **Source Coverage Matrix**: `SourceComparisonService.compare_sources()` evaluates reporting overlap (Reuters reported investment total; WSJ included white house reaction).
4. **LLM Summary Synthesis**: `StorySynthesisOrchestrator` prompts Gemini 2.5-Flash using Prompt Template `summary_v3.jinja` to generate:
   - **Executive Headline**: *"Apple Commits $30 Billion to Broadcom for U.S. Semiconductor Push"*
   - **Key Bullet Points**: Highlighting deal scale, plant locations, and market implications.
   - **AP-Style Neutral Narrative**: Balanced, factual summary text.
5. **Fact-Check Audit**: `ReflectionAgent.verify_summary_claims()` audits summary claims against original article text to ensure 100% zero-hallucination fidelity.

---

## 📍 CHAPTER 7: Atomic DB Commit, Search Indexing & REST API Response
**Primary Service**: [`app/api/v1/endpoints/stories.py`](file:///c:/Users/zakau/NewsIQ/apps/api/app/api/v1/endpoints/stories.py)

```text
Single Atomic PostgreSQL Session Commit
  (Article + Story + StoryArticle + StoryVersion + SynthesisArtifact)
       │
       ├── Stage 44: SearchService.index_story() (Meilisearch Full-Text Index)
       ├── Stage 45: CacheService.delete() (Flush stale Redis story endpoints)
       │
       ▼
REST API Client GET /api/v1/stories/3a4b5806-232d-47eb-b091-6ea41978a9b6
       │
       ▼
Pydantic StoryDetailResponse JSON Payload Rendered
```

1. **Atomic Transaction Commit**: PostgreSQL `async_session` commits all mutated records (`Article`, `Story`, `StoryArticle`, `StoryVersion`, `SynthesisArtifact`) inside a single atomic transaction block.
2. **Search Indexing**: `SearchService.index_story()` indexes story title, summary, and entities in Meilisearch for instant search retrieval.
3. **Cache Purging**: `CacheService` invalidates cached API routes `story:detail:3a4b58...`.
4. **REST API Payload**: End user requests `GET /api/v1/stories/3a4b5806-232d-47eb-b091-6ea41978a9b6`. FastAPI serializes and returns the complete `StoryDetailResponse` Pydantic JSON payload:

```json
{
  "id": "3a4b5806-232d-47eb-b091-6ea41978a9b6",
  "headline": "Apple Commits $30 Billion to Broadcom for U.S. Semiconductor Push",
  "summary": "Apple has finalized a major $30 billion multi-year agreement with Broadcom to manufacture 5G radio frequency components and cutting-edge wireless connectivity modules within the United States...",
  "status": "PUBLISHED",
  "articles_count": 5,
  "sources": ["Reuters", "CNBC", "Bloomberg", "Wall Street Journal", "TechCrunch"],
  "dominant_event": "ECONOMIC_INVESTMENT",
  "entities": [
    {"type": "ORG", "value": "Apple", "wikidata_id": "Q312"},
    {"type": "ORG", "value": "Broadcom", "wikidata_id": "Q4972144"},
    {"type": "MONEY", "value": "$30 Billion"}
  ],
  "timeline": [
    {
      "timestamp": "2026-07-08T12:00:00Z",
      "event": "Apple announces $30B Broadcom partnership",
      "source": "Reuters"
    }
  ],
  "confidence_score": 0.96,
  "updated_at": "2026-07-08T12:05:00Z"
}
```

---

## 🏁 Conclusion

From an initial RSS feed update to pre-crawler URL deduplication, multi-provider scraping, Gemini vector embeddings, 5-Factor hybrid micro-clustering, reflection auditing, multi-tier summary synthesis, and atomic database persistence—the **NewsIQ Production Codebase** turns raw, fragmented internet news into structured, actionable intelligence in under **8 seconds**.
