# NewsIQ Observability Dashboard — Full Audit

**Date:** 2026-08-16
**Method:** code tracing plus read-only queries against the production database
(`pipeline_runs` 6,318 rows / `stage_runs` 31,796 / `llm_traces` 17,333) and the
running `newsiq-celery-worker` container. No code was changed.

Every claim below is labelled **CONFIRMED** (reproduced against production),
**LIKELY** (strong code evidence, not executed), or **RECOMMENDATION**.

---

## Executive Summary

```text
Backend:              6/10   — rich collection, but three parallel systems and broken cost
Frontend:             5/10   — no mock data, but four of ten DAG stages have no backing data
Wiring:               3/10   — the primary stage-detail endpoint 500s on the busiest stage
Reliability:          5/10   — runs and stages can hang in `running` forever
Performance:          4/10   — a new synchronous Redis connection per log line, inside async code
Debuggability:        3/10   — every successful run reads "Completed (no actions)"
Production readiness: 4/10
```

The infrastructure is substantially better than the dashboard suggests. The
collectors gather genuinely rich telemetry — `input`, `output`, `metrics`,
`lineage`, `warnings`, `artifacts`, `resources` — and most of it never reaches a
screen. **The dominant failure mode is not missing data; it is data that is
collected, stored, and then dropped between the database and the UI.**

### The headline answer

> Can an engineer select any pipeline run and reliably understand why it ran,
> what data entered it, what every stage did, what failed or was skipped, what
> AI decisions occurred, how long it took, how much it cost, and where the final
> output came from?

**No.** Six links are missing, in order of severity:

1. Opening the busiest stage returns **HTTP 500** (P0-1).
2. **65% of failures never appear in the Failure Center** (P0-2).
3. **Cost is £0.00 everywhere** — every row, every model (P0-3).
4. Every successful run is summarised as **"Completed (no actions)"** (P1-1).
5. **73% of stage runs record no metadata at all** (P1-2).
6. **Synthesis has no `stage_run` records**, so its DAG node is permanently
   empty (P1-3).

---

## 1. Actual vs. assumed architecture

The documented chain is `PipelineRun → Celery → StageRun → Collector → Postgres
→ API → UI`. In production that chain exists, but **three parallel telemetry
systems** run alongside each other and only one reaches the dashboard.

| System | Rows | Written by | Read by dashboard |
|---|---|---|---|
| `stage_runs` | 31,796 | `StageSpan` collector | ✅ yes — the DAG and inspectors |
| `pipeline_traces` | 9,856 | synthesis orchestrator | ⚠️ only via `/story/{id}/traces`, which **no frontend calls** |
| `llm_traces` | 17,333 | `track_llm_call` | ✅ via stage detail |
| `ai_execution_records` | 3,794 | gateway `_persist_execution_record` | ❌ no consumer |

`pipeline_traces` holds precisely the synthesis detail the UI most needs
(`knowledge_graph` 128, `summary_generation` 119, `contradiction_detection` 127,
`timeline_generation` 127, `source_comparison` 127, `feedback_agent` 96,
`publisher` 89 — **all with decisions recorded**) and the dashboard never reads
it, because the DAG is driven by `stage_runs`, where none of those stages exist.

### Dead architecture — CONFIRMED by row count

Six tables are fully modelled, migrated, and **never written**:

```text
token_usage        0 rows      cost_records    0 rows
retry_history      0 rows      error_logs      0 rows
human_reviews      0 rows      function_runs   0 rows
```

`prompt_versions` holds 18 rows, last written **2026-07-14** — a month stale,
while `llm_traces` has no `prompt_version` column at all.

---

## 2. Pipeline lifecycle — CONFIRMED defects

### Status vocabularies disagree

`stage_runs.status` contains **two terminal success values**:

```text
success    29,410
completed   1,128      ← different writer, same meaning
failed        945
skipped       293
running         5
```

The frontend `STATUS_CONFIG` maps only `success`, `failed`, `running`,
`pending`, `skipped`, `retrying`. **`completed` is unmapped**, so those 1,128
stage runs render with no icon and no status colour.

### Runs hang forever — CONFIRMED

```text
pipeline_runs stuck `running` > 1h:   7
stage_runs   stuck `running` > 1h:    3
```

There is no reaper. A worker killed mid-stage leaves the row `running`
permanently, and the UI polls it as live work indefinitely. `total_stages`,
`successful_stages` and `failed_stages` on those rows never reconcile.

### Duplicate stage runs — CONFIRMED, and it breaks the UI

