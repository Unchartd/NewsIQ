# NewsIQ System Pipeline Audit Report

This report presents a comprehensive, production-grade technical audit of the entire **NewsIQ** system—from Feed Ingestion, Crawling, and Extraction, through Named Entity Recognition (NER), Entity Linking, and Event Extraction, to Story Clustering, Validation, and Story Synthesis.

---

## Executive Summary & Priority Roadmap

We audited the backend services, Celery tasks, database transactions, Redis caching/batching, Qdrant indexing, and LLM gateway interactions. The findings are prioritized below based on operational risk, cost impact, performance bottlenecks, and system resilience:

| Priority | Category | Issue | Impact | File Reference |
| :--- | :--- | :--- | :--- | :--- |
| **P0** | **Bug / Race Condition** | [Tavily Batch Ingestion Deadlock](#p0-tavily-batch-ingestion-deadlock) | Crawl jobs hang, timing out to expensive individual requests | [extraction_manager.py:L215-332](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/extraction_manager.py#L215-L332) |
| **P0** | **Architecture / Perf** | [Transaction Bloat during LLM Calls](#p0-database-transaction-bloat-during-sequential-llm-calls) | Connection pool starvation; locks held for 10-20 seconds | [story_synthesis_service.py:L811-1000](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/story_synthesis_service.py#L811-L1000) |
| **P1** | **Resource Leak** | [Qdrant Connection Leak](#p1-qdrant-connection-pool-leaks-across-event-loops) | Memory & file descriptor leaks from unclosed Qdrant clients | [vector_service.py:L30-53](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/vector_service.py#L30-L53) |
| **P1** | **Performance** | [Socket Churn from Ephemeral HTTP Clients](#p1-socket-churn-from-recreating-httpx-clients) | Slow HTTP requests; socket exhaustion | [entity_linker.py:L331](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/entity_linker.py#L331), [crawler_service.py:L71](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/crawler_service.py#L71) |
| **P1** | **Bug / Resiliency** | [Tenacity `reraise=False` Gotcha](#p1-tenacity-reraisefalse-exception-swallowing-gotcha) | Potential downstream type/attribute errors on query failures | [entity_linker.py:L338-343](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/entity_linker.py#L338-L343) |
| **P2** | **Observability** | [Today's Token Usage Mismatch](#p2-todays-token-usage-and-cost-aggregation-mismatch) | Dashboard metrics discrepancies between local server and UTC | [admin_service.py:L684-694](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/admin_service.py#L684-L694) |
| **P3** | **Tech Debt** | [Deprecated `datetime.utcnow()` Usage](#p3-deprecated-datetimeutcnow-usage) | Code maintenance issues under Python 3.12+ | [gnews_service.py:L558](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/gnews_service.py#L558), [tasks.py:L849](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/tasks.py#L849) |

---

## Detailed Findings

### P0: Tavily Batch Ingestion Deadlock
- **Location**: [extraction_manager.py:L215-332](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/extraction_manager.py#L215-L332)
- **Description**: The system implements a Redis-backed batching system (`extraction:tavily_buffer`) to combine multiple concurrent crawling requests into a single Tavily HTTP batch call. If a worker pushes its URL to the buffer *after* the leader worker has broken out of its polling loop (to dispatch the HTTP request) but *before* the leader releases the distributed lock, the worker fails to become the leader and is forced to poll the status key. Since the current leader has already popped the batch, the worker's URL remains in the buffer indefinitely (or until a future request flushes it). The worker eventually times out and falls back to a non-batched individual request.
- **Impact**: Heavy latency overhead (blocks for `TAVILY_BATCH_TIMEOUT_SECONDS + 5` seconds), increased credit usage, and failure of the batching logic.
- **Recommendation**: Redesign the buffer queue with atomic Redis operations (`BLPOP` or transaction-based pipelining) rather than timing/distributed locks for leader coordination.

### P0: Database Transaction Bloat during Sequential LLM Calls
- **Location**: [story_synthesis_service.py:L811-1000](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/story_synthesis_service.py#L811-L1000)
- **Description**: The `synthesize_story` orchestrator coordinates up to 6 distinct LLM-based stages sequentially (KG construction, Contradiction Detection, Source Comparison, Timeline, Summary Generation, and Quality Feedback evaluation/regeneration). This orchestrator executes inside an active database transaction context (`async with async_session_factory() as session` caller). If one or more LLM providers exhibit high response latency or require retries, the database transaction remains open for 10 to 20 seconds.
- **Impact**: Database connection pool starvation, high transaction lock contention, and vulnerability to application crashes leaving transactions in uncommitted/un-rolled-back states.
- **Recommendation**: Decouple the database session lifecycle from LLM execution. Fetch required database entities first, close the transaction/session, execute the LLM/synthesis pipeline, and then open a short transaction block to write the resulting artifacts and update states.

### P1: Qdrant Connection Pool Leaks across Event Loops
- **Location**: [vector_service.py:L30-53](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/vector_service.py#L30-L53)
- **Description**: The `VectorService` instantiates and caches `AsyncQdrantClient` objects inside a `self._clients` dictionary keyed by the current event loop's ID (`id(asyncio.get_running_loop())`). Since Celery task execution loops are frequently created, torn down, or run inside separate processes/threads, new event loops are regularly initialized. However, the vector service never closes or cleans up historical clients stored in the dictionary.
- **Impact**: Continuous socket leakage, file descriptor exhaustion, and memory leaks over long-running worker processes.
- **Recommendation**: Register an event loop cleanup hook or implement a context-managed client provider that closes connections on thread/loop termination.

### P1: Socket Churn from Ephemeral HTTP Clients
- **Location**: [entity_linker.py:L331](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/entity_linker.py#L331), [crawler_service.py:L71](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/crawler_service.py#L71), [ingestion_service.py:L734](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/ingestion_service.py#L734)
- **Description**: Ephemeral `httpx.AsyncClient` objects are initialized inside standard method calls on every execution (e.g., querying Wikidata inside the entity linker, fetching HTML in the crawler, or parsing RSS feeds).
- **Impact**: High socket churn, inability to reuse TCP connections (forcing SSL handshakes for every request), and increased HTTP latency.
- **Recommendation**: Refactor services to share a singleton `httpx.AsyncClient` instance managed by the application lifetime or connection pool manager.

### P1: Tenacity `reraise=False` Exception Swallowing Gotcha
- **Location**: [entity_linker.py:L338-343](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/entity_linker.py#L338-L343)
- **Description**: In `entity_linker.py`, the `@retry` decorator on `_query_wikidata` is configured with `reraise=False`. If all three attempts to query Wikidata fail, Tenacity will suppress the exception and return the last execution's exception object (or a `RetryError` instance) instead of raising the exception or returning `None`.
- **Impact**: Downstream code expecting `dict | None` receives an exception object, causing a crash due to `AttributeError` or type validation failure.
- **Recommendation**: Set `reraise=True` and catch the exception inside a `try/except` block, or use a custom retry error handler that explicitly returns `None` on failure.

### P2: Today's Token Usage and Cost Aggregation Mismatch
- **Location**: [admin_service.py:L684-694](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/admin_service.py#L684-L694)
- **Description**: In the admin dashboard, the "Tokens Used Today" stat card displays lifetime usage or incorrect statistics depending on timezone-naive comparisons. `start_of_today` is calculated as UTC midnight:
  ```python
  now = datetime.now(UTC).replace(tzinfo=None)
  start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
  ```
  If the host server running the PostgreSQL database operates in a non-UTC timezone, or if timestamps are inserted with varying local/naive formats, naive datetime filters on `created_at >= start_of_today` can result in query mismatches.
- **Impact**: Inaccurate and misleading dashboard graphs/counters regarding real-time cost and token spend.
- **Recommendation**: Enforce timezone-aware database columns and explicitly specify UTC zones (e.g., using PostgreSQL's `timestamptz`) for all telemetry and trace tables.

### P3: Deprecated `datetime.utcnow()` Usage
- **Location**: [gnews_service.py:L558](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/gnews_service.py#L558), [tasks.py:L849](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/tasks.py#L849)
- **Description**: Multiple files across the app use Python's built-in `datetime.utcnow()`, which is deprecated as of Python 3.12.
- **Impact**: Deprecation warnings polluting test logs and potential future compatibility breaks when upgrading Python versions.
- **Recommendation**: Replace all occurrences of `datetime.utcnow()` with `datetime.now(UTC)` or the codebase's standard timezone-naive helper `datetime.now(UTC).replace(tzinfo=None)` to preserve database compatibility.
