# Observability — Optimization Roadmap

**Date:** 2026-08-16. Effort is rough engineering days. Impact is measured
against production figures gathered during the audit.

## Status — 2026-08-17

| Phase | Scope | PR | State |
|---|---|---|---|
| 1 | Stage-detail 500, SSE auth, failure recording | #122 | merged, **deployed** (`v1.38.0`) |
| 2 | Cost, run summaries, stuck-run reaper | #123 | merged, not deployed |
| 3 | Crawl/discovery/synthesis telemetry, DAG mapping | #124 | merged, not deployed |
| 3.4 | Article lineage, wired into the UI | #125 | merged, not deployed |
| 4 | Pooled log client, durable failure logs | #126 | merged, not deployed |
| 5 | Domain-policy upsert, SSE-driven UI | #127 | merged, not deployed |
| 6 | Circular-import fix, dead code, import guard | #128 | open, **must ship before any tag** |
| 7 | Documentation reconciliation | this | — |

**Deployment is the outstanding risk, not the code.** #123 introduced a circular
import that made `import app.main` fail; `v1.39.0` shipped it and crash-looped
the workers until the API was rolled back to `v1.38.0` by hand. `v1.40.0` never
built (GitHub Actions 429/503) and points at the same broken commit, so **neither
tag may be re-run**. #128 carries the fix plus `tests/test_import_integrity.py`,
which imports each entry point in a fresh subprocess — the whole suite passed
throughout the outage because `conftest` warms `app.ai` first.

Items 1–9 below are implemented. Item 10 (a typed API layer for the admin app)
is not, and remains the highest-value structural improvement outstanding: every
response is still consumed as `any`, which is what let several of these defects
survive review.

---

## Top 10 optimizations, by value

### 1. Aggregate the stage-detail endpoint — P0-1
**Impact:** restores inspection of 89% of stage volume (28,218 of 31,796 rows).
Currently HTTP 500.
**Effort:** 0.5d. Replace `scalar_one_or_none()` with a summary query plus a
paginated child list. Do **not** `LIMIT 1` — that hides up to 2,078 rows.

### 2. One pricing table, and stop overwriting the computed cost — P0-3
**Impact:** turns 100% zero cost into real numbers; unblocks `/admin/costs` and
`/admin/cost-forecasting`.
**Effort:** 0.5d. Delete `trace.py:LLM_PRICING`, import `gateway.py:PRICING_TABLE`,
and make `track_llm_call`'s `finally` preserve an already-set cost. Log a warning
on unknown models — the silent zero default is what hid this for 17,333 calls.

### 3. Record failures from `StageSpan` — P0-2
**Impact:** recovers the 616 failures (65%) missing from the Failure Center,
including all 886 `event_extraction` failures.
**Effort:** 1d. Make "mark stage failed" and "write `pipeline_failures`" one
action rather than two independent ones.

### 4. Authenticate both SSE endpoints — P0-4
**Impact:** closes unauthenticated access to live logs and pipeline status.
**Effort:** 0.5d. Validate the query-parameter token that the frontend already
sends; prefer a short-lived stream ticket over a JWT in a URL.

### 5. Fix the run-summary nesting — P1-1
**Impact:** replaces "Completed (no actions)" on every successful run with real
figures. **No new telemetry required — the data is already stored.**
**Effort:** 1d. Read `meta["metrics"]` → `meta["output"]` → top level; accept both
`input`/`inputs`; widen beyond four keys.

### 6. Pool the Redis client in structured logging — P2-1
**Impact:** the largest avoidable cost in the telemetry path. Today
`structured_logging.py:120` calls **synchronous** `redis.from_url()` per log
line inside async worker code — a fresh connection plus three round trips, never
pooled or closed, blocking the event loop each time.
**Effort:** 0.5d. Module-level pooled async client, pipelined `rpush`+`expire`,
and log the exception instead of `except Exception: pass`.

### 7. Emit crawl and discovery metadata — P1-2
**Impact:** the only item requiring genuinely new collection. Fills the blind spot
over 28,218 stage runs at 0.0% metadata.
**Effort:** 1–2d. `crawl_article` already returns status, provider, extractor and
diagnostics; write them to the span.
**Caution:** at 23,216 rows/period, keep the payload small — per-URL detail
belongs in the child rows, not duplicated into the run.

### 8. Give synthesis a place in the DAG — P1-3
**Impact:** four permanently empty DAG nodes become real; removes the "No logs
available" report.
**Effort:** 1–2d. Either emit `stage_runs` from the synthesis orchestrator
(preferred — one system) or teach the UI to read `pipeline_traces`, where all six
synthesis stages are already traced with decisions.