834 `(run_id, stage)` pairs have more than one row. The worst:

```text
run 0e1acd88  crawling          2,079 rows
run 0d154f6a  crawling          1,228 rows
run 0e1acd88  discovery_search    376 rows
```

This is not corruption — one `crawl_url_task` per URL legitimately opens its own
`StageSpan` under the shared run. The defect is that the **read** side assumes
one row per stage (see P0-1).

---

## 3. Stage observability matrix — CONFIRMED

Derived from `stage_runs` grouped by stage. "Meta" is the share of rows carrying
non-empty metadata.

| Stage | Rows | Meta | Inputs | Outputs | Metrics | Errors | AI trace | Lineage | In UI DAG |
|---|---|---|---|---|---|---|---|---|---|
| `crawling` | 23,216 | **0.0%** | ❌ | ❌ | ❌ | ⚠️ only traceback | ❌ | ❌ | ✅ |
| `discovery_search` | 5,002 | **0.0%** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `clustering_incremental` | 1,229 | 99.8% | ⚠️ `inputs` | ⚠️ `outputs` | ❌ | ✅ | ❌ | ❌ | ✅ |
| `event_extraction` | 899 | 100% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | **❌ unmapped** |
| `embedding` | 497 | 100% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `clustering_batch` | 468 | 100% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ingestion_rss` | 313 | 100% | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `ingestion_gnews` | 157 | 100% | ✅ | ✅ | ✅ | ✅ | — | ✅ | **❌ unmapped** |
| `entity_extraction` | 6 | 100% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ unmapped |
| `entity_linking` | 6 | 100% | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `indexing` | 2 | 100% | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `synthesis` / `summary_generation` | **0** | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ node, no data |
| `stage_a` / `stage_b` | **0** | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ node, no data |
| `feedback_agent` | **0** | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ node, no data |
| `publisher` | **0** | — | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ node, no data |

Two structural problems are visible in that table.

**The two busiest stages record nothing.** `crawling` and `discovery_search`
together are **89% of all stage runs** and both sit at 0.0% metadata. Everything
the Crawling inspector is specified to show — URL, HTTP status, provider,
extraction method, content size, failure reason — exists in
`extraction_manager.crawl_article`'s return value and in `DomainExtractionPolicy`,
and none of it is written to the `StageSpan`. Only `error_traceback` is stored,
and only on failure.

**`event_extraction` is failing 98.6% of the time and is invisible.** 886 of 899
runs failed. It is absent from `BACKEND_TO_FRONTEND_STAGE`, so
`mapBackendToFrontendStage` falls through to `backendStage.toUpperCase()` →
`"EVENT_EXTRACTION"`, which matches no entry in `PIPELINE_STAGES` and is
therefore never drawn. **The single worst-performing stage in the pipeline
cannot be seen on the dashboard.** (This is consistent with the extraction
backlog tracked separately.)

### Two incompatible metadata schemas — CONFIRMED

The collector writes:

```json
{"input": {...}, "output": {...}, "metrics": {...}, "lineage": [],
 "warnings": [], "errors": [], "artifacts": {}, "resources": {...}}
