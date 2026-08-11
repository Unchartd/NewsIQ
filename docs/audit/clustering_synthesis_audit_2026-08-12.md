# NEWSIQ SYNTHESIS & CLUSTERING AUDIT

**Date:** 2026-08-12 · **Branch:** `main` @ `67e1750` · **Scope:** ingestion → clustering → synthesis → API
**Method:** production-code trace + git archaeology + executable proofs + **read-only diagnostics against the live local stack** (Postgres, Qdrant, Redis, Meilisearch). Nothing was mutated.

> **Revision 3 (post-production).** Read-only diagnostics were run against **production** (`161.118.170.28`, `newsiq_prod`, 15 941 articles). Results below.
>
> - **A live P0 incident was found that is not a clustering bug at all:** the Celery worker holds **9 993 of Redis's 10 000 `maxclients`**, so `is_pipeline_paused()` fail-safes to `True` and **every ingestion, embedding, extraction and clustering task has been returning immediately for ~9 days.** See [BUG-27](#bug-27--redis-connection-leak-exhausts-maxclients-and-silently-halts-the-entire-pipeline-p0-live-incident).
> - **BUG-03 is confirmed spectacularly:** all **476/476** production stories are `lifecycle_state='emerging'`, so the candidate query matches **zero** of them. Cluster sizes: 462 stories with 1 article, 14 with 2, **none with 3+**.
> - **My causality claim was wrong.** Story creation stopped **2026-07-02**, twenty-five days *before* commit `4442051`. PR #93 did not cause the outage — it removed the recovery path for one that had already begun. Corrected below.
> - Corrections carried over from Revision 2: BUG-08's clustering impact is **refuted** (Qdrant re-normalizes on write); BUG-09's cross-vendor mechanism is **refuted** (all embedding tiers are Gemini). **BUG-25 is refuted in production** (0 divergent articles; it was a local-data artifact).
>
> See [Production Diagnostic](#production-diagnostic).

> **Revision 4 (fixes applied).** Phase -1 and Phase 0 are implemented in the working tree — **not deployed**. Suite: 242 passed, 0 failed, including 8 new regression tests.
>
> | Bug | Status | Where |
> |---|---|---|
> | BUG-27 loop-bound client leak | **FIXED** | `cache_service.py`, `vector_service.py`, `tasks.py::run_async`, `queue_metrics_collector.py`, `trace.py`, `admin_service.py` |
> | BUG-18 silent pause | **FIXED** (observability) | `tasks.py::is_pipeline_paused`, `metrics.py` |
> | BUG-04 KG-node `TypeError` | **FIXED** | `clustering_service.py:1174-1200` |
> | BUG-02 (partial) entity-ID space | **FIXED** | `clustering_service.py:1276-1284` — the `story_embedding` half still needs FIX-B |
> | BUG-05 status poisoning | **FIXED** | `tasks.py::extract_events_task` |
>
> **Revision 5 (clustering restored).** Phases 1–3 are also implemented. Suite: **253 passed, 0 failed** (19 new regression tests). Verified end-to-end against real Postgres + Qdrant:
>
> ```
> eligible articles visible to batch clustering: 2
> run_batch_clustering() -> stories_created = 1        (was 0, always)
> stories in DB: 1 | story_articles rows: 2
> story ... state=emerging centroid_dim=768 norm=1.0
> RESULT: PASS
> ```
>
> | Bug | Status | Where |
> |---|---|---|
> | BUG-06 savepoint/commit conflict | **FIXED** | `clustering_service.py` — cluster persists atomically, synthesis runs after the commit and is retryable |
> | BUG-07 advisory-lock leak | **FIXED** | `run_batch_clustering` — `pg_try_advisory_lock` on a dedicated `engine.connect()` |
> | BUG-02 Stage B anchor | **FIXED** | `stories.story_embedding` (migration `d9f2e7b41c08`) + `refresh_story_centroid()` |
> | BUG-03 emerging deadlock | **FIXED** | candidate retrieval now includes `emerging`; creation sets the state explicitly |
> | BUG-01 orphaned queue | **FIXED** | eligibility reads `articles` directly via `NOT EXISTS (story_articles)`; `discovery_queue` dependency removed |
> | Observability gaps | **PARTLY FIXED** | `eligible_articles`, `clustering_candidates`, `clustering_similarity`, `story_article_count`, `CLUSTERING_INCREMENTAL` spans |
>
> **Revision 6 (hardening + cleanup complete).** Phases 4 and 5 applied. Suite: **253 passed, 0 failed**; end-to-end re-verified. **Nothing is deployed.**
>
> | Bug | Status | Note |
> |---|---|---|
> | BUG-08/09 | **FIXED** | `output_dimensionality` requested for all Gemini models + L2 normalize; OpenRouter asks the API for 768; NVIDIA/Bedrock now **refuse** rather than truncate a foreign space; `embedding_model` + `embedding_dim` recorded in the Qdrant payload |
> | BUG-11 | **FIXED** | `ReflectionUnavailableError` replaces the fabricated clean report |
> | BUG-12 | **FIXED** | Trace metadata reports the model that actually ran |
> | BUG-13 | **FIXED** | Verification model moved to `event_validation.yaml` |
> | BUG-14 | **FIXED** | Missing spaCy model logs at ERROR and appears in the startup report |
> | BUG-15 | **FIXED** | Dead score accumulator removed; `details` merged so `shared_entities` survives into traces |
> | BUG-16 | **FIXED** | Union-find fingerprint grouping; fingerprints fetched in one batch query instead of N+1 |
> | BUG-19 | **FIXED** | Synthesis cost gate fails **closed** |
> | BUG-20 | **FIXED** | Recovery task covers event extraction, uses the right columns — **and is now actually scheduled** (it never was) |
> | BUG-21 | **FIXED** | Story-First ingestion reports `story_candidates_created` |
> | BUG-23/24 | **FIXED** | Docstring corrected; stale `.pyc` for deleted modules removed |
> | Dead code | **REMOVED** | `compute_story_similarity`, `SIMILARITY_THRESHOLD`, `StoryAnchor.anchor_vector`, commented category filter |
> | Docs | **CORRECTED** | `story_clustering_synthesis_audit.md` de-listed `DiscoveryQueue`; both `Pipeline_XRay.ipynb` copies carry a banner documenting that they do not execute production code |
>
> Deliberately **not** done: BUG-17 (`micro_cluster_service` is orphaned — deleting or adopting it is a product decision, not a bug fix), BUG-22 (the 365 broad `except Exception` sites need case-by-case review), BUG-26 (Qdrant orphan reconciliation needs a deletion-path owner).

---

## Executive Summary

**Right now, nothing is running at all.** Production has been fully halted since ~2026-08-03 by a Redis connection leak (BUG-27) that trips the pipeline's fail-safe pause. That is an operational incident, fixable in minutes, and it sits *on top of* the structural problem below. Restarting the worker will resume ingestion — and will **not** produce a single new story, because the clustering defects are independent.

**Clustering is not working because nothing creates stories, and nothing can join the stories that do exist.**

Three independent, individually-fatal defects sit on the only two paths that can produce a `Story` or a `StoryArticle` row. Each one alone reduces the system to `N articles → 0 stories`. All three are present simultaneously.

| # | Defect | Effect |
|---|---|---|
| **P0-1** | `run_batch_clustering()` reads `discovery_queue WHERE state='discovery_ready'`. **No code anywhere writes to `discovery_queue`.** Its producer (`discovery_manager.py`) was deleted in PR #93 without removing the consumer. | Batch clustering — the **only** automated story creator — reads an always-empty table and returns `0` on every run. |
| **P0-2** | `add_article_to_existing_story_if_similar()` builds `StoryAnchor(centroid_vector=getattr(story, "story_embedding", None))`. **`Story` has no `story_embedding` column.** Stage B therefore computes `cosine = 0.0` for every candidate, and the entity-graph fallback compares actor *name strings* against knowledge-graph *dicts*. | Stage B returns `FAIL` for 100% of articles. The incremental merge path can never merge. Reflection and Judge are unreachable dead code. |
| **P0-3** | Batch clustering creates stories with the default `lifecycle_state='emerging'`, but candidate retrieval filters `lifecycle_state IN ('developing','monitoring','stable')`. Escaping `emerging` requires ≥3 articles, which requires merges, which require being a candidate. | Any story born with <3 articles is permanently frozen and invisible to clustering. **Production: 476/476 stories are `emerging`; the candidate query matches zero.** |
| **P0-4** | The Celery worker leaks one `aioredis` connection pool per task invocation and has saturated Redis's `maxclients`. `is_pipeline_paused()` fail-safes to `True` on cache errors, so every AI task no-ops. | **Production has ingested nothing for ~9 days.** Separate from the clustering defects; fixing it alone changes nothing about clustering. |

The failure is invisible in dashboards because the empty-input case is reported as `stage.mark_skipped("no_new_stories_created")` — indistinguishable from "there was legitimately nothing to do."

**Critically, the fixes have a mandatory order.** Fixing P0-1 first, alone, will trigger mass data damage: with stories present, every article whose top candidate has a knowledge graph hits `TypeError: unhashable type: 'dict'` inside `add_article_to_existing_story_if_similar`, which is swallowed by the per-article `except Exception` in `extract_events_task` and **overwrites an already-committed `event_extraction_status='completed'` with `'failed'`** — a terminal state that excludes the article from all future processing. **BUG-04 and BUG-05 must land before BUG-01.**

---

## Actual Runtime Pipeline

Traced from Celery Beat (`app/workers/celery_app.py:95-168`). Arrows marked ✅ execute; ❌ never execute.

```
Celery Beat
 ├── ingest_news_task           */15m   ✅
 ├── ingest_gnews_task          */30m   ✅
 ├── extract_events_task        */10m   ✅
 ├── cluster_news_task          */10m   ✅ (runs, always returns 0)
 └── discovery_grouping_task    ────    ❌ COMMENTED OUT (celery_app.py:111-116)
```

### Executed chain

```
ingest_news_task (tasks.py:169)
  └─ ingestion_service.ingest_all_active_sources
       └─ ingest_rss_source (ingestion_service.py:369)
            └─ STORY_FIRST_ENABLED=True (default)
                 └─ _ingest_rss_story_first → _upsert_story_candidate
                      writes: StoryCandidate, DiscoveryTask     ← NO Article written here
                      dispatches: dispatch_story_candidate_task (eta or early)
  └─ .delay(process_pending_embeddings_task)

dispatch_story_candidate_task (tasks.py:1002)
  └─ provider.search → rank_and_filter → resolve_url → pre_crawler_engine.evaluate_url
       writes: CrawlTask (tier-sorted)
       dispatches: discovery_crawl_task per URL

discovery_crawl_task (tasks.py:1565)
  └─ bloom filter → crawler_service.crawl_article → dup checks (url, content_hash)
       writes: Article(embedding_status='pending')          ← ONLY Article producer
  └─ calls clustering_service.add_article_to_existing_story_if_similar
       ⚠ article has no embedding yet → returns False at clustering_service.py:1104

process_pending_embeddings_task (tasks.py:268)
  └─ SELECT Article WHERE embedding_status='pending' LIMIT 50
  └─ embedding_service.get_embeddings → ai_gateway.embeddings → gemini-embedding-001
  └─ vector_service.upsert_article → Qdrant "articles" (768-dim, COSINE, point id = str(article.id))
       writes: Article.embedding_status='completed'
  └─ .delay(extract_events_task)

extract_events_task (tasks.py:432)
  └─ SELECT Article WHERE embedding_status='completed' AND event_extraction_status IN ('pending',NULL) LIMIT 20
  └─ event_service.extract_events (LLM)
       writes: ArticleEvent (primary + ≤3 secondary), ArticleEntity, entity_linker.link_entity
       writes: Article.event_extraction_status='completed'  → COMMIT
  └─ clustering_service.add_article_to_existing_story_if_similar   ← ✅ runs, ❌ always False
  └─ if batch < 20: .delay(cluster_news_task)

cluster_news_task (tasks.py:701)
  └─ Redis NX lock → clustering_service.run_batch_clustering
       └─ pg_advisory_lock(888888888)
       └─ SELECT Article JOIN DiscoveryQueue WHERE state='discovery_ready' LIMIT 200
            → 0 rows, ALWAYS                                ← ROOT CAUSE
       └─ return 0
  └─ stage.mark_skipped("no_new_stories_created")
```

### Never executed

| Component | Status |
|---|---|
| `discovery_manager.py` | **Deleted** (commit `44ffae4`). Only a stale `.pyc` remains in `__pycache__`. |
| `pipeline_coordinator.py` | **Deleted** (commit `44ffae4`). |
| `discovery_grouping_task` | **Deleted** from `tasks.py`; beat entry commented out. |
| `micro_cluster_service.py` (213 LOC) | **Orphaned.** Zero production callers. Referenced only by `tests/test_pre_crawler_and_micro_cluster.py`. |
| `vector_service.search_similar()` | **Orphaned.** Qdrant similarity search is never used for candidate retrieval. |
| `_verify_merge_with_agents` / Reflection / Judge (incremental path) | Unreachable — gated behind `ValidationOutcome.MAYBE`, which Stage B can never return. |

---

## Clustering Failure Root Cause

### ROOT CAUSE 1 — The batch clustering input table has no producer

**File:** `apps/api/app/services/clustering_service.py:1613-1630`

```python
from app.models.models import DiscoveryQueue, DiscoveryState

stmt = (
    select(Article, DiscoveryQueue)
    .join(DiscoveryQueue, Article.id == DiscoveryQueue.article_id)
    .where(DiscoveryQueue.state == DiscoveryState.READY)
    .order_by(Article.published_at.desc().nulls_last())
    .limit(_BATCH_LIMIT)
)
res = await session.execute(stmt)
rows = res.all()

if len(rows) < 1:
    logger.info("No unclustered articles to run batch clustering.")
    return 0          # ← every invocation, forever
```

Exhaustive reference search for `DiscoveryQueue` across the entire repository:

| Location | Operation |
|---|---|
| `app/models/models.py:142` | table definition |
| `app/services/clustering_service.py:1619` | **SELECT** |
| `app/services/clustering_service.py:1885` | UPDATE `state=CLUSTER_CREATED` (unreachable) |
| `app/services/admin_service.py:635` | COUNT (dashboard) |
| `pipeline_replay.py:160` | DELETE |

**There is no `INSERT`.** No code constructs `DiscoveryQueue(...)` and no code sets `state = DiscoveryState.READY`.

**Correction to my original causality claim.** I first wrote that commit `4442051` *caused* the clustering outage. Production data refutes the timing: the **last story was created 2026-07-02 16:00:06**, twenty-five days before that commit landed on 2026-07-27, while articles kept arriving (797 on 07-26, 2 736 on 07-31, 4 054 on 08-02). Story creation had already stopped for another reason — most plausibly BUG-03, since all 476 stories are `emerging` and therefore ineligible as merge candidates, which starves the incremental path and leaves batch clustering as the sole creator.

What commit `4442051` did was **remove the recovery path**: with `discovery_manager.py` deleted there is no longer any mechanism that could refill `discovery_queue` and restart story creation. It converted a stall into a permanent one. The evidence below stands; only the word "caused" was wrong.

**Git archaeology — the removal of the recovery path:**

```
commit 44ffae4  "chore: remove dead code and obsolete legacy services"
merged as 4442051  "refactor: Production Cleanup & Pipeline Alignment (#93)"  2026-07-27

 apps/api/app/services/discovery_manager.py    | 222 --------
 apps/api/app/services/pipeline_coordinator.py |  71 ------
```

The deleted `discovery_manager.py` contained the entire producer side:

- `enqueue_article()` → `session.add(DiscoveryQueue(state=PENDING, ...))`
- `check_triggers_and_group()` → `_run_hdbscan_clustering()` → `state = READY`
- `promote_clusters()` → READY → `Story` + `StoryArticle`

and `pipeline_coordinator.process_article()` was the caller:

```python
merged = await clustering_service.add_article_to_existing_story_if_similar(...)
if merged: ...
else:
    await self.discovery_manager.enqueue_article(session, article_id)   # ← DELETED
```

The consumer (`run_batch_clustering`) was left untouched. `celery_app.py:111-116` documents the amputation without fixing it:

```python
# Discovery grouping — DISABLED: app.services.pipeline_coordinator does not
# exist yet.  Re-enable once the module is implemented.
```

**Reproduction:** `SELECT count(*) FROM discovery_queue;` → `0` on any environment running code at or after `4442051`. Then `cluster_news_task.delay()` → logs `"No unclustered articles to run batch clustering."` → returns `0`.

### ROOT CAUSE 2 — Stage B is mathematically incapable of returning PASS or MAYBE

**File:** `apps/api/app/services/clustering_service.py:1174-1187`

```python
anchor = StoryAnchor(
    ...
    centroid_vector=getattr(story, "story_embedding", None),   # ← Story has no such column
    entity_graph_ids=set(story.knowledge_graph.get("nodes", []))
    if story.knowledge_graph
    else set(),
)
```

`Story` (`app/models/models.py:317-406`) defines no `story_embedding` attribute. `getattr(..., None)` therefore returns `None` unconditionally in production. In `validate_stage_b` (`event_validation_service.py:322-338`):

```python
cosine = 0.0
if anchor.centroid_vector and article_vector:      # False — centroid is None
    cosine = self._cosine_similarity(...)
```

**Executed proof** (production-shaped inputs, real config, real 768-dim article vector):

```
$ .venv/Scripts/python.exe  # see "Regression Test Plan" for full script
stage_b thresholds: {'cosine': 0.72, 'entity_overlap': 2}
centroid_vector resolved to: None
STAGE B -> FAIL | score(cosine)= 0.0 | Cosine (0.00) and entity overlap (0) too low.
              | {'cosine_similarity': 0.0, 'shared_canonical_entities': 0}
```

The article's actual embedding is passed in and completely ignored.

The second disjunct cannot rescue it either. `article_canonical_entity_ids` is built at `clustering_service.py:1265-1269` from `article_event.actors` and `.targets` — **plain name strings** (`"Narendra Modi"`), despite the variable name. `anchor.entity_graph_ids` is built from KG nodes, which are `{"id": "entity_<uuid>", ...}` dicts. The two sets are type-disjoint by construction, so `shared_entities` is always `0`.

Decision table, always:

| Branch | Condition | Value |
|---|---|---|
| PASS | `cosine >= 0.72 or shared >= 2` | `0.0 >= 0.72 or 0 >= 2` → **False** |
| MAYBE | `cosine >= 0.67 or shared >= 1` | `0.0 >= 0.67 or 0 >= 1` → **False** |
| **FAIL** | otherwise | **always taken** |

Because `MAYBE` is unreachable, `REFLECTION_THRESHOLD`, `_verify_merge_with_agents`, the Gemini/OpenAI dual-agent check and the Judge arbitration at `clustering_service.py:1363-1546` are all dead code.

### ROOT CAUSE 3 — The `emerging` lifecycle deadlock

`run_batch_clustering` creates stories without setting `lifecycle_state` (`clustering_service.py:1861-1871`), so the model default `StoryLifecycleState.EMERGING` applies. Candidate retrieval excludes it (`clustering_service.py:1125`):

```python
Story.lifecycle_state.in_(["developing", "monitoring", "stable"]),
```

`lifecycle_rules.py:95-104` gates `emerging → developing` on `articles_count >= 3`. A story created from a 1- or 2-article cluster can only reach 3 articles via incremental merge, which requires it to be a candidate, which requires it to already be past `emerging`. Given `HDBSCAN(min_cluster_size=2)` plus the outlier path that emits single-article clusters (`clustering_service.py:1684-1687`), the majority of stories would be born permanently frozen.

### Conclusion

**ROOT CAUSE PROVEN.** Three independent blockers, each sufficient on its own, verified by exhaustive reference search, git history of the removing commit, and an executed reproduction of the Stage B decision.

---

## Secondary Bugs

### BUG-04 — `set()` over knowledge-graph nodes raises `TypeError`

`clustering_service.py:1184-1186` calls `set(story.knowledge_graph.get("nodes", []))`. `StoryKnowledgeGraph.nodes` is `list[dict[str, Any]]` (`knowledge_graph.py:19`, `to_dict` at :65-67).

**Executed proof:**

```
PROOF-1 TypeError: unhashable type: 'dict'
```

Currently latent (no stories ⇒ no candidates ⇒ line never reached). **It becomes live the instant BUG-01 is fixed**, and it fails destructively — see BUG-05.

### BUG-05 — Clustering failures are misattributed and permanently poison articles

`tasks.py:573-623`. Order of operations per article:

1. `article.event_extraction_status = "completed"` → `await session.commit()` (line 573-574) — **durably committed**
2. `add_article_to_existing_story_if_similar(...)` (line 591) raises `TypeError` from BUG-04
3. `except Exception` (line 600) → `article.event_extraction_status = "failed"` → `commit()` (line 621-622)
4. `record_pipeline_failure(stage=PipelineStage.EVENT_EXTRACTION, input_payload={title, content, ...})`

Consequences: a *clustering* fault is recorded as an *event extraction* fault; a successful extraction is overwritten with `failed`; and because the selector at `tasks.py:455-462` only picks up `event_extraction_status IN ('pending', NULL)`, `failed` is **terminal** — the article is excluded from all future processing while its `ArticleEvent`/`ArticleEntity` rows remain committed.

### BUG-06 — `session.commit()` inside `begin_nested()` breaks the per-cluster savepoint

`clustering_service.py:1859` opens `async with session.begin_nested():`. Inside it, `generate_story_content` (line 1897) reaches `await session.commit()` at line 266, and `story_synthesis_orchestrator.synthesize_story` commits at `story_synthesis_service.py:933, 940, 946, 959, 965, 977, 1016, 1114`.

**Executed proof** (SQLAlchemy 2.0.50, engine-agnostic Session semantics):

```
RESULT: EXCEPTION -> InvalidRequestError : Can't operate on closed transaction inside
context manager.  Please complete the context manager before emitting further commands.
```

Impact: every cluster with ≥2 articles raises, is swallowed by `except Exception` at `clustering_service.py:1911`, and `stories_created += 1` is skipped — while the inner `commit()` has already **durably persisted a partial `Story` + `StoryArticle` + `StoryMetric`** with no synthesis and no `story_evolution` record. The task then reports `stories_created = 0` and `mark_skipped("no_new_stories_created")`. Half-created stories accumulate silently. Single-article clusters skip synthesis (line 1889) and survive, so the observable signature is "only orphan single-article stories ever appear."

Invisible to tests: `conftest.py:84-88` mocks `begin_nested()` as an `AsyncMock` whose `__aexit__` returns `None` and never raises.

### BUG-07 — Session-level advisory lock leaks across `commit()`

`run_batch_clustering` (`clustering_service.py:1592-1606`) takes `pg_advisory_lock(888888888)` — **session-scoped, not transaction-scoped**. `_ensure_all_categories` → `get_or_create_category` (line 93) then issues `await session.commit()`, at which point SQLAlchemy's `AsyncSession` returns the connection to the pool. The lock stays held on that physical connection; the final `pg_advisory_unlock` runs on whatever connection is checked out next and returns `false` **without raising**, so the `except` at line 1605 never fires.

A leaked global lock blocks every subsequent `run_batch_clustering` at `pg_advisory_lock` until the pooled connection is recycled. Use `pg_advisory_xact_lock` (as the per-story locks correctly do at lines 676 and 1418) or hold a dedicated connection. **Needs runtime confirmation against a live Postgres.**

### BUG-08 — Embedding truncated 3072→768 without re-normalization *(downgraded P1 → P3; clustering impact refuted)*

`app/ai/providers/gemini.py:205-220`:

```python
config: dict[str, Any] = {"task_type": "RETRIEVAL_DOCUMENT"}
if "embedding-2" in model_name:
    config["output_dimensionality"] = 768     # only for gemini-embedding-2
...
return raw_val[:768]                          # gemini-embedding-001 returns 3072
```

`settings.EMBEDDING_MODEL` defaults to `gemini-embedding-001` (`config.py:110`), for which `output_dimensionality` is **not** set — the API returns 3072 dimensions and the code slices the first 768 without re-normalizing, contrary to Google's documented guidance for non-3072 outputs.

**Measured — producer side** (six `newsiq:embedding:gemini-embedding-001:*` values read from live Redis, which caches the vector exactly as `embeddings()` returns it):

| dim | L2 norm |
|---|---|
| 768 | 0.592274 |
| 768 | 0.585544 |
| 768 | 0.582989 |
| 768 | 0.585856 |
| 768 | 0.583201 |
| 768 | 0.579377 |

Non-unit and non-uniform (≈2% spread) — the exact signature of truncating a unit 3072-vector, with the norm above √(768/3072)=0.5 because gemini-embedding-001 is Matryoshka-trained and front-loads energy into early dimensions.

**Measured — stored side** (ten points scrolled from the live Qdrant `articles` collection): **every vector has L2 norm exactly `1.00000`.**

**Correction.** Qdrant normalizes on write when `distance=Cosine`. Both clustering consumers read vectors *back from Qdrant* — `clustering_service.py:1650` (batch/HDBSCAN) and `:1249` (Stage B) — so both receive unit vectors. My earlier claim that this makes `HDBSCAN(metric="euclidean", cluster_selection_epsilon=0.35)` meaningless is **wrong and is withdrawn.** On unit vectors, euclidean `0.35` ⇔ cosine ≈ `0.939` — a coherent, if very strict, threshold.

What remains real: 75% of the model's representational capacity is discarded, and any future consumer of `embedding_service.get_embedding()` that does *not* round-trip through Qdrant will silently receive non-unit vectors. A quality and robustness defect, not a clustering blocker.

### BUG-09 — Mixed embedding spaces in one collection with no provenance *(downgraded P1 → P2; mechanism corrected)*

**Correction.** I claimed OpenRouter/NVIDIA/Bedrock failover writes foreign vectors into the shared collection. That is **wrong** — `app/ai/config.py:271-290` routes **all three** embedding tiers to Gemini:

```python
"embedding": {
    "primary":      {"provider": "gemini", "model": settings.EMBEDDING_MODEL or "gemini-embedding-001"},
    "fallback":     {"provider": "gemini", "model": "gemini-embedding-2"},
    "lastFallback": {"provider": "gemini", "model": "gemini-embedding-001"},
}
```

The `raw[:768]` calls in `openrouter.py:160`, `nvidia.py:161` and `bedrock.py:164` are unreachable for the embedding capability — dead code, not an active hazard. This matches commit `232841d` ("Gemini API exclusive routing").

The defect survives in weaker form. The `fallback` tier is **`gemini-embedding-2`**, which `gemini.py:208` requests at a *native* 768 dimensions — a different embedding space from a 3072-vector truncated to 768. On a primary-tier failure, vectors from two incompatible spaces land in the same collection, and the Qdrant payload (`tasks.py:353-360`) records only title/url/source_id/published_at, so contaminated points cannot be identified or selectively re-embedded afterward.

### BUG-10 — `get_embeddings` can silently misalign vectors to articles

`embedding_service.py:152`:

```python
return [r for r in results if r is not None]
```

The caller indexes positionally: `vectors[i]` against `pending_articles[i]` (`tasks.py:347-351`). Any `None` in `results` shortens the list and shifts **every subsequent article onto the wrong vector** — silent, permanent cross-contamination of the vector index. No current input reaches a `None`, so this is latent, but the failure mode is data corruption with no error.

### BUG-11 — Reflection agent fails open

`reflection_agent.py:93-101`: on any parse failure the function returns

```python
ReflectionSchema(has_hallucinations=False, invented_facts=[], contradicts_graph=False, ...)
```

A malformed or empty LLM response becomes an affirmative clean bill of health for the fact-check stage.

### BUG-12 — Fabricated model/provider metadata in clustering traces

`clustering_service.py:873-890` hardcodes `metadata["gemini"]["model"] = "gemini-2.5-flash"`, `metadata["judge"]["model"] = "gpt-4o"`, `metadata["judge"]["provider"] = "openai"`. In reality both agents use `get_default_model()` → `settings.SUMMARIZATION_MODEL` (default `gemini-2.5-flash-lite`, `base_agent.py:14-17`). Every persisted clustering trace records a model that was not used.

### BUG-13 — OpenAI verification agent bypasses the gateway

`clustering_service.py:943-948` constructs `Agent(model=OpenAIChat(id="gpt-4o-mini"))` directly, bypassing `capability_router`, quota handling, `QuotaExhaustedError` propagation and cost accounting. This contradicts commits `a6e147e`/`232841d` ("Gemini API exclusive routing").

### BUG-14 — spaCy model missing ⇒ degraded entity extraction

`event_validation_service.py:17-21` logs `spaCy installed but en_core_web_sm not found` and falls back to `{w.lower() for w in text.split() if w.istitle() and len(w) > 3}`. Confirmed reproduced locally. This crude heuristic feeds **both** the Stage A entity/location scores **and** the SQL candidate-retrieval entity filter at `clustering_service.py:1139-1147`, so it silently narrows recall.

### BUG-15 — Dead score accumulation and lost trace detail in Stage A

`event_validation_service.py:243-265`: `score` is accumulated across five factors and then **discarded** — `final_score` is recomputed from scratch at line 250. Line 246 reassigns `trust_score = max(0.0, 100.0 - ((tier-1)*20.0))` *after* the original value was already added to the dead `score`. The `details` dict is also rebuilt at line 258, dropping the `shared_entities` key that was set at line 167, so persisted traces lose the single most diagnostic field.

Additionally, the candidate query does not eager-load `Article.source`, so the `insp.unloaded` guard at line 229 makes `tier` default to `5` for essentially every article — publisher trust contributes a constant 2.0 points.

### BUG-16 — Non-transitive fingerprint pre-grouping

`clustering_service.py:1807-1845`: when a cluster's fingerprints match an existing group, only the *first* matching `target_idx` is used. If a cluster bridges two previously-registered groups, the second group is never merged, yet its fingerprints are re-pointed at `target_idx` — leaving `fingerprint_map` inconsistent with the actual cluster membership.

### BUG-27 — Redis connection leak exhausts `maxclients` and silently halts the entire pipeline *(P0, live incident)*

**Measured in production:**

```
established TCP connections, redis container   : 10000   ← maxclients default, saturated
established TCP connections, celery-worker     :  9993   ← 99.9% held by one container
established TCP connections, processing-api    :    10
established TCP connections, user-api          :     8

$ redis-cli PING
ERR max number of clients reached
```

**Mechanism.** `CacheService` keys its Redis clients by event-loop identity (`cache_service.py:59-77`):

```python
self._clients: dict[int, aioredis.Redis | None] = {}

@property
def _redis(self):
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if loop_id not in self._clients:
        client = _make_redis_client(settings.REDIS_URL)   # a NEW connection pool
        self._clients[loop_id] = client
    return self._clients[loop_id]
```

`run_async()` (`tasks.py:77-150`) creates a **fresh event loop for every Celery task invocation** and closes it in `finally` — but nothing ever calls `aclose()` on the Redis client or evicts the dict entry. Each task therefore strands a live connection pool. The dict also grows without bound, and because CPython recycles memory addresses, a new loop can collide with a freed loop's `id()` and be handed a client bound to a dead loop — a second defect in the same six lines.

**Arithmetic.** Task invocations in the last 24 h: 11 456 + 5 740 + 5 736 + 5 734 + 572 + 572 + 384 + 384 + 192 ≈ **30 770**. Against a 10 000 default `maxclients`, saturation is reached within hours of every worker start.

**Blast radius — this is the silent-failure pattern the audit predicted, observed live.** Once Redis refuses connections, `cache_service.ping()` fails and `is_pipeline_paused()` (`tasks.py:153-166`) returns `True` by design (BUG-18). Every AI-bearing task then returns immediately. Last 24 h:

```
Pipeline is paused. Skipping event extraction      143
Pipeline is paused. Skipping batch clustering      143
Pipeline is paused. Skipping RSS news ingestion     96
Pipeline is paused. Skipping GNews API ingestion    48
Cache is unreachable                               430
```

Zero quota-cooldown events were logged, so this is **not** the intended quota pause — it is the fail-safe firing on an infrastructure fault. Consistent with the data: articles stop at **2026-08-03**, and **11 304 of 15 941 articles (71%) are stranded at `embedding_status='pending'`**.

Nothing alerts. The tasks report `succeeded`, the logs carry only `warning`, and the dashboard's own metrics task is itself failing to write to Redis.

`VectorService._clients` (`vector_service.py:32-53`) uses the identical loop-keyed pattern for Qdrant and leaks the same way; I under-rated it as a "minor leak" in Revision 1.

**Fix:** give `CacheService` a single module-level client created from a `ConnectionPool` that is safe across loops (or create-and-`aclose()` per task), cap `max_connections` on the pool, raise `maxclients`, and alert on `redis_connected_clients / maxclients > 0.8`. **Do not** simply restart the worker and consider it resolved — that resets the counter and the leak refills it within hours.

### BUG-25 — Processing status diverges from produced artifacts, with no reconciliation *(REFUTED in production)*

> **Refuted.** In production this query returns **0**, not 12. The divergence exists only in the local development database and is an artifact of a partial manual wipe, not a code defect. Retained below for the local environment only; **not a production bug and not on the fix list.**

```sql
SELECT count(*) FROM articles a
WHERE a.event_extraction_status = 'completed'
  AND NOT EXISTS (SELECT 1 FROM article_events e WHERE e.article_id = a.id);
--  12   ← 100% of articles in the database
```

All 12 articles are marked `event_extraction_status='completed'` yet **zero** `ArticleEvent` rows exist (`article_events`, `article_entities`, `story_entities`, `story_timeline_events` are all empty).

Whatever produced this state, the system cannot recover from it. `extract_events_task:455-462` selects only `event_extraction_status IN ('pending', NULL)`, so these articles are never re-extracted; and every clustering signal keys off `ArticleEvent` (`art_evt_map` at `clustering_service.py:1696-1703`, `_compute_event_similarity_direct`, `compute_story_similarity`). The articles are permanently unclusterable while reporting as fully processed.

There is no invariant check anywhere that a `completed` status corresponds to actual persisted artifacts, and no repair task for status/artifact divergence — only `recover_stuck_embeddings_task`, which handles the narrower `processing` case and does so on the wrong column (BUG-20).

### BUG-26 — Qdrant is never reconciled against Postgres *(new, confirmed live)*

```
postgres articles       :  12
qdrant points           : 101
pg articles WITH vector :  12   ← all article IDs resolve correctly
pg articles NO vector   :   0
orphan qdrant points    :  89   ← 88% of the collection
```

Point IDs match perfectly for live articles — confirming there is no ID-mismatch bug — but 89 vectors belong to articles that no longer exist. `delete_article()` (`vector_service.py:187-196`) exists and has no callers on any article-deletion path. Orphans inflate the HNSW index, and because batch clustering fetches by explicit ID list they do not corrupt results today; they would matter immediately if `search_similar()` were ever wired into candidate retrieval as the architecture docs describe.

### BUG-17 — Micro-clustering algorithm defects (orphaned code)

`micro_cluster_service.py`:
- `t_sim = 0.95` (line 93) — "Temporal Proximity Decay" is a hardcoded constant; publication times are never read.
- `st_sim` ∈ {0.8, 1.0} (line 96) — always ≥0.8.
- Combined, these contribute a constant floor of `0.10×0.95 + 0.05×0.8 = 0.135` to every pair score regardless of content.
- `confidence = 0.94` (line 198) and `dominant_event = "ECONOMIC_EVENT"` (line 179) are hardcoded.
- **Greedy, order-dependent, non-transitive partitioning** (lines 148-161): `articles[j]` is compared only to the seed `articles[i]`, never to the growing cluster, and `visited[j] = True` is irreversible. Input order alone determines whether the output is `N → N` or `N → 1`.

Weights do sum correctly to 1.00 (`config.py:239-243`).

### Verified NOT buggy

- **Judge decision mapping is correct.** `JudgeSchema.final_decision: bool` means "same_event resolved"; `clustering_service.py:1015` returns it directly as the merge decision. No inversion.
- **Embedding dimensions are internally consistent** at 768 across `EMBEDDING_DIM`, Qdrant collection creation, and all providers.
- **Qdrant point IDs match**: written as `str(article_id)` (`vector_service.py:152`), read as `str(article_id)` (`clustering_service.py:1247, 1645`). No ID mismatch.
- **Distance metric is COSINE** and is never treated as a distance in scoring code.
- **PairScore weights sum to exactly 1.00.**

---

## Data Flow Problems

- **Story-First ingestion produces zero `Article` rows.** With `STORY_FIRST_ENABLED=True` (default), `ingest_rss_source` returns a count of `StoryCandidate`s, but `ingest_news_task` labels it `stage.metric("articles_ingested", total_new)` (`tasks.py:204`). The dashboard reports StoryCandidates as articles.
- **Premature clustering call.** `discovery_crawl_task:1843` invokes `add_article_to_existing_story_if_similar` on an article with `embedding_status='pending'`; it returns `False` at `clustering_service.py:1104` before doing anything. Pure waste, and it makes the log line "Failed to run downstream match coordinator" misleading.
- **No terminal sink for unmatched articles.** After the incremental merge returns `False`, nothing routes the article anywhere. The log at `clustering_service.py:1241` still claims *"Routing to Discovery Queue"* — the routing was deleted; only the log survives.
- **Secondary events carry no fingerprint** (`tasks.py:527-541`), so fingerprint pre-grouping sees only primary events.

---

## Async / Celery Problems

- **BUG-06** (savepoint/commit conflict) — see above. P0.
- **BUG-07** (advisory lock leak across commit) — see above. P1.
- **Redis-down fails the whole pipeline closed, silently.** `is_pipeline_paused` (`tasks.py:153-166`) returns `True` on any cache error, and every AI-bearing task begins with `if await is_pipeline_paused(): return`. A Redis outage halts ingestion, embedding, extraction and clustering with only `logger.warning`. Combined with `_pause_pipeline_for_quota_cooldown` (a 1-hour TTL flag), there is no metric or alert distinguishing "paused" from "healthy and idle."
- **`run_async` disposal is correct.** `engine.sync_engine.dispose(close=False)` per task plus a fresh event loop correctly handles prefork + asyncpg. `VectorService` keys clients by `id(loop)` (`vector_service.py:42-53`) — also correct, though the dict grows unboundedly across loops within a long-lived worker (minor leak).
- **`session` is passed across the crawl network boundary.** `discovery_crawl_task` commits before the HTTP crawl (lines 1642-1647) and re-fetches after — this pattern is correct and was fixed in `43eb684`.
- **Recovery task uses a mismatched column.** `recover_stuck_embeddings_task` (`tasks.py:882-889`) filters `Article.crawled_at < cutoff`, but "stuck in processing" is a function of when embedding *started*, not when the article was crawled. Articles crawled recently but stuck in `processing` are never recovered; there is no equivalent recovery for `event_extraction_status='processing'` at all.

---

## Database Problems

- `discovery_queue` is a live table with a live consumer and no producer (**BUG-01**).
- Partial commits inside a broken savepoint (**BUG-06**) leave orphan `Story`/`StoryArticle`/`StoryMetric` rows.
- **N+1 in fingerprint pre-grouping**: `clustering_service.py:1816-1822` issues one `SELECT` per article inside a nested loop over clusters, on a batch of up to 200.
- **N+1 in `update_story_incrementally`**: `clustering_service.py:620-624` re-queries `Source` per article inside a loop, immediately after an identical batch fetch at line 527-534.
- **N+1 in `compute_story_similarity`**: `clustering_service.py:834-841` queries `ArticleEntity` once per story article.
- **Timestamp handling is consistent** (naive UTC via `_now()` / `datetime.now(UTC).replace(tzinfo=None)`), and `validate_stage_a` defensively strips tzinfo. One exception: `Story.lifecycle_changed_at`, `last_discovery_at`, `last_significant_update_at` are `DateTime(timezone=True)` while every other timestamp is naive — `lifecycle_rules.py:70-83` compensates by re-attaching UTC, but the schema inconsistency is a latent trap.
- The 72-hour candidate window (`clustering_service.py:1111`) filters on `Story.updated_at`, not `first_seen_at` or article publication time — an actively-updated story never ages out, which is probably intended but is undocumented.

---

## Qdrant Problems

Verified live against `GET /collections/articles` and a 500-point scroll.

| Aspect | Finding |
|---|---|
| Collection name | `articles` — consistent everywhere |
| Dimensions | **Live: `size: 768`** — matches `EMBEDDING_DIM`; auto-recreate on mismatch (`vector_service.py:87-99`) |
| Distance | **Live: `Cosine`** — correct, never inverted |
| Point IDs | **Live: 12/12 article IDs resolve exactly.** No ID mismatch. |
| Stored vector norms | **Live: exactly `1.00000`** — Qdrant normalizes on write for Cosine |
| **Similarity search** | **Never used for clustering.** `search_similar()` has zero production callers. Candidate retrieval is a plain Postgres query. |
| Vector quality | BUG-08 impact **refuted** by measurement; BUG-09 reduced to intra-Gemini space mixing |
| Score threshold | `search_similar` defaults to `0.70` — unused |
| **Deleted/stale vectors** | **Live: 89 orphans of 101 points (88%)** — see BUG-26. No reconciliation exists. |
| Indexing | `indexed_vectors_count: 0` — below the 20 000 `indexing_threshold`, so search is brute-force. Fine at this scale. |
| Failure handling | `search_similar` returns `[]` on exception (`vector_service.py:248-250`); `retrieve_vectors` returns `{}` (`:269-271`) — both indistinguishable from "no matches" |
| Docstring | Claims "Dimensions: 3072" (`vector_service.py:4`) — stale, contradicted by the live collection |

---

## Embedding Problems

Covered by BUG-08, BUG-09, BUG-10. Additional notes:

- **Cache keys are model-aware but not dimension- or version-aware.** `_cache_key` (`embedding_service.py:30-34`) hashes `model + sha256(text)` with a 30-day TTL. Fixing BUG-08 (adding `output_dimensionality=768`) will **not** invalidate the cache — every article embedded in the last 30 days will keep returning its old truncated vector. **A cache flush of `newsiq:embedding:*` is mandatory as part of that fix.**
- Empty text yields `[0.0] * 768` (lines 102, 119) — a zero vector. Cosine against a zero vector is `0.0` (guarded), but it is upserted into Qdrant as a legitimate point.
- Per-item cache `get` and `set` are issued in a Python loop (lines 100-115, 141-150) rather than `MGET`/pipelined — 50 round-trips per batch.

---

## Micro-Clustering Problems

The requested "internal micro-clustering" stage **does not exist in the production pipeline.** `micro_cluster_service.py` is orphaned (BUG-17), and the two things that do partition articles are:

1. **HDBSCAN** (`clustering_service.py:1668-1690`) — `min_cluster_size=2, min_samples=1, metric="euclidean", cluster_selection_epsilon=0.35` on the poisoned vectors of BUG-08. Outliers (`label == -1`) become single-article clusters.
2. **Pairwise event-similarity splitting** (`clustering_service.py:1720-1805`) — a greedy sub-cluster assignment with the same non-transitivity flaw as BUG-17: `art` is compared against sub-clusters in insertion order and joins the first that clears the bar.

`_compute_event_similarity_direct` (`clustering_service.py:739-796`) sums to at most **0.90**, with a comment stating "Entity overlap (10%) is added externally." The batch path honours that (`combined_sim = avg_sim + 0.10 * avg_entity_sim`, line 1760), but the thresholds are applied inconsistently:

| Path | Threshold | Comment |
|---|---|---|
| Batch split | `>= 0.90` auto-merge, `>= 0.70` → agents | Auto-merge requires a near-perfect score on a 0.0–1.0 scale where location defaults to 0.5 and time to 0.5 when data is missing |
| `SIMILARITY_THRESHOLD` (module constant, line 53) | `0.80` | **Never referenced anywhere** |
| Agent fallback (line 1087) | `>= 0.80` | Applies only when Gemini is entirely unavailable |

Missing-value handling inflates scores: absent location scores `0.5` and absent event time scores `0.5` (lines 770, 783), so two articles with no location and no time start at `0.20 × 0.5 + 0.10 × 0.5 = 0.15` for free.

---

## Reflection / Judge Problems

- **Both are unreachable in the incremental path** — gated behind `ValidationOutcome.MAYBE`, which BUG-02 makes impossible.
- **The naming is misleading.** The clustering "Reflection Agent" is `cluster_verification_agent.verify_cluster_decision`. `reflection_agent.py` is a *summary* fact-checker used by the synthesis path. The architecture docs conflate them.
- **Judge is invoked narrowly**: only when `high_stakes AND settings.OPENAI_API_KEY AND gemini_ver is not None AND gemini.same_event != openai.same_event` (`clustering_service.py:934, 992-993`). Correct in principle.
- **Judge mapping is correct** — no inversion (verified).
- **Failure behaviour is fail-toward-Gemini**: judge timeout (line 1032), judge error (line 1048), OpenAI unavailable (line 1062) all `return gemini_ver.same_event`. Reasonable, and metered via `newsiq_reflection_fallback_total`.
- **Total Gemini failure falls back to `similarity_score >= 0.80`** (line 1087) — a silent switch from LLM adjudication to a bare threshold, with no `MAYBE`/abstain option.
- **Confidence is captured but never used.** `metadata["gemini"]["confidence"]` is recorded (line 926) and then ignored; only the boolean `same_event` drives the decision.
- **BUG-11** (reflection fails open) and **BUG-12** (fabricated model metadata) apply.

---

## Synthesis Problems

`StorySynthesisOrchestrator.synthesize_story` (`story_synthesis_service.py:809-1114`) is well-structured, but it **cannot currently run** — it is only reachable from `generate_story_content` (batch clustering, dead) and `merge_article_into_existing_story` (incremental, dead).

| Stage | Input | Process | Output | Persistence | Failure mode |
|---|---|---|---|---|---|
| 0. Budget gate | `story_id` | Redis daily cost | bool | trace row | `except` → `return True` (fail-open, `:234`) |
| 0b. Updates guard | article hash | Redis compare | bool | — | `except` → warn, proceed |
| 1. Knowledge graph | DTO articles/events/entities | deterministic | `kg_dict` | artifact | — |
| 2. Contradiction | DTOs + source map | cache → LLM | payload | artifact | swallowed |
| 3. Source comparison | DTOs + contradictions | cache → LLM | payload | artifact | swallowed |
| 4. Timeline | DTO events | deterministic | payload | artifact | — |
| 5. Summary | KG + contras + timeline | LLM | payload | artifact | swallowed |
| 6. Feedback | summary text | `evaluate_story_quality` | action | trace | — |
| 5b. Regenerate | corrections | LLM (once) | payload | artifact | — |
| 7. Publisher | all payloads | writes story fields | Story + sub-tables | commit | — |

Issues:

- **Nine `session.commit()` calls** (lines 933-1114) inside what callers treat as an atomic unit — the direct cause of BUG-06 and of partial persistence on any mid-pipeline failure.
- **`return` on empty articles is indistinguishable from success.** Lines 846-863 return `None` on "story not found" and "no articles" alike; callers cannot tell.
- **Budget gate fails open** (`:219-236`): a Redis error returns `True` (proceed), so cost controls silently disappear during a Redis incident.
- **`story.category` lazy-load hazard** in `generate_story_content:262-263` — `story.category.slug` is accessed on a `Story` created moments earlier without `selectinload`; safe only because `category_id` is `None` at that point.
- **`compute_trending_score` commits** (`clustering_service.py:1973`) — another commit inside the savepoint.

---

## Observability Gaps

The failure survived because the telemetry is structurally incapable of showing it.

| Missing signal | Where it should go |
|---|---|
| Eligible-article count for batch clustering (`len(rows)`) | `clustering_service.py:1626` → `stage.metric("eligible_articles", ...)` |
| Distinction between "queue empty" and "nothing to do" | `tasks.py:759-760` — `mark_skipped("no_new_stories_created")` conflates them. Needs a distinct `input_starved` reason. |
| `discovery_queue` depth by state as a gauge | Prometheus; `newsiq_discovery_queue_size` exists but has **no setter** since `discovery_manager` was deleted |
| Candidate-story count per article | `clustering_service.py:1152` |
| Stage A / Stage B outcome distribution per article | Counters exist (`newsiq_stage_a_pass_total`, `newsiq_stage_b_pass_total`) but the incremental path never opens a `StageSpan` |
| `CLUSTERING_INCREMENTAL` spans | The enum member exists (`trace.py:158`) and is **never used**. The path writes `PipelineTraceModel(stage="article_clustering")` — a magic string outside the enum. |
| Qdrant vector-retrieval hit/miss counts | `clustering_service.py:1650-1658` |
| HDBSCAN label distribution / noise ratio | `clustering_service.py:1679` |
| Cosine / pair-score histograms | Needed to detect BUG-02 (a histogram pinned at exactly 0.0 would have flagged it on day one) |
| Embedding model + dimension per Qdrant point | `tasks.py:353-360` payload |
| Story lifecycle-state distribution | Would have exposed the `emerging` pile-up (BUG-03) |
| Token usage / cost per clustering agent call | `metadata` dict records latency but not tokens or cost |
| Prompt version on clustering agents | Recorded for synthesis stages, absent for `cluster_verification`/`judge` |

The admin dashboard actively reinforces the illusion: `admin_service.py:635-638` counts `discovery_queue` rows in `PENDING/GROUPING/READY` as the backlog metric — permanently `0`, which reads as "queue healthy."

---

## Documentation Mismatches

| Claim | Source | Reality |
|---|---|---|
| "CS→DB: INSERT DiscoveryQueue (state = READY)" for unmerged articles | `docs/architecture/story_clustering_synthesis_audit.md:129` | **DOCUMENTED, NOT IMPLEMENTED.** `clustering_service.py:1588` returns `False` and writes nothing. |
| "`discovery_manager.py` verifies if an article_id is already linked… before enqueuing" | same, `:248` | **File deleted** in `44ffae4`. |
| "Queue Expiration… TTL (default: 72 hours)" | same, `:249` | No expiration code exists. |
| "Worker→DB: Enqueue article in DiscoveryQueue (state = PENDING)" | `docs/architecture/deduplication_extraction_audit.md:144` | Same — producer deleted. |
| Stage 23 "Vector Search Verify" | `docs/NewsIQ_Full_Pipeline_Architecture.md` | `search_similar()` has no callers. **DOCUMENTED, IMPLEMENTED, NOT EXECUTED.** |
| Stage 29 "Hybrid Micro-Clustering Engine", Stage 30 "Micro-Cluster Story Search" | same | `micro_cluster_service` has no production callers. **IMPLEMENTED, NOT EXECUTED.** |
| Stage 21 "Gemini Embeddings 768d" | same | The API returns 3072 and the code truncates without normalizing (BUG-08). |
| "Dimensions: 3072 (gemini-embedding-001)" | `vector_service.py:4` (docstring) | Collection is created at 768. Docstring contradicts its own module. |
| Reflection/Judge run per micro-cluster | `docs/NewsIQ_Full_Pipeline_Architecture.md` Stages 31-32 | They run per candidate *story*, and only in a branch that is currently unreachable. |

### Pipeline_XRay.ipynb is not an X-ray of production

The notebook (103 cells, `notebooks/Pipeline_XRay.ipynb`) does **not** exercise the production clustering code. Reference counts across all code cells:

```
clustering_service                        0
run_batch_clustering                      0
add_article_to_existing_story_if_similar  0
micro_cluster_service                     0
DiscoveryQueue                            0
```

Instead it:

- **Reimplements** `compute_pair_score` inline (cell 60) rather than calling `micro_cluster_service`.
- **Fabricates the ranking stage** (cell 62): `entity_score = 0.85`, `title_score = 0.80`, `vector_score = 0.88`, `time_decay = 0.95` are hardcoded constants — every candidate story receives an identical composite score of `0.8455`. The "Story Ranking" stage the notebook demonstrates does not compute anything.
- **Calls a signature that no longer exists** (cell 66): `resolve_disagreement(task_description=..., agent_outputs=[...])`. The real signature (`judge_agent.py:38-45`) is `(task_description, provider_a_name, provider_a_output, provider_b_name, provider_b_output, context)`. This raises `TypeError` — the cell cannot have been executed against current code. It then reads `judge_decision.winner_id`, which is not a field of `JudgeSchema`.
- **Creates `Story` rows directly** (cell 68), bypassing clustering entirely.

The notebook validates a pipeline that does not exist. It should not be used as evidence of production behaviour.

---

## Dead / Legacy Code

| Item | Location | Note |
|---|---|---|
| `micro_cluster_service.py` (213 LOC) | `app/services/` | No production callers |
| `vector_service.search_similar()` | `vector_service.py:200-250` | No callers |
| `SIMILARITY_THRESHOLD = 0.80` | `clustering_service.py:53` | Never referenced |
| `DiscoveryQueue` model + `DiscoveryState` enum | `models.py:35-41, 142-164` | Producer deleted; either restore or remove |
| Stage A `score` accumulator | `event_validation_service.py:141-243` | Computed then discarded |
| `StoryAnchor.anchor_vector` | `event_validation_service.py:69` | Declared, never set or read |
| Commented-out category filter | `clustering_service.py:1133-1136` | Dead comment block |
| `discovery_manager.cpython-31{2,3}.pyc` | `app/services/__pycache__/` | Stale artifacts of a deleted module — actively misleading during investigation |
| `newsiq_discovery_queue_size` gauge | `app/core/metrics.py` | No setter remains |
| `compute_story_similarity` | `clustering_service.py:798-850` | No callers found |

---

## Bug Severity Matrix

| ID | Sev | File | Function | Line | Symptom | Root cause | Impact |
|---|---|---|---|---|---|---|---|
| **BUG-01** | **P0** | `clustering_service.py` | `_run_batch_clustering_locked` | 1618-1630 | Every run returns 0 | `discovery_queue` producer deleted in `44ffae4`, consumer kept | No stories ever created |
| **BUG-02** | **P0** | `clustering_service.py` | `add_article_to_existing_story_if_similar` | 1183 | Stage B always FAIL | `Story.story_embedding` does not exist → `centroid_vector=None` → `cosine=0.0` | No article ever merges |
| **BUG-03** | **P1** | `clustering_service.py` | `_run_batch_clustering_locked` / candidate query | 1125, 1861 | Stories invisible to merge | Created as `emerging`; filter excludes `emerging`; exit needs ≥3 articles | Stories <3 articles frozen forever |
| **BUG-04** | **P1** | `clustering_service.py` | `add_article_to_existing_story_if_similar` | 1184 | `TypeError: unhashable type: 'dict'` | `set()` over `list[dict]` KG nodes | Latent; fatal once BUG-01 is fixed |
| **BUG-05** | **P1** | `tasks.py` | `extract_events_task` | 600-623 | Articles stuck at `failed` | Clustering exception caught by event-extraction handler; overwrites committed `completed` | Permanent article loss + misattributed failures |
| **BUG-06** | **P0** | `clustering_service.py` / `story_synthesis_service.py` | `_run_batch_clustering_locked` / `synthesize_story` | 1859 / 933 | `InvalidRequestError`, partial commits | `session.commit()` inside `begin_nested()` | Orphan half-created stories; `stories_created` under-reported |
| **BUG-07** | **P1** | `clustering_service.py` | `run_batch_clustering` | 1592-1606 | Clustering hangs after first run | Session-scoped advisory lock leaked across `commit()` | Global clustering deadlock |
| **BUG-08** | ~~P1~~ **P3** | `ai/providers/gemini.py` | `embeddings` | 205-220 | Producer emits norm-0.58 vectors (measured) | `output_dimensionality` set only for `embedding-2`; no renormalize after `raw[:768]` | **Clustering impact refuted** — Qdrant re-normalizes on write. 75% capacity loss + hazard for non-Qdrant consumers |
| **BUG-09** | ~~P1~~ **P2** | `ai/config.py` | embedding route | 271-290 | Two embedding spaces, one collection | `fallback` tier is `gemini-embedding-2` (native 768) vs primary truncated-from-3072; no model in payload | **Cross-vendor mechanism refuted** — all tiers are Gemini. Intra-Gemini failover still mixes spaces unidentifiably |
| **BUG-10** | **P1** | `embedding_service.py` | `get_embeddings` | 152 | Wrong vector on wrong article | `filter(None)` shifts positional alignment | Latent silent data corruption |
| **BUG-11** | **P1** | `agents/reflection_agent.py` | `reflect_on_summary` | 93-101 | Bad LLM output ⇒ "no hallucinations" | Fail-open fallback schema | Fact-check silently disabled |
| **BUG-12** | **P3** | `clustering_service.py` | `_verify_merge_with_agents` | 873-890 | Traces name unused models | Hardcoded metadata | Untrustworthy audit trail |
| **BUG-13** | **P2** | `clustering_service.py` | `_verify_merge_with_agents` | 943-948 | Ungoverned OpenAI spend | Direct `OpenAIChat`, bypasses gateway | No quota/cost control |
| **BUG-14** | **P2** | `event_validation_service.py` | module import | 17-21 | Degraded entity extraction | `en_core_web_sm` not installed | Stage A + SQL entity filter lose recall |
| **BUG-15** | **P3** | `event_validation_service.py` | `validate_stage_a` | 243-265 | Dead code; traces lose `shared_entities` | `score` discarded, `details` rebuilt, `trust_score` reassigned | Undiagnosable Stage A decisions |
| **BUG-16** | **P2** | `clustering_service.py` | `_run_batch_clustering_locked` | 1807-1845 | Clusters that should merge don't | Non-transitive fingerprint grouping | Duplicate stories for identical events |
| **BUG-17** | **P2** | `micro_cluster_service.py` | `partition_micro_clusters` | 93, 148-161 | `N→N` or `N→1` | Constant `t_sim`; greedy order-dependent seeding | Orphaned today; blocking if adopted |
| **BUG-18** | **P2** | `tasks.py` | `is_pipeline_paused` | 153-166 | Whole pipeline silently off | Redis error ⇒ fail-closed, warn-only | Undetected total outage |
| **BUG-19** | **P2** | `story_synthesis_service.py` | `check_budget_limit` | 219-236 | Cost controls vanish | Redis error ⇒ `return True` | Unbounded LLM spend during Redis incident |
| **BUG-20** | **P3** | `tasks.py` | `recover_stuck_embeddings_task` | 882-889 | Stuck articles not recovered | Filters `crawled_at` instead of an embedding-start timestamp; no equivalent for `event_extraction_status` | Permanent `processing` limbo |
| **BUG-21** | **P3** | `tasks.py` | `ingest_news_task` | 204 | `articles_ingested` counts StoryCandidates | Story-First return value mislabelled | Misleading dashboard |
| **BUG-22** | **P3** | multiple | — | see table | 365 `except Exception`, 45 → `pass`, 21 → `return None`, 22 → `return []` | Broad swallowing | Failures indistinguishable from empty results |
| **BUG-23** | **P4** | `vector_service.py` | module docstring | 4 | Says 3072 dims | Stale doc | Confusion |
| **BUG-24** | **P4** | `app/services/__pycache__/` | — | — | `discovery_manager.pyc` for a deleted module | Untracked build artifact | Misleads investigators |
| **BUG-27** | **P0** | `cache_service.py` (+ `vector_service.py`) | `CacheService._redis` | 59-77 | Redis at 10 000/10 000 clients; worker holds 9 993 (measured) | New `aioredis` pool per event loop; `run_async` makes one loop per task; never closed or evicted | **Entire pipeline halted ~9 days.** 71% of articles stranded at `pending` |
| ~~BUG-25~~ | — | — | — | — | ~~status/artifact divergence~~ | **REFUTED in production** (query returns 0) | Local-data artifact only |
| **BUG-26** | **P3** | `vector_service.py` | `delete_article` | 187-196 | 89 of 101 Qdrant points are orphans (measured) | Function has no callers on any deletion path | Index bloat now; wrong results if `search_similar` is ever wired in |

---

## Recommended Fixes

### P0/P1 — must fix immediately

---

**FIX-A — Restore the batch-clustering feed (BUG-01)**

- **File / function:** `apps/api/app/services/clustering_service.py::add_article_to_existing_story_if_similar` (add an enqueue on the `return False` paths at lines 1155, 1244, 1588) + a new `app/services/discovery_manager.py` + `app/workers/tasks.py::discovery_grouping_task` + `celery_app.py` beat entry.
- **Change:** Reinstate the producer. Recover `discovery_manager.py` verbatim from `git show 44ffae4^:apps/api/app/services/discovery_manager.py` as the starting point (it already implements `enqueue_article` with content-hash dedup, `process_expirations`, and `check_triggers_and_group`). Wire `enqueue_article` into every "did not merge" exit of `add_article_to_existing_story_if_similar`. Restore the beat entry at `celery_app.py:113-116`. **Do not** restore `promote_clusters` — it duplicates `run_batch_clustering` and would create a second, competing story creator.
- **Why it fixes it:** `run_batch_clustering`'s `SELECT` gains rows for the first time since 2026-07-27.
- **Alternative (smaller blast radius):** change `_run_batch_clustering_locked` to select articles directly — `embedding_status='completed' AND event_extraction_status='completed' AND NOT EXISTS (SELECT 1 FROM story_articles WHERE article_id = articles.id) AND created_at > now() - interval '72 hours'` — and drop `discovery_queue` entirely. This removes a whole subsystem rather than resurrecting one. **Recommended** unless the queue's retry/expiry semantics are genuinely needed.
- **Test:** integration test against a real Postgres asserting that an article which fails incremental merge becomes visible to `run_batch_clustering` and yields a `Story`.
- **Risk:** Medium — this is what unblocks the pipeline, so the first production run will process the entire accumulated backlog. Cap `_BATCH_LIMIT` and run once manually with `dry_run` logging before enabling the beat schedule.
- **Rollback:** revert the enqueue call sites; the beat entry stays commented.

---

**FIX-B — Give `StoryAnchor` a real centroid (BUG-02)**

- **File / function:** `apps/api/app/models/models.py::Story` (+ Alembic migration), `apps/api/app/services/clustering_service.py::add_article_to_existing_story_if_similar:1183`.
- **Change:** Add `story_embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)` (or a dedicated Qdrant `stories` collection, which scales better). Populate it in `merge_article_into_existing_story` and at story creation as the mean of member article vectors. Replace `getattr(story, "story_embedding", None)` with a direct attribute access so a future rename fails loudly instead of silently returning `None`.
- **Why it fixes it:** `validate_stage_b` gains a non-`None` `centroid_vector`, so the article's embedding is finally compared against something.
- **Test:** unit test asserting `validate_stage_b` returns `PASS` for `cosine >= 0.72` and `FAIL` for a known-dissimilar pair — using a **real `Story` ORM instance**, not a `MagicMock`. The existing tests (`test_multi_signal_clustering.py:146, 216`) assign `story.story_embedding` to a mock, which is exactly why this bug shipped.
- **Risk:** Low. Additive schema change.
- **Rollback:** revert the migration; Stage B returns to its current (broken) behaviour.

---

**FIX-C — Fix the entity-graph comparison (BUG-04 + Stage B second disjunct)**

- **File / function:** `apps/api/app/services/clustering_service.py:1184-1186` and `:1265-1269`.
- **Change:** Build both sides from the same identifier space. Replace `set(story.knowledge_graph.get("nodes", []))` with a query over `StoryEntity.canonical_entity_id`, and replace the actor/target name strings with `ArticleEntity.canonical_entity_id` for the article. Add a type assertion so a future shape change raises rather than silently intersecting to zero.
- **Why it fixes it:** eliminates the `TypeError` **and** makes `shared_canonical_entities` a real signal instead of a constant `0`.
- **Test:** `test_stage_b_entity_overlap` with two articles sharing two canonical entities → `PASS`; property test asserting `set(...)` is never applied to KG nodes.
- **Risk:** Low.
- **Ordering:** **must land before FIX-A.**

---

**FIX-D — Stop clustering failures from poisoning articles (BUG-05)**

- **File / function:** `apps/api/app/workers/tasks.py::extract_events_task:588-623`.
- **Change:** Wrap the `add_article_to_existing_story_if_similar` call in its own `try/except`, logging under a `clustering_incremental` stage and **never** touching `article.event_extraction_status`. The extraction result is already committed at line 574 and must stay `completed`.
- **Why it fixes it:** prevents a downstream fault from marking upstream work as failed and from moving articles into a terminal state.
- **Test:** regression test — patch `add_article_to_existing_story_if_similar` to raise; assert `event_extraction_status == "completed"` afterwards and that the recorded failure stage is clustering, not event extraction.
- **Risk:** Very low.
- **Ordering:** **must land before FIX-A.**

---

**FIX-E — Remove commits from inside the savepoint (BUG-06)**

- **File / function:** `apps/api/app/services/clustering_service.py::generate_story_content:265-268`, `::compute_trending_score:1973`, `apps/api/app/services/story_synthesis_service.py::synthesize_story` (all nine `session.commit()` calls).
- **Change:** Replace every internal `commit()` with `flush()` and let the outermost caller own the transaction boundary. `generate_story_content` already has a `commit: bool` parameter — thread it through and pass `commit=False` from `run_batch_clustering:1897`. Synthesis stages that genuinely need to release the connection during long LLM calls should take their own short-lived session rather than committing the caller's.
- **Why it fixes it:** the savepoint stays open for the duration of the cluster, restoring per-cluster atomicity and eliminating half-created stories.
- **Test:** integration test against real Postgres — force a failure in `run_publisher_stage` and assert **zero** `Story` rows exist afterwards. Also update `conftest.py:84-88` so `begin_nested()` is backed by a real session in clustering tests; the current `AsyncMock` cannot catch this class of bug.
- **Risk:** Medium — longer-held transactions increase lock contention. Mitigate by keeping `_BATCH_LIMIT` modest and monitoring transaction duration.
- **Rollback:** revert; behaviour returns to partial commits.

---

**FIX-F — Make new stories reachable (BUG-03)**

- **File / function:** `apps/api/app/services/clustering_service.py:1861-1871` and `:1125`.
- **Change:** Set `lifecycle_state=StoryLifecycleState.EMERGING` explicitly **and** add `"emerging"` to the candidate-retrieval filter. A story that cannot accept articles cannot grow into the state that lets it accept articles.
- **Why it fixes it:** breaks the circular dependency.
- **Test:** create a 1-article story, run incremental merge with a matching article, assert the merge succeeds and the story later transitions to `developing`.
- **Risk:** Low — widens candidate recall slightly; Stage A/B still gate the merge.

---

> **FIX-G was here.** Following the live measurements it is **no longer a P0/P1 item and is not on the critical path.** Qdrant re-normalizes on write, so clustering already receives unit vectors; the mandatory full re-embed I originally called for is not required for correctness. It moves to P2/P3 below.

---

**FIX-H — Fix positional vector alignment (BUG-10)**

- **File / function:** `apps/api/app/services/embedding_service.py::get_embeddings:152`.
- **Change:** Return `list[list[float] | None]` preserving length, and have `process_pending_embeddings_task` mark `None` entries as `failed` explicitly. Never silently compact a positionally-indexed list.
- **Test:** assert `len(get_embeddings(texts)) == len(texts)` unconditionally.
- **Risk:** Very low.

---

**FIX-I — Use a transaction-scoped global clustering lock (BUG-07)**

- **File / function:** `apps/api/app/services/clustering_service.py::run_batch_clustering:1592-1606`.
- **Change:** `pg_advisory_lock` → `pg_advisory_xact_lock`, or acquire the lock on a dedicated connection held for the method's lifetime. Note that `pg_advisory_xact_lock` releases at the first `commit()`, so this fix is only correct **after** FIX-E collapses the method to a single transaction.
- **Test:** integration test — run `run_batch_clustering` twice sequentially; the second must not block.
- **Risk:** Low, but strictly ordered after FIX-E.

---

**FIX-J — Make the reflection agent fail closed (BUG-11)**

- **File / function:** `apps/api/app/agents/reflection_agent.py:93-101`.
- **Change:** Raise on unparseable output, or return an explicit `verdict="unavailable"` state that callers must handle. Never synthesize `has_hallucinations=False`.
- **Test:** patch the agent to return malformed JSON; assert an exception or an explicit unavailable verdict, not a clean report.
- **Risk:** Low — may surface previously-hidden LLM failures, which is the point.

---

### P2 — before production rollout

| Fix | File / function | Change | Risk |
|---|---|---|---|
| BUG-08/09 (ex-FIX-G) | `ai/providers/gemini.py:205-220`; `tasks.py:353-360` | Set `output_dimensionality=768` for **all** Gemini embedding models and L2-normalize after truncation; add `embedding_model` to the Qdrant payload so mixed-space points are identifiable. Re-embed is *optional* (quality, not correctness) — if done, flush `newsiq:embedding:*` first, since the cache key is model-aware but not dimension-aware. | Medium |
| BUG-25 | `tasks.py` + new reconciliation task | Add an invariant check that `event_extraction_status='completed'` implies ≥1 `ArticleEvent`; add a repair task that resets divergent rows to `pending`. Today all 12 articles are silently unprocessable. | Low |
| BUG-13 | `clustering_service.py:943-948` | Route the OpenAI verification agent through `ai_gateway`/`capability_router` for quota and cost governance | Low |
| BUG-14 | `pyproject.toml` / Dockerfile | Install `en_core_web_sm`; **fail startup** if `nlp is None` rather than degrading silently | Low |
| BUG-16 | `clustering_service.py:1807-1845` | Replace first-match grouping with union-find over fingerprints | Low |
| BUG-17 | `micro_cluster_service.py` | Either delete, or fix `t_sim`, replace greedy seeding with connected components, and wire it in | Medium |
| BUG-18 | `tasks.py:153-166` | Emit a Prometheus gauge for pause state and alert on it; distinguish "explicitly paused" from "Redis unreachable" | Low |
| BUG-19 | `story_synthesis_service.py:219-236` | Fail **closed** on Redis error in the cost gate | Low |
| Thresholds | `clustering_service.py:53, 1763, 1765, 1087` | Move `SIMILARITY_THRESHOLD`, `0.90`, `0.70`, `0.80` into `event_validation.yaml` alongside the Stage A/B thresholds | Low |
| Missing-value inflation | `clustering_service.py:770, 783` | Missing location/time should reduce confidence, not default to `0.5` | Medium |

### P3/P4 — cleanup

| Fix | Item |
|---|---|
| BUG-12 | Remove hardcoded model/provider strings from `_verify_merge_with_agents` metadata; read from `get_default_model()` |
| BUG-15 | Delete the dead `score` accumulator; merge rather than rebuild `details` so `shared_entities` survives; eager-load `Article.source` in the candidate query so `trust_tier` is real |
| BUG-20 | Add an `embedding_started_at` column; add recovery for `event_extraction_status='processing'` |
| BUG-21 | Rename the Story-First ingestion metric to `story_candidates_created` |
| BUG-22 | Audit the 45 `except: pass` sites; require every swallow to increment a labelled counter |
| BUG-23 | Fix the `vector_service.py` docstring (768, not 3072) |
| BUG-24 | Add `__pycache__/` to `.gitignore` scope and purge stale `.pyc` files |
| Dead code | Remove `search_similar`, `compute_story_similarity`, `StoryAnchor.anchor_vector`, the commented category filter, and either restore or drop `DiscoveryQueue`/`newsiq_discovery_queue_size` |
| Docs | Correct `story_clustering_synthesis_audit.md:129, 248-249` and `deduplication_extraction_audit.md:144`; mark Stages 23/29/30 in `NewsIQ_Full_Pipeline_Architecture.md` as not-executed |
| Notebook | Rewrite `Pipeline_XRay.ipynb` to **call** production services, or clearly label it a design mock-up. Cell 66 currently cannot execute against the real `resolve_disagreement` signature. |

---

## Regression Test Plan

The existing suite passes while production is fully broken. That is the deepest finding in this audit, and the test strategy must change before the fixes land.

**Why the tests missed all three P0s:**

- `conftest.py:73-90` — `mock_db_session` is an `AsyncMock`. `session.execute` returns canned rows regardless of the statement, so the `DiscoveryQueue` join is never exercised against a real schema (misses BUG-01). `begin_nested()` returns an `AsyncMock` whose `__aexit__` returns `None` and never raises (misses BUG-06).
- `test_multi_signal_clustering.py:146, 216` — assigns `story.story_embedding = [0.1] * 128` to a mock object. Python permits attribute assignment on mocks, so the test proves Stage B works on a field the production model does not have (misses BUG-02).
- `test_clustering.py:137` — patches out `synthesize_story`, `_index_and_invalidate`, `entity_linker.link_entity` and `get_or_create_category`, then asserts `stories_created == 1`. Production returns `0`.

### Required tests

**Tier 1 — real-database integration (new; this tier does not currently exist)**

| Test | Asserts |
|---|---|
| `test_batch_clustering_finds_eligible_articles` | Against real Postgres: N articles satisfying the eligibility predicate ⇒ `run_batch_clustering` returns `> 0`. Fails today. |
| `test_batch_clustering_cluster_is_atomic` | Force a failure in `run_publisher_stage`; assert **zero** `Story` rows persist. Catches BUG-06. |
| `test_advisory_lock_released_between_runs` | Two sequential `run_batch_clustering` calls; the second must not block. Catches BUG-07. |
| `test_story_reachable_after_creation` | A 1-article story is returned by the candidate query. Catches BUG-03. |
| `test_end_to_end_two_articles_form_a_story` | Seed two near-identical articles → embed (mock gateway) → extract events (mock LLM) → cluster → assert one `Story` with two `StoryArticle` rows. **This is the test whose absence allowed the regression.** |

**Tier 2 — schema and contract**

| Test | Asserts |
|---|---|
| `test_story_model_has_story_embedding` | `hasattr(Story, "story_embedding")`. Catches BUG-02 at import time. |
| `test_no_orphaned_table_consumers` | Every model read by a service has at least one writer. Catches the whole class of BUG-01. |
| `test_kg_nodes_are_dicts` | `set(kg["nodes"])` raises; assert the production code path does not attempt it. Catches BUG-04. |
| `test_embedding_dimension_and_norm` | Every provider returns `len == 768` and `abs(norm - 1.0) < 1e-6`. Catches BUG-08/09. |
| `test_get_embeddings_preserves_length` | `len(out) == len(texts)` unconditionally. Catches BUG-10. |

**Tier 3 — behavioural unit tests using real ORM instances (not mocks)**

| Test | Asserts |
|---|---|
| `test_stage_b_pass_on_high_cosine` | Real `Story` + populated centroid, cosine `0.85` ⇒ `PASS` |
| `test_stage_b_fail_on_low_cosine` | cosine `0.30`, no shared entities ⇒ `FAIL` |
| `test_stage_b_maybe_triggers_reflection` | cosine `0.69` ⇒ `MAYBE` and `_verify_merge_with_agents` is invoked |
| `test_judge_true_means_merge` | `final_decision=True` ⇒ merge. Locks in the currently-correct mapping. |
| `test_clustering_exception_does_not_fail_extraction` | Patch merge to raise; assert `event_extraction_status == "completed"`. Catches BUG-05. |
| `test_reflection_parse_failure_raises` | Malformed LLM output ⇒ no fabricated clean report. Catches BUG-11. |
| `test_micro_cluster_partition_is_order_invariant` | Shuffle input; assert stable partitions. Catches BUG-17. |

**Executable proofs used in this audit** (retain as regression tests):

```python
# Proof 1 — BUG-04
kg = {"nodes": [{"id": "entity_1"}, {"id": "source_2"}], "edges": []}
set(kg["nodes"])          # TypeError: unhashable type: 'dict'

# Proof 2 — BUG-02
from app.services.event_validation_service import EventValidationService, StoryAnchor
class FakeStory: pass
anchor = StoryAnchor(
    story_id="s1", headline="Modi meets Putin in Moscow",
    first_seen_at=datetime(2026, 8, 12), last_updated_at=datetime(2026, 8, 12),
    primary_entities={"modi", "putin"}, top_locations={"moscow"},
    category="world", event_type=None,
    centroid_vector=getattr(FakeStory(), "story_embedding", None),   # -> None
    entity_graph_ids=set(),
)
d = EventValidationService().validate_stage_b(article, anchor, [0.5] * 768,
                                              {"Narendra Modi", "Vladimir Putin"})
assert d.outcome == "FAIL" and d.score == 0.0      # passes today — the bug

# Proof 3 — BUG-06
with Session(engine) as s:
    with s.begin_nested():
        s.execute(text("SELECT 1"))
        s.commit()
        s.execute(text("SELECT 2"))
# InvalidRequestError: Can't operate on closed transaction inside context manager.
```

---

## Implementation Order

The order is not negotiable — BUG-04 and BUG-05 are latent only because BUG-01 keeps the code path unreachable. Fixing BUG-01 first would convert a dormant `TypeError` into mass article corruption.

```
Phase -1 — LIVE INCIDENT (do this first; unrelated to clustering)
  0a. BUG-27  fix CacheService/_VectorService loop-keyed client leak:
              module-level client on a bounded ConnectionPool, or aclose() per task
  0b. raise Redis maxclients; alert on connected_clients/maxclients > 0.8
  0c. alert on is_pipeline_paused()==True for > 15 min, distinguishing
      "explicitly paused" from "cache unreachable" (BUG-18)
  0d. THEN restart the worker to clear the 10 000 stranded connections
      → a restart WITHOUT 0a refills the leak within hours
      → this restores ingestion; it creates ZERO stories. That is expected.

Phase 0 — Safety net (no behaviour change)
  1. FIX-D   BUG-05  isolate clustering exceptions from event-extraction status
  2. FIX-C   BUG-04  fix KG-node set() + entity-id comparison
  3. Tier-1 harness: real-Postgres integration fixtures; drop mock_db_session for clustering
     → deploy, confirm no change in behaviour

Phase 1 — Correct the transaction model
  4. FIX-E   BUG-06  remove commits from inside begin_nested()
  5. FIX-I   BUG-07  pg_advisory_lock -> pg_advisory_xact_lock  (requires FIX-E)
     → deploy, confirm no orphan Story rows

Phase 2 — Make the data processable again
  6. FIX-H   BUG-10  preserve positional alignment in get_embeddings
  7. BUG-25  reset the 12 articles whose 'completed' status has no ArticleEvent rows
             back to 'pending', and add the invariant check that prevents recurrence
     → without this there is no event data for clustering to act on

Phase 3 — Restore clustering  ← nothing before this point changes the outcome
  8. FIX-B   BUG-02  add Story.story_embedding + migration + population
  9. FIX-F   BUG-03  include 'emerging' in candidate retrieval
 10. FIX-A   BUG-01  restore the batch-clustering feed (prefer the direct-select variant)
     → run cluster_news_task manually once with a small _BATCH_LIMIT before enabling beat

Phase 4 — Hardening
 11. FIX-J   BUG-11  reflection fails closed
 12. BUG-08/09 (ex-FIX-G), BUG-13, BUG-14, BUG-16, BUG-18, BUG-19; externalize thresholds
 13. Observability: eligible_articles, candidate counts, cosine histograms,
     CLUSTERING_INCREMENTAL spans, lifecycle-state distribution

Phase 5 — Cleanup
 14. BUG-12, BUG-15, BUG-20..24, BUG-26; delete dead code; correct docs and the X-Ray notebook
```

**Note on the 72-hour window.** The one story in the database was last updated 16 days ago, so it is currently outside the candidate window at `clustering_service.py:1111` regardless of every other fix. Fresh ingestion is required to exercise the clustering path end-to-end after Phase 3 — do not read "0 candidates" on stale data as a failed fix.

**Gate between Phase 3 and Phase 4:** the cosine histogram must show a real distribution. If it is still pinned at `0.0`, FIX-B did not take effect and no threshold should be touched.

---

## Production Diagnostic

Executed 2026-08-12 against `ubuntu@161.118.170.28` (`newsiq-vni`, up 42 days) and database `newsiq_prod`. Read-only: `SELECT`s, `docker logs`, `/proc/net/tcp` counts. **Nothing was restarted, written, or reconfigured.** Deployed image verified to contain the audited code (`clustering_service.py:1183` `story_embedding` getattr; `:1619-1621` DiscoveryQueue select; `discovery_manager.py` and `pipeline_coordinator.py` absent).

### Census

| Table | Rows | Table | Rows |
|---|---|---|---|
| `articles` | **15 941** | `discovery_queue` | **0** |
| `stories` | **476** | `article_events` | 8 139 |
| `story_articles` | **490** | `story_candidates` | 5 571 |
| `story_versions` | **0** | `crawl_tasks` | 24 332 |
| `pipeline_traces` | **0** | | |

### The outcome distribution — the signature of the failure

| Articles in story | Number of stories |
|---|---|
| 1 | **462** |
| 2 | 14 |
| 3+ | **0** |

**15 520 of 15 941 articles (97.4%) belong to no story at all.** Mean story size is 1.03 articles. The maximum observed size of 2 is exactly `HDBSCAN(min_cluster_size=2)`'s output — no story has ever grown after creation.

| `lifecycle_state` | count |
|---|---|
| `emerging` | **476** |

**Every single story is `emerging`.** The candidate query filters `IN ('developing','monitoring','stable')`, so it matches **zero of 476**. This is BUG-03, confirmed at 100% incidence, and it explains `pipeline_traces = 0`: traces are only written after candidates are found, so with zero candidates the incremental path has never recorded a decision across 15 941 articles. Stage A, Stage B, Reflection and Judge have **never executed in production**.

### The two production queries, run verbatim

```sql
SELECT count(*) FROM articles a JOIN discovery_queue dq ON a.id=dq.article_id
WHERE dq.state='discovery_ready';                                    --  0
SELECT count(*) FROM stories WHERE lifecycle_state IN
  ('developing','monitoring','stable')
  AND updated_at >= (now() AT TIME ZONE 'utc') - interval '72 hours'; --  0
SELECT count(*) FROM information_schema.columns
WHERE table_name='stories' AND column_name='story_embedding';        --  0
```

### Timeline — the outage predates the commit I blamed

| Date | Stories created | Articles created |
|---|---|---|
| 2026-06-27 → 07-02 | **476 (all of them)** | — |
| 2026-07-16 / 07-17 | 0 | 978 / 902 |
| 2026-07-26 / 07-27 | 0 | 797 / 304 |
| 2026-07-31 → 08-03 | 0 | 2 736 / 2 681 / 4 054 / 1 942 |
| 2026-08-04 → today | 0 | **0** |

Two distinct events: story creation stopped **2026-07-02**; ingestion stopped **2026-08-03** (BUG-27). Between them, production ingested roughly 14 000 articles and created zero stories — **41 days of silent clustering failure**, followed by 9 days of total pipeline silence.

### Findings status after the production diagnostic

| Finding | Status | Evidence |
|---|---|---|
| BUG-27 Redis leak / pipeline halted | **CONFIRMED — live P0** | 9 993/10 000 clients on worker; 430 `Cache is unreachable`; 143 clustering skips in 24 h |
| BUG-03 emerging deadlock | **CONFIRMED at 100%** | 476/476 stories `emerging`; candidate query returns 0 |
| BUG-01 queue never populated | **CONFIRMED** | `discovery_queue` = 0; production query returns 0 |
| BUG-02 Stage B always FAIL | **CONFIRMED** | no `story_embedding` column in `newsiq_prod` |
| Clustering produces only singletons | **CONFIRMED** | 462×1, 14×2, 0×3+; 97.4% orphan rate |
| Stage A/B/Reflection/Judge ever ran | **NEVER** | `pipeline_traces` = 0 across 15 941 articles |
| Synthesis ever versioned a story | **NEVER** | `story_versions` = 0 |
| BUG-05 status poisoning | **PARTIALLY FIRED** | 44 articles `failed`, 53 stuck `processing` |
| BUG-08 / BUG-09 | **CORRECTED** | see Revision 2 |
| BUG-25 status/artifact divergence | **REFUTED** | production query returns 0 |
| BUG-06 savepoint conflict | **UNPROVEN in prod** | batch clustering never reaches cluster creation, so it cannot fire yet |
| BUG-07 advisory-lock leak | **UNPROVEN** | needs an instrumented run; `cluster_news_task` currently no-ops at the pause gate |

---

## Local Environment Diagnostic

Executed 2026-08-12 against the local stack (`newsiq-postgres`, `newsiq-qdrant`, `newsiq-redis`, `newsiq-meilisearch`, all healthy). Read-only: `SELECT`s, Qdrant `GET`/`scroll`, Redis `GET`. No writes. Schema at `alembic_version = 7578d7e9c7dc`.

### Database census

| Table | Rows | | Table | Rows |
|---|---|---|---|---|
| `discovery_queue` | **0** | | `article_events` | **0** |
| `articles` | 12 | | `article_entities` | **0** |
| `stories` | 1 | | `story_entities` | **0** |
| `story_articles` | 12 | | `story_timeline_events` | **0** |
| `story_candidates` | 0 | | `story_versions` | 1 |
| `crawl_tasks` | 0 | | `pipeline_traces` | **0** |

### The two production queries, run verbatim

```sql
-- clustering_service._run_batch_clustering_locked:1618-1624
SELECT count(*) FROM articles a JOIN discovery_queue dq ON a.id = dq.article_id
WHERE dq.state = 'discovery_ready';
--  0     ← BUG-01 CONFIRMED

-- add_article_to_existing_story_if_similar:1121-1131
SELECT count(*) FROM stories s
WHERE s.lifecycle_state IN ('developing','monitoring','stable')
  AND s.updated_at >= (now() AT TIME ZONE 'utc') - interval '72 hours';
--  0     ← no candidates for the incremental path either
```

Isolating which predicate excludes the single story:

| `lifecycle_state` | within 72h | total |
|---|---|---|
| `developing` | **0** | 1 |

The story passes the lifecycle filter but fails the recency window — `updated_at = 2026-07-26 18:29:52`, **16 days old**. Both clustering paths are simultaneously starved, for different reasons.

### Schema confirmation of BUG-02

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='stories' AND column_name LIKE '%embed%';
--  (0 rows)     ← Story.story_embedding does not exist in the live schema
```

`StoryAnchor.centroid_vector` is therefore `None` for every candidate in this database, exactly as the local reproduction predicted.

### Findings status after the diagnostic

| Finding | Status | Evidence |
|---|---|---|
| BUG-01 queue never populated | **CONFIRMED** | `discovery_queue` = 0 rows; production query returns 0 |
| BUG-02 Stage B always FAIL | **CONFIRMED** | no `story_embedding` column in live schema |
| BUG-03 emerging deadlock | **CONSISTENT, not exercised** | only story is `developing`; no `emerging` stories exist to observe |
| BUG-04 KG-node `TypeError` | **CONFIRMED (latent)** | executed reproduction; `knowledge_graph IS NULL` on the one story, so not yet triggered |
| BUG-05 status poisoning | **NOT YET FIRED** | no `failed` articles — consistent with BUG-04 being unreachable so far |
| BUG-06 savepoint conflict | **CONFIRMED (code)** | executed reproduction; not observable here because batch clustering never reaches cluster creation |
| BUG-07 advisory-lock leak | **UNPROVEN** | `pg_locks` shows no advisory locks at rest; requires an instrumented `cluster_news_task` run under a live worker |
| BUG-08 truncation | **CORRECTED** | producer norms 0.579–0.592 (confirmed); stored norms 1.00000 → clustering impact **refuted** |
| BUG-09 mixed spaces | **CORRECTED** | all embedding tiers are Gemini → cross-vendor claim **refuted**; intra-Gemini mixing stands |
| BUG-25 status/artifact divergence | **CONFIRMED (new)** | 12/12 articles `completed` with 0 `ArticleEvent` rows |
| BUG-26 Qdrant orphans | **CONFIRMED (new)** | 89 of 101 points have no corresponding article |

### Still outstanding

- **BUG-07** is the only finding resting primarily on inference. Confirming it needs a running Celery worker: query `pg_locks WHERE locktype='advisory'` immediately after a `cluster_news_task` invocation and check whether `objid` for `888888888` remains granted.
- **BUG-06** cannot fire in this environment because clustering never reaches cluster creation. It will become observable the moment BUG-01 is fixed — which is why FIX-E is sequenced in Phase 1, before FIX-A.
- The database contains no worker-generated activity (`pipeline_traces` = 0, `crawl_tasks` = 0, `story_candidates` = 0), so no runtime log evidence of any stage was available. All timestamps cluster on 2026-07-26 — the day before the breaking commit `4442051` landed.
