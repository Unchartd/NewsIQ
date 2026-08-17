/**
 * Response shapes for the admin API.
 *
 * Why these are hand-written rather than generated: only 22 of the 49 admin
 * endpoints declare a `response_model`, and the ones where wiring bugs actually
 * occurred — stage detail, the run list, stage status — return plain dicts. An
 * OpenAPI generator emits `unknown` for exactly those, which is no better than
 * the `any` it would replace.
 *
 * Hand-written types drift, so they are guarded: `test_admin_response_contract.py`
 * builds each real response payload and asserts its keys against the interfaces
 * in this file. Adding a field to the backend without adding it here, or renaming
 * one, fails in CI rather than silently rendering `undefined`.
 *
 * The bugs this exists to prevent, both of which shipped and both of which are
 * compile-time errors now:
 *
 *   - the run summary read `articles_ingested` at the top level of stage
 *     metadata, where it has never appeared for any stage
 *   - `STATUS_CONFIG` had no `completed` key, so 1,128 stage runs rendered with
 *     no icon and no colour
 */

/** Terminal and in-flight states a stage run can hold.
 *
 * `completed` is historical: the trace collector wrote it where StageSpan writes
 * `success`. It still exists on 1,128 rows, so any exhaustive switch must handle
 * it. New writes use `success`.
 */
export type StageStatus =
  | "pending"
  | "running"
  | "success"
  | "completed"
  | "failed"
  | "skipped"
  | "retrying";

export type RunStatus = "running" | "success" | "failed";

/** Collector metadata attached to a stage run.
 *
 * The collector nests everything; `clustering_incremental` writes a hand-rolled
 * `inputs`/`outputs` shape instead. Both spellings are declared because both
 * exist in the database — reading only the singular form is what made every run
 * summary say "Completed (no actions)".
 */
export interface StageMetadata {
  input?: Record<string, unknown>;
  inputs?: Record<string, unknown>;
  output?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  metrics?: Record<string, number | string>;
  lineage?: unknown[];
  warnings?: unknown[];
  errors?: unknown[];
  artifacts?: Record<string, unknown>;
  resources?: Record<string, unknown>;
  /** Snapshotted on failure so logs survive the 24h Redis TTL. */
  logs_tail?: string[];
  error_traceback?: string;
  [key: string]: unknown;
}

export interface LlmTrace {
  id: string;
  provider: string | null;
  model: string | null;
  system_prompt: string | null;
  user_prompt: string | null;
  response_text: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  /** Null when the model has no confirmed rate — distinct from a free call. */
  cost_usd: number | null;
  status: string;
  error: string | null;
  parent_llm_trace_id: string | null;
}

/** One execution of a stage within a run. A stage is not unique per run. */
export interface StageAttempt {
  id: string;
  status: StageStatus;
  started_at: string | null;
  completed_at: string | null;
  latency_ms: number | null;
  retry_count: number;
  error: string | null;
  error_type: string | null;
  article_id: string | null;
  story_id: string | null;
}

/**
 * Stage detail. When a stage ran many times — `crawling` reached 2,079 in one
 * run — the top-level fields describe the stage as a whole and `is_aggregated`
 * is true.
 */
export interface StageDetail {
  id: string;
  run_id: string;
  trace_id: string;
  stage: string;
  /** Worst status across attempts, so one failure is never hidden by successes. */
  status: StageStatus;
  started_at: string | null;
  completed_at: string | null;
  /** Summed across attempts when aggregated, not the latency of one attempt. */
  latency_ms: number | null;
  retry_count: number;
  error: string | null;
  error_type: string | null;
  story_id: string | null;
  article_id: string | null;
  metadata: StageMetadata;
  llm_traces: LlmTrace[];
  llm_traces_truncated: boolean;
  rca_report: RcaReport | null;
  attempt_count: number;
  status_counts: Partial<Record<StageStatus, number>>;
  is_aggregated: boolean;
  aggregate: StageAggregate;
  attempts: StageAttempt[];
  attempts_page: { limit: number; offset: number; total: number };
}

export interface StageAggregate {
  total_latency_ms: number | null;
  avg_latency_ms: number | null;
  max_latency_ms: number | null;
  first_started_at: string | null;
  last_completed_at: string | null;
  total_retries: number;
}

export interface RcaReport {
  category: string;
  confidence: number;
  description: string;
  remediation: string;
}

/** A row in the run history list. */
export interface PipelineRunSummary {
  id: string;
  trace_id: string;
  trigger: string;
  pipeline_type: string;
  status: RunStatus;
  started_at: string | null;
  completed_at: string | null;
  total_latency_ms: number | null;
  error: string | null;
  /** Derived from stage metrics; never the bare word "Completed". */
  summary: string;
  metadata_payload: Record<string, unknown> | null;
}

/** Article lineage: URL -> article -> story -> summary. */
export interface ArticleLineage {
  article: {
    id: string;
    url: string;
    title: string | null;
    source_id: string | null;
    crawled_at: string | null;
    published_at: string | null;
    content_length: number;
    event_extraction_status: string | null;
  };
  story: {
    id: string;
    headline: string | null;
    status: string | null;
    one_line_summary: string | null;
  } | null;
  stages: LineageStage[];
  story_stages: LineageStage[];
  llm_traces: Array<
    Pick<
      LlmTrace,
      "id" | "provider" | "model" | "input_tokens" | "output_tokens" | "cost_usd" | "latency_ms" | "status" | "error"
    > & { stage: string }
  >;
}

export interface LineageStage {
  id: string;
  run_id: string;
  stage: string;
  status: StageStatus;
  started_at: string | null;
  completed_at: string | null;
  latency_ms: number | null;
  error: string | null;
  metadata: StageMetadata;
}

/** Live pipeline status driving the DAG. */
export interface PipelineStatus {
  run_id: string | null;
  status: RunStatus | null;
  stages: Array<{
    stage: string;
    status: StageStatus;
    started_at?: string | null;
    completed_at?: string | null;
    latency_ms?: number | null;
    error?: string | null;
  }>;
  [key: string]: unknown;
}
