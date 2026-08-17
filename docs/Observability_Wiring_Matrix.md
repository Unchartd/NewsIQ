# Observability — Frontend ↔ Backend Wiring Matrix

> **Status 2026-08-17.** W1–W7 below are all fixed in code (#122–#127). The two
> orphaned lineage endpoints are now wired: `/admin/articles/{id}/trace` backs an
> expandable panel in the story inspector (#125), and the synthesis stages it
> could not previously show are mirrored into `stage_runs` (#124). Production
> still runs `v1.38.0` — Phase 1 only — so the matrix below describes what was
> measured, not what is currently served.
>
> Section 6 (no typed API layer) is **not** fixed and remains the root enabler:
> every response is still consumed as `any`, so a field rename or an unmapped
> status value still fails silently at runtime rather than at build time.

**Date:** 2026-08-16. Verified by tracing each frontend call site to its endpoint,
service and table, and by querying production for whether the data exists.

Admin frontend: 21 files, 6,729 lines, of which `admin/pipeline/page.tsx` is
2,195. There is no hooks directory, no shared TypeScript interface file, and the
API client is 40 lines with no typed methods — every response is consumed as
`any`, so **no field-name mismatch can be caught at compile time**.

---

## 1. Feature matrix

| Feature | Frontend | API | Backend reads | Data exists | Working |
|---|---|---|---|---|---|
| Run history list | `pipeline/page.tsx` | `GET /admin/pipeline/runs` | `pipeline_runs` + `stage_runs` | ✅ 6,318 runs | ⚠️ list yes, **summary always generic** |
| Run summary text | same | same | `_build_run_summary` | ✅ nested in metadata | ❌ **reads wrong nesting** |
| DAG / stage status | `pipeline/page.tsx` | `GET /admin/pipeline/status` | `stage_runs` | ⚠️ 11 of 15 stages | ⚠️ 4 nodes permanently empty |
| **Stage inspector** | `pipeline/page.tsx:1272` | `GET /admin/pipeline/runs/{id}/stages/{stage}` | `stage_runs` + `llm_traces` | ✅ | ❌ **HTTP 500 on `crawling`/`discovery_search`** |
| Stage logs | `LiveLogViewer:132` | `GET .../stages/{stage}/logs` | Redis `newsiq:logs:*` | ⚠️ 2,392 keys, 24h TTL | ⚠️ works for real stages, empty for the 4 phantom ones |
| Live log stream | `LiveLogViewer:144` | `GET .../logs/stream` (SSE) | Redis pubsub | ✅ | ⚠️ works, **but unauthenticated** |
| Pipeline event stream | `pipeline/page.tsx` | `GET /admin/pipeline/stream` (SSE) | Redis Streams | ✅ | ⚠️ works, **unauthenticated** |
| Failure Center list | `failures/page.tsx` | `GET /admin/failures` | `pipeline_failures` | ⚠️ 331 of 947 | ❌ **65% of failures missing** |
| Failure detail | `failures/[id]/page.tsx` | `GET /admin/failures/{id}` | `pipeline_failures` | ✅ | ✅ |
| Failure resolve / replay | `failures/[id]` | `POST .../resolve`, `.../replay` | — | ✅ | ✅ |
| Failure analytics | `failure-analytics/page.tsx` | `GET /admin/failure-analytics` | `pipeline_failures` | ⚠️ partial set | ⚠️ analytics over 35% of reality |
| Cost view | `costs/page.tsx` | `GET /admin/costs` | `llm_traces.cost_usd` | ❌ **0 for all 17,333** | ❌ **structurally zero** |
| Story inspector | `stories/[storyId]` | `GET /admin/stories/{id}` | stories + traces | ✅ | ✅ |
| Story versions / evolution | `stories/[storyId]` | `GET /admin/pipeline/story/{id}/versions`, `/evolution` | `story_evolutions` 716 | ✅ | ✅ |
| Story rollback | `stories/[storyId]` | `POST .../rollback/{n}` | — | ✅ | ✅ |
| Clusters debugger | `clusters/page.tsx` | `GET /admin/clusters` | stories | ✅ | ✅ |
| Cluster merge / split | `clusters/page.tsx` | `POST /admin/clusters/merge`, `/{id}/split` | — | ✅ | ✅ |
| Entities debugger | `entities/page.tsx` | `GET /admin/entities` | entities | ✅ | ✅ |
| Prompts | `prompts/page.tsx` | `GET /admin/prompts` | `prompt_versions` | ⚠️ 18 rows, stale since 2026-07-14 | ⚠️ shows month-old data |
| Quality / evaluation | `quality/page.tsx` | `GET /admin/evaluation/report`, `POST /run` | file | ✅ | ✅ |
| Metrics summary | `admin/page.tsx` | `GET /admin/metrics/summary` | mixed | ✅ | ✅ |
| Dashboard metrics | `pipeline/page.tsx` | `GET /admin/pipeline/dashboard-metrics` | mixed | ✅ | ✅ |
| Run comparison | `pipeline/page.tsx` | `GET /admin/pipeline/compare` | `stage_runs` | ✅ | ⚠️ inherits duplicate-row problem |
| OTEL export | `pipeline/page.tsx` | `POST .../export-otel` | — | ✅ | ✅ |
| Pause / resume / trigger | `pipeline/page.tsx` | `/pipeline/pause`,`/resume`,`/trigger`,`/paused` | Redis | ✅ | ✅ |
| Sources | `sources/page.tsx` | `GET /sources` | sources | ✅ | ✅ |
| **Data lineage** | — | — | — | partial | ❌ **no UI at all** (see §4) |

---

## 2. Confirmed wiring defects

### W1 — Stage inspector 500s on 89% of stage volume

```text
Frontend: pipeline/page.tsx:1272 — GET /admin/pipeline/runs/{run_id}/stages/{stage}
Backend:  admin.py:575 — select(StageRunModel).where(run_id==, stage==).scalar_one_or_none()
Expected: stage detail for `crawling`
Actual:   MultipleResultsFound → HTTP 500 (reproduced in production)
Impact:   The two highest-volume stages cannot be inspected at all.
Fix:      Return an aggregate + paginated children; never LIMIT 1.
```

### W2 — Run summary reads a metadata shape that is never produced

```text
Frontend: renders `summary` verbatim in the run list
Backend:  admin.py:488-497 — meta.get("articles_ingested"), meta.get("stories_created"), …
Expected: "Ingested 42 articles · Created 3 stories"
Actual:   "Completed (no actions)" — the keys are nested under metrics/output
Impact:   Run history answers none of its intended questions.
Fix:      Read meta["metrics"] → meta["output"] → top level; support inputs/input.
```

### W3 — Four DAG nodes map to stages that never emit stage runs

```text
Frontend: FRONTEND_TO_BACKEND_STAGES (page.tsx:91) → STAGE_A, STAGE_B, SYNTHESIS, FEEDBACK
Backend:  no stage_runs rows for any of their mapped names
Expected: synthesis telemetry in the drawer
Actual:   selector falls back to backendStages[0] → 404 detail, [] logs
Impact:   "No logs available" on synthesis; four nodes are decorative.
Fix:      Emit stage_runs for synthesis, or read pipeline_traces (which has it).
```

### W4 — Live stages exist in the backend but not in the frontend map

```text
Backend:  event_extraction (899 rows, 886 failed), ingestion_gnews (157), entity_extraction (6)
Frontend: absent from BACKEND_TO_FRONTEND_STAGE
Actual:   mapBackendToFrontendStage falls through to .toUpperCase(), matching no PIPELINE_STAGES entry
Impact:   The worst-performing stage in the pipeline (98.6% failure) is invisible.
Fix:      Add the mappings; add DAG nodes for extraction.
```

### W5 — `completed` status renders unstyled

```text
Backend:  stage_runs.status ∈ {success, completed, failed, skipped, running}
Frontend: STATUS_CONFIG (page.tsx:56) has no `completed` key
Actual:   1,128 rows render with undefined icon/label
Fix:      Normalise on the write side to one terminal value; map both on read.
```

### W6 — Costs are wired end-to-end but the value is always zero

```text
Frontend: costs/page.tsx renders `cost_usd`
Backend:  llm_traces.cost_usd — 0 for 17,333/17,333 rows
Root:     trace.py LLM_PRICING lacks every production model AND overwrites the
          gateway's correctly computed cost in a finally block
Impact:   Cost observability does not exist.
```

### W7 — SSE token is sent but never validated

```text
Frontend: page.tsx:144 — ?token=${token} appended to the SSE URL
Backend:  stream_stage_run_logs / stream_pipeline_status accept no auth dependency
Impact:   Unauthenticated log access; token leaked into access logs for nothing.
```

---

## 3. Backend endpoints with no frontend consumer

Verified by searching the whole admin app for each path.

| Endpoint | Response model | Confidence dead |
|---|---|---|
| `GET /admin/users` | `list[UserResponse]` | High |
| `GET /admin/stats` | — | High |
| `GET /admin/timeline/{story_id}` | `TimelineDebuggerResponse` | High |
| `GET /admin/review/queue` | `HumanReviewQueueResponse` | High — backed by `human_reviews`, **0 rows** |
| `POST /admin/pipeline/purge` | — | High |
| `GET /admin/articles/{article_id}/trace` | — | **High — and it is the lineage endpoint** |
| `GET /admin/pipeline/story/{id}/traces` | — | High — the synthesis data the UI lacks |
| `GET /admin/prompt-analytics` | `list[PromptAnalyticsResponse]` | High |
| `GET /admin/model-benchmarks` | `list[ModelBenchmarkResponse]` | High |
| `GET /admin/context-analytics` | `list[ContextAnalyticsResponse]` | High |
| `GET /admin/cache-effectiveness` | `list[CacheEffectivenessResponse]` | High |
| `GET /admin/hallucination-analytics` | `HallucinationAnalyticsResponse` | High |
| `GET /admin/cost-forecasting` | `CostForecastingResponse` | High — would render zeros anyway |
| `GET /admin/provider-sla` | `list[ProviderSLAResponse]` | High |

**13 of 49 admin endpoints (27%) have no consumer**, including seven fully
modelled analytics endpoints. Two of them —
`/admin/articles/{id}/trace` and `/admin/pipeline/story/{id}/traces` — are
exactly the capabilities the audit brief asks for and that the UI is missing.
They should be **wired up, not deleted**.

---

## 4. Data lineage

The brief asks whether an engineer can follow
`RSS URL → Article → Embedding → Entity → Event → Story → Summary`.

**Backend:** `GET /admin/articles/{article_id}/trace` exists and is the intended
mechanism. `stage_runs.metadata.lineage` is populated for the collector-based
stages, and `llm_traces.story_id`/`article_id` provide partial links.

**Frontend:** no page, component, or call references it. Lineage is unreachable
from the UI.

**Gaps even if wired:**
- `llm_traces.story_id` is populated on only **3%** of rows.
- `crawling` writes no lineage, breaking the URL → Article link for the busiest stage.
- Synthesis lineage lives in `pipeline_traces`, which the UI never reads.

---

## 5. Real-time behaviour

| Property | State |
|---|---|
| Transport | **SSE**, not WebSocket (`useSSE.ts`, `EventSource`) |
| Event source | Redis Streams (`/pipeline/stream`), Redis pub/sub (logs) |
| Reconnect | Browser `EventSource` default only; `last_id` param exists for replay |
| State reconciliation after reconnect | ⚠️ relies on React Query refetch, not on `last_id` |
| Polling alongside SSE | ⚠️ yes — `refetchInterval: 4000` on stage details while `running` |
| Duplicate events | Not de-duplicated client-side |
| Subscription cleanup | `EventSource.close()` on unmount ✅ |
| Auth | ❌ none (W7) |

The `last_id` cursor is implemented on the backend and **not used by the
frontend**, so a 30-second disconnect loses events rather than replaying them.
Recovery depends on the 4-second poll, which means the stated requirement — clean
recovery after a 30-second disconnect — is met only accidentally and only for
polled views.

---

## 6. Type safety

`api-client.ts` exports a bare axios instance. Every call site uses
`useQuery<any>` or `res.data` untyped. There are **no shared response
interfaces**, so:

- W2 (wrong metadata keys) could not be caught at build time
- W5 (unmapped status value) could not be caught at build time
- A backend field rename would fail silently at runtime

This is the root enabler of most defects in this document.