```

`clustering_incremental` instead writes a hand-rolled shape:

```json
{"inputs": {"article_id": "..."}, "outputs": {"merged": false}}
```

Note `input`/`output` versus `inputs`/`outputs`. Any renderer keyed on one shape
silently shows nothing for the other.

---

## 4. Critical bugs

### P0-1 — Stage detail returns HTTP 500 for the busiest stage — CONFIRMED

**Issue.** `GET /admin/pipeline/runs/{run_id}/stages/{stage}` uses
`scalar_one_or_none()` against a `(run_id, stage)` pair that is not unique.

**Evidence.** Executed against production inside the container:

```text
RAISED MultipleResultsFound: Multiple rows were found when one or none was required
```

834 pairs are affected; one run has 2,079 `crawling` rows.

**Root cause.** `admin.py:575-579` assumes one stage run per stage per run. The
write side legitimately creates one per crawled URL.

**Impact.** Clicking **Crawl** or **Discovery** — 89% of all stage volume — on
any substantial run returns 500. The drawer shows an error or stays blank. This
alone makes the dashboard unusable for its primary purpose.

**Fix.** Aggregate rather than assume: return a stage *summary* (count, status
histogram, total/percentile latency, error samples) plus a paginated child list.
Do not `LIMIT 1` — that would silently hide 2,078 rows.

**Files.** `apps/api/app/api/v1/admin.py:566-640`

---

### P0-2 — Two thirds of failures never reach the Failure Center — CONFIRMED

**Issue.** Failed stage runs and recorded failures do not reconcile.

**Evidence.**

```text
stage_runs with status='failed':  947
pipeline_failures rows:           331      →  616 failures (65%) invisible
```

**Root cause.** `pipeline_failures` is written by an explicit
`failure_recorder` call on selected paths; `StageSpan` marks a stage failed
independently. Nothing guarantees the two happen together.

**Impact.** Directly violates the stated invariant that *a failed pipeline must
never disappear from Failure Center*. The 886 `event_extraction` failures are
the largest missing block.

**Fix.** Record the failure from `StageSpan.__aexit__` itself, so marking a stage
failed and creating the failure record are the same action rather than two
independent ones.

**Files.** `apps/api/app/core/trace.py` (StageSpan), `app/core/failure_recorder.py`

---

### P0-3 — Cost tracking reads zero for every call ever made — CONFIRMED

**Issue.** `llm_traces.cost_usd = 0` for **17,333 of 17,333 rows (100%)**.

**Evidence.** Two divergent pricing tables exist:

| Table | File | Contains production models? |
|---|---|---|
| `PRICING_TABLE` | `app/ai/gateway.py:44` | ✅ `gemini-3.1/3.5-flash-lite` present |
| `LLM_PRICING` | `app/core/trace.py:1069` | ❌ only `gemini-2.0/2.5-*` |

Confirmed absent from `LLM_PRICING`: `gemini-3.5-flash-lite`,
`gemini-3.1-flash-lite`, `qwen.qwen3-vl-235b-a22b-instruct`, `deepseek.v3.2`.

**Root cause — a genuine overwrite.** The gateway computes the correct cost at
`gateway.py:479-480` and assigns it to `trace_call.cost_usd`. Then
`track_llm_call`'s `finally` block unconditionally recomputes it:

```python
call.cost_usd = calculate_llm_cost(call.model, call.input_tokens, call.output_tokens)
```

`calculate_llm_cost` looks up the *stale* table and its `.get(model, {"input":
0.0, "output": 0.0})` default silently returns zero pricing for every model
actually in production. The correct value is computed and then discarded.

**Compounding.** `input_tokens`/`output_tokens` are 0 on **15,910 of 17,333
rows (92%)**, so even a corrected table would leave most rows at zero.

**Impact.** `/admin/costs`, `/admin/cost-forecasting` and every per-stage cost
figure are structurally zero. There is no cost observability at all.

**Fix.** Delete `LLM_PRICING`, import the gateway's `PRICING_TABLE` as the single
source, and make the `finally` block preserve an already-set cost. Log a warning
on an unknown model instead of defaulting to zero — silent zero is what hid this.

**Files.** `apps/api/app/core/trace.py:1069-1086,1153`, `app/ai/gateway.py:44-63`

---

### P0-4 — Both SSE endpoints are unauthenticated — CONFIRMED

**Issue.** Neither streaming endpoint requires an admin.

```python
@router.get("/pipeline/runs/{run_id}/stages/{stage}/logs/stream")
async def stream_stage_run_logs(run_id: uuid.UUID, stage: str):   # no Depends(require_admin)

