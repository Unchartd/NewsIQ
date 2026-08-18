# Observability — Dead Code Report

**Date:** 2026-08-16. Nothing here has been deleted. Every candidate was checked
by searching the whole repository for references and by counting production rows.

**Rule applied:** a symbol is only "safe to remove" when it has no reference, no
data, and no plausible near-term consumer. Several items below are *unused but
valuable* — they are marked **WIRE UP, DO NOT DELETE**.

---

## 1. Database tables never written

| Table | Rows | Model | Why it appears dead | References | Confidence | Safe to remove? |
|---|---|---|---|---|---|---|
| `token_usage` | **0** | `TokenUsageModel` (`observability_models.py:214`) | No writer anywhere; `llm_traces` carries token fields instead | model + migration only | High | **NO — decide first.** Token data is currently 92% missing (P1-5); this table may be the intended fix rather than dead weight |
| `cost_records` | **0** | `CostRecordModel:243` | No writer; cost lives on `llm_traces` (and is 0) | model + migration only | High | **NO — decide first**, same reasoning as above |
| `retry_history` | **0** | `RetryHistoryModel:284` | No writer; `retry_count` is a column on other tables | model + migration only | High | YES, after confirming no roadmap need |
| `error_logs` | **0** | `ErrorLogModel:313` | No writer; logs go to Redis with a 24h TTL | model + migration only | High | **NO — this is the missing durable log store** (P2-2) |
| `human_reviews` | **0** | `HumanReviewModel:475` | ~~No writer~~ — **CORRECTED, see below** | model + endpoint + service | — | **NO — it is live** |
| `function_runs` | **0** | ~~`FunctionRunModel:516`~~ | No writer, no reader, no endpoint | model + exports only | High | **REMOVED** (2026-08-17) |

### Correction: `human_reviews` is not dead — 2026-08-17

This entry was wrong. Verified before removing anything:

`admin_service.py:485` **constructs and adds** a `HumanReviewModel` row, reached from
`POST /admin/review/{story_id}/action` — an endpoint the admin frontend does
call. The table is empty because no admin has used the action yet, not because
nothing writes to it. Removing it would have deleted a working feature.

The lesson generalises: **zero rows means "unused", not "unreachable".** Only
`function_runs` had no reference beyond its own export, and it is the only model
removed.

**None of these should be dropped in the same change as any other work.** Four
of the six describe capabilities the audit found *missing* — dropping them would
remove the obvious place to put the fix.

---

## 2. Endpoints with no frontend consumer

Confirmed by searching `apps/admin/src` for each path.

### 2a. WIRE UP, DO NOT DELETE

| Endpoint | Why it matters | Confidence dead |
|---|---|---|
| `GET /admin/articles/{article_id}/trace` | **The data-lineage endpoint.** The audit's lineage gap is a missing UI, not a missing API | High (unused) |
| `GET /admin/pipeline/story/{story_id}/traces` | Reads `pipeline_traces` — the synthesis telemetry the DAG is missing (P1-3) | High (unused) |

### 2b. Genuinely unused analytics surface

| Endpoint | Response model | Confidence | Safe to remove? |
|---|---|---|---|
| `GET /admin/prompt-analytics` | `list[PromptAnalyticsResponse]` | High | NO — reads `prompt_versions`, stale since 2026-07-14; fix data first |
| `GET /admin/model-benchmarks` | `list[ModelBenchmarkResponse]` | High | Probably — verify no external caller |
| `GET /admin/context-analytics` | `list[ContextAnalyticsResponse]` | High | Probably |
| `GET /admin/cache-effectiveness` | `list[CacheEffectivenessResponse]` | High | Probably |
| `GET /admin/hallucination-analytics` | `HallucinationAnalyticsResponse` | High | NO — reads `ai_execution_records`, which has real data (3,794 rows) and genuine value |
| `GET /admin/cost-forecasting` | `CostForecastingResponse` | High | NO — blocked by P0-3; would return zeros today |
| `GET /admin/provider-sla` | `list[ProviderSLAResponse]` | High | NO — provider health is directly relevant to the quota problems seen in production |

### 2c. Plain unused

| Endpoint | Confidence | Safe to remove? |
|---|---|---|
| `GET /admin/users` | High | NO — plausible admin need, trivial cost |
| `GET /admin/stats` | High | Probably — superseded by `/metrics/summary` |
| `GET /admin/timeline/{story_id}` | High | NO — story timeline is a real feature elsewhere |
| `GET /admin/review/queue` | High | Tied to `human_reviews` (0 rows); remove together or not at all |
| `POST /admin/pipeline/purge` | High | NO — manual escape hatch for retention |

