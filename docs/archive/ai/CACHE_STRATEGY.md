# NewsIQ Pipeline Cache Strategy

NewsIQ employs a strict, content-addressed caching architecture at the LLM pipeline level. This ensures that the platform never invokes an LLM twice for the same factual input, minimizing costs and latency without sacrificing output quality.

---

## 1. Core Architecture

Unlike traditional caching systems that rely on time-to-live (TTL) expiration to update data, the NewsIQ cache is **fully content-addressed**. Invalidation is driven entirely by changes in the input data, code version, or prompt template.

### Cache Key Formats

#### A. Stage-Level Cache Key
Used to cache intermediate outputs of individual pipeline stages (e.g. contradiction detection, source comparison):
```
stage_cache:{stage}:{model}:{prompt_version}:{pipeline_version}:{temperature}:{content_hash}
```

| Key Component | Description | Invalidation Event |
|---|---|---|
| `stage_cache` | Namespace prefix | None |
| `stage` | Pipeline stage name (e.g. `contradiction_detection`, `source_comparison`) | Code path changes |
| `model` | Exact name of the model being called (e.g. `gemini-3.1-flash-lite`) | Routing model change |
| `prompt_version` | Semver-ish prompt template version from the prompt registry | Prompt edits / bumps |
| `pipeline_version` | Overall version of the system architecture (e.g. `1.0.0`) | Pipeline logic release |
| `temperature` | The generation temperature (formatted as string) | Temperature adjustment |
| `content_hash` | SHA-256 digest of normalized, sorted input text/JSON | Article edits / new sources |

#### B. Incremental Updates Guard Key
Used to track entire story synthesis states to avoid redundant regeneration runs:
```
story_synthesis_hash:{story_id}
```
- **Value**: The composite content-addressed hash of all articles currently associated with the story.
- **TTL**: 7 days (`604,800` seconds).
- **Behavior**: If a story is updated but the set of articles has not changed (i.e. composite hash matches this cached value), execution of the synthesis pipeline is skipped entirely.

---

## 2. Invalidation Mechanics

Cache invalidation is **implicit** through key space separation. Instead of calling `DEL` operations on Redis, any change to the inputs or system configuration automatically maps the request to a new key, leading to a cache miss and subsequent regeneration.

```
Article Change → New content_hash → Key change → Cache Miss → LLM Call → Cache Set
Prompt Edit    → New prompt_version → Key change → Cache Miss → LLM Call → Cache Set
Model Upgrade  → New model          → Key change → Cache Miss → LLM Call → Cache Set
```

### Invalidation Triggers

1. **Factual Updates**:
   - When an article is edited or updated, its `content_hash` changes.
   - When new articles are added to a story, the composite hash of the story inputs changes.
2. **Prompt Tuning**:
   - Bumping the `version` of a prompt template in the [Prompt Registry](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/prompt_registry.py) immediately invalidates all cached responses for that stage.
3. **Architecture Releases**:
   - Upgrading pipeline code requires bumping the `PIPELINE_VERSION` in [config.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/core/config.py), forcing a complete cache roll across all stages.

---

## 3. TTL (Time-To-Live) Policy

TTL is **only** used as a Redis memory cleanup mechanism. It is **not** a correctness or consistency mechanism.

- **Uniform TTL**: 30 days (`2,592,000` seconds).
- **Rationale**: Since the keys are content-addressed, old entries represent stale inputs or old versions that will never be requested again. Expiring them after 30 days prevents Redis memory bloat.

---

## 4. Semantic Cache Policy

> [!CAUTION]
> **Semantic Caching is explicitly disabled for all factual extraction and synthesis stages.**
> Similar embeddings do NOT imply identical facts. For example, "15 people killed" vs "15 people injured" have a high cosine similarity (>0.98), but represent conflicting facts. Using semantic caching here would lead to catastrophic factual leakage.

Semantic caching may be considered in the future only for:
- Non-factual generation (e.g. social media headlines).
- Summary styling / formatting hints.