@router.get("/pipeline/stream")
async def stream_pipeline_status(request: Request, last_id: str = "$"):   # no Depends(require_admin)
```

The sibling `GET .../logs` **does** require admin, so this is an inconsistency
rather than a deliberate policy.

**Compounding.** The frontend appends the JWT as a **query parameter**
(`?token=${token}`, `pipeline/page.tsx:144`) because `EventSource` cannot set
headers — and the backend never reads it. So the token is written into access
logs and proxy logs while providing no protection.

**Impact.** Anyone who can reach the API can stream live pipeline logs and status
transitions, which include article URLs, story IDs, stage errors and tracebacks.

**Fix.** Accept the token as a query parameter, validate it explicitly, and reject
unauthenticated subscribers. Prefer a short-lived single-use stream ticket over a
full JWT in a URL.

**Files.** `apps/api/app/api/v1/admin.py:661-700,702+`

---

### P1-1 — Every successful run says "Completed (no actions)" — CONFIRMED

**Issue.** `_build_run_summary` reads four keys at the **top level** of stage
metadata. Those keys are never at the top level.

**Evidence.** Sampled live rows:

| Stage | Top-level keys | `articles_ingested` present? |
|---|---|---|
| `ingestion_rss` | `input, errors, output, lineage, metrics, warnings, artifacts, resources` | ❌ |
| `clustering_batch` | same collector shape | ❌ |
| `embedding` | same collector shape | ❌ |
| `clustering_incremental` | `inputs, outputs` | ❌ |

The real values are nested — `clustering_batch` genuinely holds
`{"metrics": {"stories_created": 1}, "output": {"stories_created": "1"}}` — but
the builder asks for `meta.get("stories_created")` and gets `None`.

**Root cause.** The summary builder was written against a flat metadata shape
that the collector does not produce. `parts` is therefore always empty and the
function falls through to its generic string.

**Impact.** The run history answers none of its intended questions. This is the
exact symptom raised in the brief, and it is a pure read-side defect — **the
data needed for the richer summary is already in the database.**

**Fix.** Read `meta["metrics"]` first, falling back to `meta["output"]` and
top-level; accept both `input`/`inputs` spellings; extend beyond four keys to
cover crawl, discovery, event extraction and synthesis. Never return
"Completed (no actions)" when any stage recorded metrics — prefer naming the
stages that ran.

**Files.** `apps/api/app/api/v1/admin.py:474-513`

---

### P1-2 — The two busiest stages record no metadata — CONFIRMED

`crawling` (23,216 rows) and `discovery_search` (5,002) are at **0.0%**
metadata. Every field the Crawl and Discovery inspectors are specified to show is
available at the call site and simply never written to the span.

**Impact.** No per-URL HTTP status, provider, extraction method, content size or
failure reason is retrievable after the fact. Crawler regressions are invisible
to the dashboard and can only be diagnosed from container logs within the 24-hour
Redis window.

**Files.** `apps/api/app/workers/tasks.py` (`crawl_url_task`),
`app/services/extraction_manager.py`

---

### P1-3 — Four of ten DAG stages have no backing data — CONFIRMED

`FRONTEND_TO_BACKEND_STAGES` maps these to backend stages that produce **zero**
`stage_runs`:

| DAG node | Mapped backend stages | Rows |
|---|---|---|
| `STAGE_A` | `stage_a`, `stage a (pre-embedding)` | 0 |
| `STAGE_B` | `stage_b`, `stage b (post-embedding)` | 0 |
| `SYNTHESIS` | `summary_generation`, `timeline_generation`, `contradiction_detection`, `difference_engine`, `knowledge_graph`, `synthesis_orchestrator` | 0 |
| `FEEDBACK` | `feedback_agent` | 0 |
| `PUBLISHER` | `publisher`, `indexing` | 2 |

When no stage run matches, the selector falls back to `backendStages[0]`
(`pipeline/page.tsx:1263`) — e.g. `summary_generation` — and both the detail and
logs requests then 404 / return `[]`. **This is the "No logs available" report:
the log key `newsiq:logs:{run}:summary_generation` is never created because no
such stage span exists.**

The irony is that all six synthesis stages *are* traced — in `pipeline_traces`,
with decisions — via an endpoint (`/pipeline/story/{id}/traces`) that no frontend
code calls.

---

### P1-4 — Runs and stages hang in `running` forever — CONFIRMED

7 runs and 3 stages have been `running` for over an hour with no reaper. See §2.

**Fix.** A periodic task that marks spans older than a threshold as
`failed`/`unknown` with an explicit reason, mirroring the existing
`recover_stuck_embeddings_task` pattern.

---

### P1-5 — 92% of LLM traces have no token counts — CONFIRMED

`input_tokens = output_tokens = 0` on 15,910 of 17,333 rows. Providers that do
not return usage are recorded as zero rather than unknown, so token and cost
analytics silently under-report instead of flagging the gap.

---

### P2-1 — Logging opens a new synchronous Redis connection per log line — LIKELY

`_store_and_publish_log` (`app/core/structured_logging.py:120`) executes
`redis.from_url(settings.REDIS_URL)` — the **synchronous** client — on **every
log record** emitted inside a stage span, then `rpush`, `expire` and `publish`.

This runs inside async worker code, so each log line blocks the event loop for a
connect plus three round trips, and no connection is pooled or closed. With 8,412
stage runs per day this is the single largest avoidable cost in the telemetry
path. The whole body is wrapped in `except Exception: pass`, so failures are
invisible.

**Fix.** Module-level pooled client, pipelined commands, and log the exception
rather than swallowing it.

---

### P2-2 — Logs are Redis-only with a 24-hour TTL — CONFIRMED

2,392 log keys exist, each `expire`d at 86,400s. There is no durable log store —
`error_logs` exists as a table and holds **0 rows**. A failed run older than a day
has no logs at all, which is precisely when they are wanted.

---

## 5. AI observability

| Field | Populated | Note |
|---|---|---|
| `run_id` | 98% | good |
| `stage_run_id` | 98% | good |
| `stage` | 100% | good |
| `provider` / `model` | 100% | good |
| `story_id` | **3%** | lineage from a story back to its LLM calls is mostly broken |
| `prompt_version` | **absent** | no column on `llm_traces`; only on `ai_execution_records` |
| `input/output tokens` | 8% | see P1-5 |
| `cost_usd` | **0%** | see P0-3 |

`ai_execution_records` (3,794 rows) carries the richer fields the UI would want —
`decision`, `confidence`, `cache_hit`, `schema_repaired`, `fallback_count`,
`prompt_version`, plus reflection counters — and **has no reader anywhere in the
frontend**. Two AI telemetry systems are maintained; the better one is unused.

---

## 6. Security

| # | Finding | Severity | Status |
|---|---|---|---|
| S1 | Both SSE endpoints unauthenticated (P0-4) | **High** | CONFIRMED |
| S2 | JWT passed as a URL query parameter → leaks into access logs | **Medium** | CONFIRMED |
| S3 | `llm_traces` stores `system_prompt`, `user_prompt`, `response_text`; the stage-detail endpoint returns all three verbatim | **Medium** | CONFIRMED — admin-gated, and `save_prompts` limits it to errors/DEBUG/sampled calls, but the table is 53 MB and retained 30 days |
| S4 | `pipeline_failures.input_payload` / `raw_response` store unbounded provider output | **Medium** | LIKELY |
| S5 | Stage detail returns raw tracebacks to the client | **Low** | CONFIRMED — acceptable for an admin tool, noted for completeness |

No API keys or database credentials were found in telemetry payloads.

---

## 7. Data growth and retention

Measured:

```text
stage_runs        8,412/day     23 MB total    avg metadata 711 B, max 61 KB
llm_traces        7,871/day     53 MB total    ← largest, driven by prompt text
pipeline_runs     1,792/day    3.2 MB
pipeline_traces   3,437/day    8.7 MB
ai_execution_records 1,160/day  2.0 MB
Redis logs        2,392 keys, 24h TTL
```

Projected at current rates: **~2.6 GB/month** of observability data, dominated by
`llm_traces`.

`purge_observability_data_task(retention_days=30, redact_days=14)` exists **and is
scheduled** in `celery_app.py:183`, which is the main saving grace. Gaps: no
cleanup for the six empty tables, no orphan sweep (currently 0 orphans, so it
has not yet mattered), and `queue_metrics` (9,332 rows) has no timestamp column
usable for retention.

---

## 8. Documentation drift

| Document | Drift |
|---|---|
| RFC/architecture docs describing `token_usage`, `cost_records`, `retry_history`, `human_reviews` | Tables exist, are **never written** |
| Any doc describing cost dashboards | Cost is 0 for 100% of rows |
| Pipeline stage lists | Omit `event_extraction` and `ingestion_gnews`, which are live; include `stage_a`/`stage_b`, which produce nothing |
| `pipeline_audit_report.md`, `implementation-report.md` (repo root) | Predate the current three-system split |

---

## 9. Recommended fix order

**Phase 1 — Critical correctness (unblocks the dashboard)**
1. P0-1 aggregate stage detail instead of `scalar_one_or_none`
2. P0-4 authenticate both SSE endpoints
3. P0-2 record failures from `StageSpan` so none can be lost

**Phase 2 — Make the data truthful**
4. P0-3 single pricing table; stop overwriting a computed cost
5. P1-1 read nested metadata in the run summary
6. P1-4 reaper for stuck runs and stages

**Phase 3 — Fill the blind spots**
7. P1-2 record crawl and discovery metadata
8. P1-3 either emit `stage_runs` for synthesis or have the UI read `pipeline_traces`
9. Map `event_extraction` and `ingestion_gnews` into the DAG

**Phase 4 — Logs**
10. P2-1 pooled Redis client
11. P2-2 durable log store for failed runs

**Phase 5 — Performance**
12. Frontend log virtualisation; reconcile polling against SSE

**Phase 6 — Dead code** — see `Observability_Dead_Code.md`

**Phase 7 — Documentation**

---

## 10. What it takes to reach "YES"

Items 1, 3, 4, 5, 7 and 8 are the complete set required to answer the headline
question affirmatively. Notably **five of the six are read-side or wiring fixes**
— the telemetry already exists in the database. Only item 7 (crawl/discovery
metadata) requires new collection.