### 9. Reaper for stuck runs and stages — P1-4
**Impact:** clears 7 runs and 3 stages currently hung in `running`, and stops the
UI polling dead work forever.
**Effort:** 0.5d. Mirror the existing `recover_stuck_embeddings_task` pattern;
mark with an explicit reason rather than silently flipping to failed.

### 10. A typed API layer for the admin app
**Impact:** the root enabler of most wiring defects. Every response is consumed as
`any`, so the wrong-metadata-key bug (#5) and the unmapped `completed` status
could not be caught at build time.
**Effort:** 2d. Generate types from the OpenAPI schema; replace `useQuery<any>`.

---

## Backend performance findings

| # | Finding | Evidence | Impact | Fix |
|---|---|---|---|---|
| B1 | Sync Redis connect per log line in async code | `structured_logging.py:120` | Blocks the event loop; 8,412 stage runs/day | Pooled async client (#6) |
| B2 | `_update_domain_policy` opens a new session per provider attempt | `extraction_manager.py:419` | 1–3 extra SELECT+UPDATE+COMMIT per crawled URL, at 23,216 crawls | Batch, or write via the existing session |
| B3 | Duplicate telemetry writes | `llm_traces` **and** `ai_execution_records` written per call | ~2× AI telemetry writes; 53 MB + 2 MB | Converge (see Dead Code §3) |
| B4 | Prompt text stored in Postgres | `llm_traces` 53 MB, largest table | Growth and exposure | Already gated by `save_prompts`; consider truncation and shorter retention |
| B5 | Unbounded `input_payload`/`raw_response` | `pipeline_failures` | Growth risk | Cap at write time |
| B6 | `stage_runs` metadata up to 61 KB | max observed | JSONB bloat | Cap per-span payload; `embedding` stores an article-ID sample list |
| B7 | Failure analytics over an incomplete set | 331 of 947 | Wrong conclusions, not slow | Fixed by #3 |

**Measured growth: ~2.6 GB/month**, dominated by `llm_traces`. The scheduled
`purge_observability_data_task` (30d retain / 14d redact, `celery_app.py:183`) is
the main mitigation and it is genuinely running.

---

## Frontend performance findings

| # | Finding | Evidence | Fix |
|---|---|---|---|
| F1 | No log virtualisation | `LiveLogViewer` renders `logs.map(...)` over an unbounded array; Redis lists are uncapped | Windowed list; cap retained lines |
| F2 | Polling alongside SSE | `refetchInterval: 4000` on stage details while `running`, plus an open `EventSource` | Let SSE drive; poll only as a fallback |
| F3 | `last_id` cursor unused | Backend supports replay; frontend never sends it | Send it on reconnect so a 30s disconnect replays instead of dropping events |
| F4 | 2,195-line page component | `admin/pipeline/page.tsx` | Split; memoise the DAG |
| F5 | No client-side event de-duplication | SSE events applied directly | Key by stage-run id |

---

## Phased plan

**Phase 1 — Critical correctness (~2.5d)**
Items 1, 4, 3 — the dashboard becomes usable and secure, and no failure is lost.

**Phase 2 — Truthful data (~2d)**
Items 2, 5, 9 — cost stops being zero, summaries become real, runs stop hanging.
Highest perceived improvement per day of work, because it is almost entirely
read-side.

**Phase 3 — Wiring and blind spots (~4d)**
Items 7, 8, plus mapping `event_extraction`/`ingestion_gnews` into the DAG and
wiring the two orphaned endpoints (`/articles/{id}/trace`,
`/pipeline/story/{id}/traces`) that already hold the lineage and synthesis data.

**Phase 4 — Logs (~1.5d)**
Item 6, plus a durable store for failed-run logs (`error_logs` exists and is
empty — it is the natural destination).

**Phase 5 — Performance (~2d)**
B2, B3, F1, F2, F3.

**Phase 6 — Dead code (~1d)**
Only after Phase 2, since several endpoints look useless purely because cost is
zero. See `Observability_Dead_Code.md`.

**Phase 7 — Documentation (~0.5d)**
Reconcile the docs listed in the audit §8.

---

## Sequencing note

Phases 1 and 2 total roughly **4.5 days and resolve five of the six blockers**
identified in the audit's headline question — because the telemetry already
exists and is being discarded on the read path. Only item 7 (crawl/discovery
metadata) requires new collection. Sequencing new instrumentation before the
read-side fixes would add data to a dashboard that still cannot display it.
