"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useSSE } from "@/lib/useSSE";
import {
  GitBranch,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  SkipForward,
  Loader2,
  Play,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

const PIPELINE_STAGES = [
  { id: "INGESTION_RSS", label: "RSS Ingestion", group: "ingestion" },
  { id: "INGESTION_GNEWS", label: "GNews API", group: "ingestion" },
  { id: "DEDUPLICATION", label: "Deduplication", group: "processing" },
  { id: "NLP_ANALYSIS", label: "NLP Analysis", group: "processing" },
  { id: "ENTITY_LINKING", label: "Entity Linking", group: "processing" },
  { id: "CLUSTERING", label: "Story Clustering", group: "processing" },
  { id: "SUMMARIZATION", label: "AI Summarization", group: "generation" },
  { id: "TIMELINE", label: "Timeline Builder", group: "generation" },
  { id: "CONTRADICTION", label: "Contradiction Engine", group: "generation" },
  { id: "SEARCH_INDEXING", label: "Search Indexing", group: "output" },
];

const GROUP_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  ingestion: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400" },
  processing: { bg: "bg-primary/10", border: "border-primary/30", text: "text-primary" },
  generation: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400" },
  output: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400" },
};

const STATUS_CONFIG: Record<string, { icon: React.ElementType; cls: string; label: string }> = {
  success: { icon: CheckCircle2, cls: "text-emerald-400", label: "Success" },
  failed: { icon: XCircle, cls: "text-red-400", label: "Failed" },
  running: { icon: Loader2, cls: "text-primary", label: "Running" },
  pending: { icon: Clock, cls: "text-slate-500", label: "Pending" },
  skipped: { icon: SkipForward, cls: "text-slate-650", label: "Skipped" },
};

function StageNode({
  stage,
  stageStatus,
}: {
  stage: (typeof PIPELINE_STAGES)[0];
  stageStatus?: string;
}) {
  const status = stageStatus ?? "pending";
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  const group = GROUP_COLORS[stage.group];

  return (
    <div
      className={`flex flex-col gap-1 p-4 rounded-xl border ${group.border} ${group.bg} glass-hover transition-all`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`text-xs font-semibold ${group.text}`}>
          {stage.label}
        </span>
        <Icon className={`w-4 h-4 shrink-0 ${cfg.cls} ${status === "running" ? "animate-spin" : ""}`} />
      </div>
      <span className="text-[10px] font-mono text-slate-600">{stage.id}</span>
      <span className={`text-[10px] font-semibold ${cfg.cls}`}>{cfg.label}</span>
    </div>
  );
}

export default function PipelinePage() {
  const { lastEvent, events, status: sseStatus } = useSSE();

  const { data: pipelineStatus, isLoading, refetch } = useQuery({
    queryKey: ["pipeline-status"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/pipeline/status");
      return res.data;
    },
    refetchInterval: 10000,
  });

  const triggerMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/sources/trigger-ingestion");
    },
    onSuccess: () => toast.success("Ingestion pipeline queued!"),
    onError: () => toast.error("Failed to trigger ingestion."),
  });

  // Build a map of stage → latest status from SSE events
  const stageStatusMap: Record<string, string> = {};
  [...events].reverse().forEach((ev) => {
    if (!stageStatusMap[ev.stage]) {
      stageStatusMap[ev.stage] = ev.status;
    }
  });

  // Merge with backend data (backend takes priority for non-running stages)
  if (pipelineStatus?.stages) {
    for (const stg of pipelineStatus.stages) {
      if (stg.status !== "running") {
        stageStatusMap[stg.stage] = stg.status;
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <GitBranch className="w-6 h-6 text-primary" />
            Pipeline DAG
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Real-time story intelligence pipeline visualization
          </p>
        </div>
        <div className="flex gap-2">
          <button
            id="pipeline-refresh-btn"
            onClick={() => refetch()}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl glass border border-border text-xs text-slate-400 hover:text-slate-200 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            id="pipeline-trigger-btn"
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary hover:bg-primary/90 text-white text-xs font-semibold transition-all shadow-lg shadow-primary/20 disabled:opacity-50"
          >
            {triggerMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            Trigger Ingestion
          </button>
        </div>
      </div>

      {/* SSE status bar */}
      <div className="glass rounded-xl px-4 py-3 flex items-center gap-3">
        <div
          className={`w-2 h-2 rounded-full shrink-0 ${
            sseStatus === "connected"
              ? "bg-emerald-500 animate-pulse"
              : sseStatus === "connecting"
              ? "bg-amber-400 animate-pulse"
              : "bg-slate-655"
          }`}
        />
        <span className="text-xs text-slate-400">
          Live SSE Stream:{" "}
          <span className="font-mono capitalize text-slate-350">{sseStatus}</span>
        </span>
        {lastEvent && (
          <>
            <span className="text-slate-700">·</span>
            <span className="text-xs text-slate-500 font-mono">
              Last: <span className="text-slate-400">{lastEvent.stage}</span> →{" "}
              <span
                className={
                  lastEvent.status === "success"
                    ? "text-emerald-400"
                    : lastEvent.status === "failed"
                    ? "text-red-405"
                    : "text-primary"
                }
              >
                {lastEvent.status}
              </span>
            </span>
          </>
        )}
      </div>

      {/* Pipeline DAG */}
      <div className="glass rounded-2xl p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {PIPELINE_STAGES.map((stage) => (
            <StageNode
              key={stage.id}
              stage={stage}
              stageStatus={stageStatusMap[stage.id]}
            />
          ))}
        </div>

        {/* Group legend */}
        <div className="mt-6 pt-4 border-t border-border flex flex-wrap gap-4">
          {Object.entries(GROUP_COLORS).map(([group, colors]) => (
            <div key={group} className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-sm border ${colors.border} ${colors.bg}`} />
              <span className={`text-[10px] font-semibold capitalize ${colors.text}`}>{group}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent events table */}
      <div className="glass rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-slate-200">
            Recent Stage Transitions
          </h2>
          <span className="text-xs text-slate-500">{events.length} events received</span>
        </div>

        {events.length === 0 ? (
          <div className="text-center py-8">
            <AlertTriangle className="w-8 h-8 text-slate-700 mx-auto mb-2" />
            <p className="text-xs text-slate-655">
              No events yet. Trigger an ingestion run to see live updates.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 pr-4 text-slate-500 font-semibold">Stage</th>
                  <th className="text-left py-2 pr-4 text-slate-500 font-semibold">Status</th>
                  <th className="text-left py-2 pr-4 text-slate-500 font-semibold">Run ID</th>
                  <th className="text-right py-2 text-slate-500 font-semibold">Duration</th>
                </tr>
              </thead>
              <tbody>
                {events.slice(0, 50).map((ev, i) => {
                  const cfg = STATUS_CONFIG[ev.status] ?? STATUS_CONFIG.pending;
                  const Icon = cfg.icon;
                  return (
                    <tr key={i} className="border-b border-border/50 hover:bg-white/2 transition-colors">
                      <td className="py-2 pr-4 font-mono text-slate-300">{ev.stage}</td>
                      <td className="py-2 pr-4">
                        <span className={`flex items-center gap-1.5 ${cfg.cls}`}>
                          <Icon className={`w-3 h-3 ${ev.status === "running" ? "animate-spin" : ""}`} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="py-2 pr-4 font-mono text-slate-600 text-[10px]">
                        {ev.run_id?.slice(0, 12)}…
                      </td>
                      <td className="py-2 text-right font-mono text-slate-500">
                        {ev.duration_ms ? `${ev.duration_ms}ms` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
