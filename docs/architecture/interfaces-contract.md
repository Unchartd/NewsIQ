# NewsIQ Pipeline Component Contracts (Frozen)

This document freezes the interfaces and data contracts between components before initiating Epic 7 (Multi-Stage Story Synthesis).

---

## 1. Discovery Queue Interface
- **Responsibility**: Manages the lifecycle of unclustered articles.
- **Contract**:
  - `DiscoveryManager.enqueue_article(session: AsyncSession, article_id: UUID) -> bool`
    - Inserts a new article into `discovery_queue` with state `discovery_pending`.
    - Auto-calculates expiration time `expires_at` based on source/category settings.
    - Resolves duplicates implicitly.
  - `DiscoveryManager.check_triggers_and_group(session: AsyncSession, force: bool = False) -> None`
    - Event-driven grouping trigger: Transition state `discovery_pending` -> `discovery_ready` and sets a unique `cluster_group_id` if queue counts exceed thresholds (N=50) or age limits (X=15m).

---

## 2. Validation Interfaces (Stage A & Stage B)
- **Responsibility**: Gatekeeping checks to decide if an article merges into a story or joins the Discovery Queue.
- **Contract**:
  - **Stage A (Zero-LLM Heuristic)**:
    - Fast, deterministic check based on entity overlap and publication metadata.
    - Output outcomes: `PASS` (proceed to Stage B), `REJECT` (Stage A fail -> enqueue in Discovery), `MAYBE` (same as PASS).
  - **Stage B (Embeddings & Semantic Validation)**:
    - Cosine similarity vector validation.
    - Output outcomes: `PASS` (merge article), `MAYBE` (reflection required), `REJECT` (skip candidate).

---

## 3. Clustering Interface
- **Responsibility**: Dynamic grouping of unclustered articles.
- **Contract**:
  - `ClusteringService.run_batch_clustering(session: AsyncSession) -> int`
    - Retrieves articles in `discovery_ready` state up to batch limits.
    - Pulls vectors from Qdrant and fits them using `HDBSCAN`.
    - Promotes clusters of size >= 2 to stable Stories.
    - Marks promoted queue items as `cluster_created`.

---

## 4. Synthesis Interface (Contract for Epic 7)
- **Responsibility**: Generating the editorial layer for stories.
- **Contract**:
  - `Story` creation establishes:
    - An initial `StoryAnchor` (dataclass containing headline, category, primary entities, and centroid vector).
    - Status set to `developing`.
  - Epic 7 (Multi-Stage Story Synthesis) will:
    - Consume the list of `StoryArticles` associated with a story.
    - Execute LLM synthesis to fill `headline`, `one_line_summary`, `short_summary`, `detailed_summary`, `key_facts`.
    - Populate `StoryTimelineEvent`, `StorySourceCoverage`, `StoryDifference`, `StoryContradiction`.
    - Must **NOT** alter the article-to-story assignments or Discovery states managed by upstream services.