**Summary: 13 of 49 endpoints (27%) unused. Only ~3 are true deletion
candidates**; the rest are unfinished wiring or blocked on a data bug.

---

## 3. Duplicated architecture

Not dead, but redundant — this is where consolidation pays.

| Duplication | Evidence | Recommendation |
|---|---|---|
| **Two pricing tables** | `PRICING_TABLE` (`gateway.py:44`, current models) vs `LLM_PRICING` (`trace.py:1069`, gemini-2.x only) | **DONE** in #123 — consolidated into `app/core/llm_pricing.py`. Note it deliberately does **not** live under `app.ai`: `app/ai/__init__.py` imports the gateway, which imports `app.core.trace`, so a pricing module there makes `import app.main` fail with a circular import. That regression shipped in #123 and was caught in Phase 6; `tests/test_import_integrity.py` now guards it |
| **Two AI telemetry stores** | `llm_traces` (17,333, no `prompt_version`) vs `ai_execution_records` (3,794, richer: decision, confidence, cache_hit, schema_repaired, prompt_version) | Converge. `ai_execution_records` has the better schema and no reader |
| **Two stage-trace systems** | `stage_runs` (31,796, read by UI) vs `pipeline_traces` (9,856, synthesis only, unread) | Either emit `stage_runs` from synthesis or teach the UI to read both |
| **Two metadata shapes** | collector `input/output/metrics/...` vs `clustering_incremental`'s `inputs/outputs` | Normalise `clustering_incremental` onto the collector |
| **Two terminal statuses** | `success` (29,410) vs `completed` (1,128) | Pick one on the write side; accept both on read during transition |

---

## 4. Frontend

| Candidate | Finding |
|---|---|
| Mock / demo / hardcoded data | **None found.** Every grep hit was an `<input placeholder>` attribute. The dashboard is genuinely wired to the API |
| Unused hooks | None — there is no hooks directory; all logic is inline |
| Unused components | None obviously orphaned; the app is small (21 files) |
| `useSSE.ts` | Used ✅ |
| `date-utils.ts` | Used ✅ |
| **Missing** rather than dead | No typed API layer, no lineage view, no consumer for `ai_execution_records` |

The frontend's problem is not dead code. It is a 2,195-line monolith
(`admin/pipeline/page.tsx`) with no shared types, where every response is `any`.

---

## 5. Stale configuration and data

| Item | State | Action |
|---|---|---|
| `prompt_versions` | 18 rows, last write **2026-07-14** | Either resume writing on prompt change or stop surfacing it as live |
| `queue_metrics` | 9,332 rows, **no usable timestamp column** for retention | Add one or exclude from growth planning |
| `stage_a` / `stage_b` stage names | Referenced in frontend mappings, **0 rows ever** | Remove from the DAG or start emitting |
| `difference_engine`, `synthesis_orchestrator`, `discovery_crawl`, `deduplication` | In `FRONTEND_TO_BACKEND_STAGES`, **0 rows** | Confirm whether renamed or removed |

---

## 6. Recommended removal order

1. **Nothing in Phase 1.** No deletion is on the critical path; the P0 bugs are all
   read-side logic.
2. After P0-3 lands: delete `LLM_PRICING` (§3) — the only unambiguous deletion
   that also fixes a bug.
3. After a product decision on human review: `human_reviews` + `/admin/review/queue`
   + `HumanReviewQueueResponse` together.
4. `function_runs` and `retry_history` — genuinely unreferenced.
5. Re-evaluate §2b once P0-3 is fixed; several endpoints only look useless because
   they would currently render zeros.

**Do not remove** `error_logs`, `token_usage`, or `cost_records` until the
corresponding gaps (durable logs, token capture, cost) are resolved — they are the
natural destinations for those fixes.

---

## 7. Newly dead after the P0-6 / P0-7 fixes

| Item | State | Action |
|---|---|---|
| `check_contradiction` (`app/agents/contradiction_agent.py:39`) | Its only production caller was the duplicate chain removed from `ContradictionService`. Now referenced solely by its own module, `agent_registry`'s `"contradiction"` branch, and `test_agents.py` | Remove together with the registry branch and its test, once the fix has run in production long enough to be sure the gateway path is sufficient |

Deliberately left in place for now: deleting it would widen a correctness fix
into a refactor of the agent registry, and the registry branch is the kind of
thing another caller could reasonably pick up.
