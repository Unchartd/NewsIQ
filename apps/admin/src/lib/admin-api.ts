/**
 * Typed accessors for the admin API.
 *
 * `apiClient` is a bare axios instance, so every call site was written as
 * `useQuery<any>` and `res.data`. That is how a backend field rename or an
 * unhandled status value reached production silently — the wrong-metadata-key
 * and unmapped-`completed` bugs were both invisible at build time.
 *
 * These wrappers exist so a call site names a return type it cannot get wrong.
 * They are intentionally thin: no caching, no retries, no error translation —
 * React Query already owns all three.
 */

import apiClient from "@/lib/api-client";
import type {
  ArticleLineage,
  PipelineRunSummary,
  PipelineStatus,
  StageDetail,
} from "@/lib/api-types";

export async function fetchPipelineRuns(): Promise<PipelineRunSummary[]> {
  const res = await apiClient.get<PipelineRunSummary[]>("/admin/pipeline/runs");
  return res.data;
}

export async function fetchPipelineStatus(runId?: string | null): Promise<PipelineStatus> {
  const url = runId
    ? `/admin/pipeline/status?run_id=${encodeURIComponent(runId)}`
    : "/admin/pipeline/status";
  const res = await apiClient.get<PipelineStatus>(url);
  return res.data;
}

export async function fetchStageDetail(
  runId: string,
  stage: string,
  opts: { limit?: number; offset?: number } = {},
): Promise<StageDetail> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set("limit", String(opts.limit));
  if (opts.offset != null) params.set("offset", String(opts.offset));
  const query = params.toString();
  const res = await apiClient.get<StageDetail>(
    `/admin/pipeline/runs/${runId}/stages/${encodeURIComponent(stage)}${query ? `?${query}` : ""}`,
  );
  return res.data;
}

export async function fetchStageLogs(runId: string, stage: string): Promise<string[]> {
  const res = await apiClient.get<string[]>(
    `/admin/pipeline/runs/${runId}/stages/${encodeURIComponent(stage)}/logs`,
  );
  return res.data;
}

export async function fetchArticleLineage(articleId: string): Promise<ArticleLineage> {
  const res = await apiClient.get<ArticleLineage>(`/admin/articles/${articleId}/trace`);
  return res.data;
}
