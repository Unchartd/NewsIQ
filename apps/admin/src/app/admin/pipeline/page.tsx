"use client";

import { useQuery, useMutation } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useSSE } from "@/lib/useSSE";
import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  GitBranch,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  SkipForward,
  Loader2,
  Play,
  Pause,
  AlertTriangle,
  Info,
  Terminal,
  ArrowRightLeft,
  AlertOctagon,
  BarChart3,
  RotateCw,
  Copy,
  Check,
} from "lucide-react";
import { toast } from "sonner";

// Frontend Node configuration
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
  processing: { bg: "bg-indigo-500/10", border: "border-indigo-500/30", text: "text-indigo-400" },
  generation: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400" },
  output: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400" },
};

const STATUS_CONFIG: Record<string, { icon: React.ElementType; cls: string; label: string; iconCls?: string }> = {
  success: { icon: CheckCircle2, cls: "text-emerald-400", label: "Success" },
  failed: { icon: XCircle, cls: "text-red-400", label: "Failed" },
  running: { icon: Loader2, cls: "text-blue-400", iconCls: "animate-spin", label: "Running" },
  pending: { icon: Clock, cls: "text-slate-500", label: "Pending" },
  skipped: { icon: SkipForward, cls: "text-slate-650", label: "Skipped" },
  retrying: { icon: RotateCw, cls: "text-amber-400", iconCls: "animate-pulse", label: "Retrying" },
};

// Stage normalization helper mappings
const BACKEND_TO_FRONTEND_STAGE: Record<string, string> = {
  ingestion_rss: "INGESTION_RSS",
  ingestion_gnews: "INGESTION_GNEWS",
  crawling: "INGESTION_RSS",
  deduplication: "DEDUPLICATION",
  embedding: "DEDUPLICATION",
  event_extraction: "NLP_ANALYSIS",
  entity_extraction: "NLP_ANALYSIS",
  entity_linking: "ENTITY_LINKING",
  clustering_batch: "CLUSTERING",
  clustering_incremental: "CLUSTERING",
  timeline_generation: "TIMELINE",
  contradiction_detection: "CONTRADICTION",
  summary_generation: "SUMMARIZATION",
  difference_engine: "SUMMARIZATION",
  indexing: "SEARCH_INDEXING",
};

const FRONTEND_TO_BACKEND_STAGES: Record<string, string[]> = {
  INGESTION_RSS: ["ingestion_rss", "crawling"],
  INGESTION_GNEWS: ["ingestion_gnews"],
  DEDUPLICATION: ["deduplication", "embedding"],
  NLP_ANALYSIS: ["event_extraction", "entity_extraction"],
  ENTITY_LINKING: ["entity_linking"],
  CLUSTERING: ["clustering_batch", "clustering_incremental"],
  TIMELINE: ["timeline_generation"],
  CONTRADICTION: ["contradiction_detection"],
  SUMMARIZATION: ["summary_generation", "difference_engine"],
  SEARCH_INDEXING: ["indexing"],
};

function mapBackendToFrontendStage(backendStage: string): string {
  const norm = (backendStage || "").toLowerCase().trim();
  return BACKEND_TO_FRONTEND_STAGE[norm] || backendStage.toUpperCase();
}

function getBackendStagesForFrontend(frontendStage: string): string[] {
  return FRONTEND_TO_BACKEND_STAGES[frontendStage] || [frontendStage.toLowerCase()];
}

// Sub-component for Live log streaming
function LiveLogViewer({ runId, stage, isRunning }: { runId: string; stage: string; isRunning: boolean }) {
  const [logs, setLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement | null>(null);
  const prevRunAndStageRef = useRef<string>("");

  useEffect(() => {
    const currentKey = `${runId}:${stage}`;
    if (prevRunAndStageRef.current !== currentKey) {
      setLogs([]);
      prevRunAndStageRef.current = currentKey;
    }

    if (!runId || !stage) return;

    let eventSource: EventSource | null = null;

    const fetchInitialLogs = async () => {
      try {
        const res = await apiClient.get(`/admin/pipeline/runs/${runId}/stages/${stage}/logs`);
        setLogs(res.data);
      } catch (err) {
        // Safe fallback
      }
    };

    fetchInitialLogs();

    if (isRunning) {
      const token = typeof window !== "undefined" ? localStorage.getItem("newsiq_admin_token") : null;
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";
      const sseUrl = `${apiBase}/admin/pipeline/runs/${runId}/stages/${stage}/logs/stream${token ? `?token=${token}` : ""}`;

      eventSource = new EventSource(sseUrl);
      eventSource.onmessage = (event) => {
        setLogs((prev) => {
          if (prev.includes(event.data)) return prev;
          return [...prev, event.data];
        });
      };
      eventSource.onerror = () => {
        eventSource?.close();
      };
    }

    return () => {
      eventSource?.close();
    };
  }, [runId, stage, isRunning]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="bg-slate-950 font-mono text-[11px] text-emerald-400 p-4 rounded-xl border border-slate-800 overflow-y-auto space-y-1 shadow-inner flex-1 min-h-0">
      {logs.length === 0 ? (
        <div className="text-slate-600 italic">No logs generated for this stage yet.</div>
      ) : (
        logs.map((log, index) => (
          <div key={index} className="whitespace-pre-wrap leading-relaxed border-l-2 border-emerald-950 pl-2">
            {log}
          </div>
        ))
      )}
      <div ref={logsEndRef} />
    </div>
  );
}

// Stage Node UI representation
function StageNode({
  stage,
  stageStatus,
  onClick,
  isActive,
}: {
  stage: (typeof PIPELINE_STAGES)[0];
  stageStatus?: string;
  onClick: () => void;
  isActive: boolean;
}) {
  const status = stageStatus ?? "pending";
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  const Icon = cfg.icon;
  const colors = GROUP_COLORS[stage.group];

  let stateCls = "bg-slate-900/40 border-slate-800/80 text-slate-400 hover:border-slate-700";
  if (status === "running") {
    stateCls = "bg-blue-950/30 border-blue-500 text-blue-400 animate-pulse ring-1 ring-blue-500/20";
  } else if (status === "success") {
    stateCls = "bg-emerald-950/20 border-emerald-500/40 text-emerald-400 hover:border-emerald-500/80";
  } else if (status === "failed") {
    stateCls = "bg-red-950/20 border-red-500/40 text-red-400 hover:border-red-500/80";
  } else if (status === "skipped") {
    stateCls = "bg-slate-900/10 border-slate-800/40 text-slate-500 opacity-60";
  } else if (status === "retrying") {
    stateCls = "bg-amber-950/30 border-amber-500 text-amber-400 animate-pulse hover:border-amber-400";
  }

  if (isActive) {
    stateCls += " ring-2 ring-primary ring-offset-2 ring-offset-slate-950";
  }

  return (
    <button
      onClick={onClick}
      className={`flex flex-col gap-1 p-4 rounded-xl border text-left transition-all duration-200 glass-hover ${stateCls}`}
    >
      <div className="flex items-center justify-between gap-2 w-full">
        <span className="text-[12px] font-bold tracking-tight">
          {stage.label}
        </span>
        <Icon className={`w-3.5 h-3.5 shrink-0 ${cfg.iconCls || ""}`} />
      </div>
      <span className="text-[9px] font-mono text-slate-600 uppercase mt-0.5">{stage.id}</span>
      <div className="flex items-center gap-1.5 mt-2">
        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-black/30">
          {status}
        </span>
      </div>
    </button>
  );
}

export default function PipelinePage() {
  const { lastEvent, events, status: sseStatus } = useSSE();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [wasAutoPinned, setWasAutoPinned] = useState(false);

  // Active stage drawer states
  const [activeStageId, setActiveStageId] = useState<string | null>(null); // e.g. "NLP_ANALYSIS"
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const closeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [selectedBackendStage, setSelectedBackendStage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "logs" | "inputs" | "outputs" | "errors" | "metrics" | "retries">("overview");
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // Lock body scroll when drawer is open
  useEffect(() => {
    if (isDrawerOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isDrawerOpen]);

  // Clean up timer on unmount and track mount state
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
    return () => {
      if (closeTimeoutRef.current) {
        clearTimeout(closeTimeoutRef.current);
      }
    };
  }, []);

  const handleOpenDrawer = (stageId: string) => {
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current);
      closeTimeoutRef.current = null;
    }
    setActiveStageId(stageId);
    setIsDrawerOpen(true);
    setActiveTab("overview");
    if (!selectedRunId && pipelineStatus?.run_id) {
      setSelectedRunId(pipelineStatus.run_id);
      setWasAutoPinned(true);
    }
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current);
    }
    closeTimeoutRef.current = setTimeout(() => {
      setActiveStageId(null);
      setSelectedBackendStage(null);
      if (wasAutoPinned) {
        setSelectedRunId(null);
        setWasAutoPinned(false);
      }
      closeTimeoutRef.current = null;
    }, 300);
  };

  const { data: pipelineStatus, isLoading, refetch } = useQuery<any>({
    queryKey: ["pipeline-status", selectedRunId],
    queryFn: async () => {
      const url = selectedRunId
        ? `/admin/pipeline/status?run_id=${selectedRunId}`
        : "/admin/pipeline/status";
      const res = await apiClient.get(url);
      return res.data;
    },
    refetchInterval: (query) => {
      const data = query.state.data;
      return !selectedRunId || !data || data.status === "running" ? 6000 : false;
    },
  });

  const { data: metricsSummary } = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/metrics/summary");
      return res.data;
    },
    refetchInterval: 15000,
  });

  const { data: pipelineHistory, refetch: refetchHistory } = useQuery({
    queryKey: ["pipeline-runs"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/pipeline/runs");
      return res.data;
    },
  });

  const { data: pausedData, refetch: refetchPaused } = useQuery({
    queryKey: ["pipeline-paused"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/pipeline/paused");
      return res.data;
    },
    refetchInterval: 10000, // refresh every 10s
  });

  const togglePauseMutation = useMutation({
    mutationFn: async () => {
      const isPaused = !!pausedData?.paused;
      const endpoint = isPaused ? "/admin/pipeline/resume" : "/admin/pipeline/pause";
      const res = await apiClient.post(endpoint);
      return res.data;
    },
    onSuccess: (resData) => {
      toast.success(resData.message);
      refetchPaused();
    },
    onError: () => {
      toast.error("Failed to update pipeline status.");
    },
  });

  const triggerMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/sources/trigger-ingestion");
    },
    onSuccess: () => {
      toast.success("Ingestion pipeline triggered!");
      setTimeout(() => {
        refetch();
        refetchHistory();
      }, 1000);
    },
    onError: () => toast.error("Failed to trigger ingestion."),
  });

  const replayStageMutation = useMutation({
    mutationFn: async ({ storyId, stageName }: { storyId: string; stageName: string }) => {
      const res = await apiClient.post(`/admin/replay/${storyId}/${stageName}`);
      return res.data;
    },
    onSuccess: () => {
      toast.success("Stage replay queued successfully!");
      refetch();
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || "Failed to trigger stage replay.");
    },
  });

  const replayFullMutation = useMutation({
    mutationFn: async (storyId: string) => {
      const res = await apiClient.post(`/admin/replay/${storyId}`);
      return res.data;
    },
    onSuccess: () => {
      toast.success("Full story intelligence replay queued!");
      refetch();
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || "Failed to trigger full replay.");
    },
  });

  // When active stage changes, match first available backend stage
  useEffect(() => {
    if (!activeStageId || !pipelineStatus?.stages) {
      setSelectedBackendStage(null);
      return;
    }
    const backendStages = getBackendStagesForFrontend(activeStageId);
    const available = pipelineStatus.stages.filter((s: any) => backendStages.includes(s.stage));
    if (available.length > 0) {
      setSelectedBackendStage(available[0].stage);
    } else {
      setSelectedBackendStage(backendStages[0]);
    }
  }, [activeStageId, pipelineStatus]);

  // Fetch detailed telemetry for active stage run
  const { data: stageDetails, isLoading: isLoadingDetails } = useQuery<any>({
    queryKey: ["stage-details", pipelineStatus?.run_id, selectedBackendStage],
    queryFn: async () => {
      if (!pipelineStatus?.run_id || !selectedBackendStage) return null;
      const res = await apiClient.get(`/admin/pipeline/runs/${pipelineStatus.run_id}/stages/${selectedBackendStage}`);
      return res.data;
    },
    enabled: !!pipelineStatus?.run_id && !!selectedBackendStage,
    refetchInterval: (query) => {
      const data = query.state.data;
      return !data || data.status === "running" ? 4000 : false;
    },
  });

  // Build real-time map of stage -> status
  const stageStatusMap: Record<string, string> = {};
  if (!selectedRunId) {
    [...events].reverse().forEach((ev) => {
      const frontendStageId = mapBackendToFrontendStage(ev.stage);
      stageStatusMap[frontendStageId] = ev.status;
    });
  }

  // Merge with pipeline database status
  if (pipelineStatus?.stages) {
    for (const stg of pipelineStatus.stages) {
      const frontendStageId = mapBackendToFrontendStage(stg.stage);
      if (!selectedRunId || stageStatusMap[frontendStageId] !== "running") {
        stageStatusMap[frontendStageId] = stg.status;
      }
    }
  }

  // Calculate current active running stage (if any)
  const runningStageName = Object.entries(stageStatusMap).find(([_, stat]) => stat === "running")?.[0];

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  return (
    <div className="space-y-6 text-slate-100 font-sans pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2 tracking-tight text-white">
            <GitBranch className="w-6 h-6 text-primary" />
            Pipeline Observability
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time stage profiling, log streaming, and telemetry inspector.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {selectedRunId && (
            <button
              onClick={() => setSelectedRunId(null)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-white transition-all"
            >
              Clear Selected Run (Live Mode)
            </button>
          )}
          <button
            onClick={() => togglePauseMutation.mutate()}
            disabled={togglePauseMutation.isPending}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all border ${
              pausedData?.paused
                ? "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/30 animate-pulse"
                : "bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/30"
            }`}
          >
            {togglePauseMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : pausedData?.paused ? (
              <>
                <Play className="w-3.5 h-3.5" />
                Resume Pipeline
              </>
            ) : (
              <>
                <Pause className="w-3.5 h-3.5" />
                Pause Pipeline
              </>
            )}
          </button>
          <button
            id="pipeline-refresh-btn"
            onClick={() => {
              refetch();
              refetchPaused();
              refetchHistory();
            }}
            disabled={isLoading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl glass border border-slate-850 text-xs text-slate-400 hover:text-slate-200 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button
            id="pipeline-trigger-btn"
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending || !!selectedRunId}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary hover:bg-primary/95 text-white text-xs font-semibold transition-all shadow-lg shadow-primary/20 disabled:opacity-40"
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

      {pausedData?.paused && (
        <div className="flex items-center gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          <div>
            <span className="font-semibold text-white">Pipeline suspended:</span> Background ingestion, embedding, event extraction, and clustering tasks are currently paused.
          </div>
        </div>
      )}

      {/* Top Banner Real-Time Event Stream Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">SSE Stream</span>
          <div className="flex items-center gap-2 mt-1">
            <div
              className={`w-2 h-2 rounded-full shrink-0 ${
                sseStatus === "connected"
                  ? "bg-emerald-500 animate-pulse"
                  : sseStatus === "connecting"
                  ? "bg-amber-400 animate-pulse"
                  : "bg-slate-650"
              }`}
            />
            <span className="text-xs font-bold font-mono uppercase text-slate-200">{sseStatus}</span>
          </div>
        </div>

        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Active Stage</span>
          <span className="text-xs font-bold truncate text-slate-200 mt-1 font-mono">
            {runningStageName ? PIPELINE_STAGES.find((s) => s.id === runningStageName)?.label : "Idle"}
          </span>
        </div>

        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Last Event</span>
          <span className="text-xs font-bold text-slate-200 truncate mt-1 font-mono">
            {lastEvent ? `${lastEvent.stage} (${lastEvent.status})` : "None"}
          </span>
        </div>

        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Queue Active/Wait</span>
          <span className="text-xs font-bold text-slate-200 mt-1 font-mono">
            {metricsSummary ? `${metricsSummary.active_jobs_count} / ${metricsSummary.waiting_jobs_count}` : "0 / 0"}
          </span>
        </div>

        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Total Runs</span>
          <span className="text-xs font-bold text-slate-200 mt-1 font-mono">
            {metricsSummary?.total_pipeline_runs ?? "0"}
          </span>
        </div>

        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">Total Tokens</span>
          <span className="text-xs font-bold text-slate-200 mt-1 font-mono">
            {metricsSummary?.total_tokens_consumed ? metricsSummary.total_tokens_consumed.toLocaleString() : "0"}
          </span>
        </div>

        <div className="glass rounded-xl p-3 flex flex-col justify-between border border-slate-850">
          <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider">LLM Cost</span>
          <span className="text-xs font-bold text-primary mt-1 font-mono">
            {metricsSummary?.total_llm_cost ? `$${metricsSummary.total_llm_cost.toFixed(4)}` : "$0.0000"}
          </span>
        </div>
      </div>

      {selectedRunId && (
        <div className="p-3 bg-indigo-950/20 border border-indigo-900/60 rounded-xl flex items-center justify-between text-xs text-indigo-300">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4" />
            <span>
              Viewing execution trace for historical Run ID: <strong className="font-mono text-white">{selectedRunId}</strong>
            </span>
          </div>
          <button
            onClick={() => setSelectedRunId(null)}
            className="px-2 py-1 rounded bg-indigo-900/60 hover:bg-indigo-900 text-[10px] font-bold text-white transition-colors"
          >
            Switch to Live
          </button>
        </div>
      )}

      {/* Pipeline DAG */}
      <div className="glass rounded-2xl p-6 border border-slate-850">
        <h2 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
          <span>Pipeline Stage execution DAG</span>
          {pipelineStatus?.status === "running" && (
            <span className="flex items-center gap-1.5 text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full font-normal animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
              Executing
            </span>
          )}
        </h2>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3.5">
          {PIPELINE_STAGES.map((stage) => (
            <StageNode
              key={stage.id}
              stage={stage}
              stageStatus={stageStatusMap[stage.id]}
              onClick={() => handleOpenDrawer(stage.id)}
              isActive={activeStageId === stage.id && isDrawerOpen}
            />
          ))}
        </div>

        {/* Legend */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 flex flex-wrap gap-4 items-center justify-between">
          <div className="flex flex-wrap gap-4">
            {Object.entries(GROUP_COLORS).map(([group, colors]) => (
              <div key={group} className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded border ${colors.border} ${colors.bg}`} />
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${colors.text}`}>{group}</span>
              </div>
            ))}
          </div>
          <span className="text-[10px] text-slate-500 font-mono">
            Click any stage card to inspect inputs, outputs, terminal logs, cost metrics, and trigger replays.
          </span>
        </div>
      </div>

      {/* Slide-over Detail Drawer */}
      {mounted && createPortal(
        <>
          <div
            className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-40 transition-opacity duration-300 ${
              isDrawerOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
            }`}
            onClick={handleCloseDrawer}
          />

          <div
            className={`fixed inset-y-0 right-0 w-[600px] bg-slate-950/75 backdrop-blur-xl border-l border-slate-800/80 shadow-2xl z-50 flex flex-col transform transition-transform duration-300 ease-in-out ${
              isDrawerOpen ? "translate-x-0" : "translate-x-full"
            }`}
          >
        {activeStageId && (
          <>
            {/* Header */}
            <div className="p-6 border-b border-slate-800 flex items-center justify-between bg-slate-950/30">
              <div>
                <span className="text-[9px] uppercase font-bold tracking-wider text-slate-500 font-mono">
                  {activeStageId} Detail
                </span>
                <h2 className="text-base font-bold text-white mt-1">
                  {PIPELINE_STAGES.find((s) => s.id === activeStageId)?.label || activeStageId}
                </h2>
              </div>
              <button
                onClick={handleCloseDrawer}
                className="p-1.5 rounded-lg bg-slate-800/60 hover:bg-slate-800 text-slate-400 hover:text-white transition-all text-xs font-mono"
              >
                ✕
              </button>
            </div>

            {/* Backend sub-stage selector (for combined front-end cards) */}
            {activeStageId && getBackendStagesForFrontend(activeStageId).length > 1 && (
              <div className="px-6 py-3 bg-slate-950/50 border-b border-slate-800 flex items-center gap-3">
                <span className="text-[11px] font-semibold text-slate-400">Sub-stage execution:</span>
                <div className="flex gap-1.5">
                  {getBackendStagesForFrontend(activeStageId).map((sub) => {
                    const isSel = selectedBackendStage === sub;
                    return (
                      <button
                        key={sub}
                        onClick={() => setSelectedBackendStage(sub)}
                        className={`text-[10px] font-mono px-2.5 py-1 rounded transition-colors ${
                          isSel
                            ? "bg-primary text-white font-bold"
                            : "bg-slate-800/80 text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {sub}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Tab navigation */}
            <div className="flex border-b border-slate-800 bg-slate-950/20 text-xs overflow-x-auto">
              {(
                [
                  { id: "overview", label: "Overview", icon: Info },
                  { id: "logs", label: "Logs", icon: Terminal },
                  { id: "inputs", label: "Inputs", icon: ArrowRightLeft },
                  { id: "outputs", label: "Outputs", icon: ArrowRightLeft },
                  { id: "errors", label: "Errors", icon: AlertOctagon },
                  { id: "metrics", label: "Metrics", icon: BarChart3 },
                ] as const
              ).map((tab) => {
                const TabIcon = tab.icon;
                const isSel = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={`flex items-center gap-1.5 px-4 py-3 border-b-2 font-semibold transition-all shrink-0 ${
                      isSel
                        ? "border-primary text-primary bg-primary/5"
                        : "border-transparent text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <TabIcon className="w-3.5 h-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Content Body */}
            <div
              className={`flex-1 p-6 overscroll-contain ${
                activeTab === "logs" || activeTab === "inputs" || activeTab === "outputs"
                  ? "flex flex-col min-h-0 overflow-hidden"
                  : "overflow-y-auto space-y-6"
              }`}
            >
              {isLoadingDetails ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-2 flex-1">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <span className="text-xs">Loading stage telemetry...</span>
                </div>
              ) : !stageDetails ? (
                <div className="text-center py-20 text-slate-500 text-xs flex-1">
                  No telemetry runs captured yet for <code className="text-slate-450">{selectedBackendStage}</code> in this run.
                </div>
              ) : (
                <>
                  {/* Overview Tab */}
                  {activeTab === "overview" && (
                    <div className="space-y-6">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/80">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">
                            Stage Status
                          </span>
                          <span className="text-xs font-bold text-white capitalize block mt-1">
                            {stageDetails.status}
                          </span>
                        </div>
                        <div className="bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/80">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">
                            Execution Latency
                          </span>
                          <span className="text-xs font-mono font-bold text-white block mt-1">
                            {stageDetails.latency_ms ? `${stageDetails.latency_ms.toFixed(2)} ms` : "—"}
                          </span>
                        </div>
                        <div className="bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/80">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">
                            Started At
                          </span>
                          <span className="text-xs font-mono text-white block mt-1">
                            {stageDetails.started_at
                              ? new Date(stageDetails.started_at).toLocaleString()
                              : "—"}
                          </span>
                        </div>
                        <div className="bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/80">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">
                            Completed At
                          </span>
                          <span className="text-xs font-mono text-white block mt-1">
                            {stageDetails.completed_at
                              ? new Date(stageDetails.completed_at).toLocaleString()
                              : "—"}
                          </span>
                        </div>
                      </div>

                      {/* Processed Metadata Summary */}
                      {stageDetails.metadata && Object.keys(stageDetails.metadata).length > 0 && (
                        <div className="p-4 bg-slate-900/40 rounded-xl border border-slate-800 space-y-2">
                          <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Process Summary</h4>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                            {Object.entries(stageDetails.metadata).map(([key, val]) => {
                              if (typeof val === "object" && val !== null) return null; // skip nested structures
                              const label = key.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
                              return (
                                <div key={key} className="flex justify-between py-1 border-b border-slate-850/60">
                                  <span className="text-slate-450">{label}</span>
                                  <span className="font-mono font-semibold text-slate-200">{String(val)}</span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Technical Identifiers */}
                      <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800 space-y-3.5 text-xs font-mono">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-500">Pipeline Run ID:</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-300 text-[11px]">{stageDetails.run_id}</span>
                            <button
                              onClick={() => handleCopy(stageDetails.run_id, "run")}
                              className="text-slate-500 hover:text-white transition-colors"
                            >
                              {copiedText === "run" ? (
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>

                        <div className="flex items-center justify-between">
                          <span className="text-slate-500">Trace ID:</span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-300 text-[11px]">{stageDetails.trace_id}</span>
                            <button
                              onClick={() => handleCopy(stageDetails.trace_id, "trace")}
                              className="text-slate-500 hover:text-white transition-colors"
                            >
                              {copiedText === "trace" ? (
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>

                        {stageDetails.story_id && (
                          <div className="flex items-center justify-between">
                            <span className="text-slate-500">Story ID:</span>
                            <div className="flex items-center gap-1.5">
                              <span className="text-slate-300 text-[11px]">{stageDetails.story_id}</span>
                              <button
                                onClick={() => handleCopy(stageDetails.story_id, "story")}
                                className="text-slate-500 hover:text-white transition-colors"
                              >
                                {copiedText === "story" ? (
                                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Replay Triggers */}
                      {stageDetails.story_id &&
                        ["entity_extraction", "contradiction_detection", "timeline_generation", "summary_generation"].includes(
                          selectedBackendStage || ""
                        ) && (
                          <div className="p-4 bg-primary/5 rounded-xl border border-primary/10 space-y-3">
                            <h4 className="text-xs font-bold text-primary uppercase tracking-wider">Replay Stage</h4>
                            <p className="text-[11px] text-slate-400">
                              Execute a localized hot-swap run of this specific pipeline stage for the story. This runs
                              independently using the stored payloads without triggering unrelated tasks.
                            </p>
                            <div className="flex gap-2">
                              <button
                                onClick={() =>
                                  replayStageMutation.mutate({
                                    storyId: stageDetails.story_id!,
                                    stageName: selectedBackendStage!,
                                  })
                                }
                                disabled={replayStageMutation.isPending}
                                className="px-3.5 py-1.5 bg-primary text-white text-[11px] font-bold rounded-lg hover:bg-primary/95 transition-all flex items-center gap-1.5 disabled:opacity-50"
                              >
                                {replayStageMutation.isPending ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <RotateCw className="w-3 h-3" />
                                )}
                                Replay Stage
                              </button>

                              <button
                                onClick={() => replayFullMutation.mutate(stageDetails.story_id!)}
                                disabled={replayFullMutation.isPending}
                                className="px-3.5 py-1.5 bg-slate-800 text-slate-300 text-[11px] font-bold rounded-lg hover:bg-slate-700 transition-all flex items-center gap-1.5 disabled:opacity-50"
                              >
                                {replayFullMutation.isPending ? (
                                  <Loader2 className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Play className="w-3 h-3" />
                                )}
                                Replay Full Story
                              </button>
                            </div>
                          </div>
                        )}
                    </div>
                  )}

                  {/* Logs Tab */}
                  {activeTab === "logs" && (
                    <div className="flex flex-col flex-1 min-h-0 space-y-3">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Terminal Log Output</span>
                        {stageDetails.status === "running" && (
                          <span className="flex items-center gap-1.5 text-blue-400 animate-pulse font-semibold">
                            <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                            Streaming
                          </span>
                        )}
                      </div>
                      <LiveLogViewer
                        runId={stageDetails.run_id}
                        stage={selectedBackendStage!}
                        isRunning={stageDetails.status === "running"}
                      />
                    </div>
                  )}

                  {/* Inputs Tab */}
                  {activeTab === "inputs" && (
                    <div className="flex flex-col flex-1 min-h-0 space-y-4">
                      <span className="text-xs text-slate-400 block">Factual inputs and configurations</span>
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-850 font-mono text-[11px] text-slate-300 overflow-auto flex-1 min-h-0">
                        <pre>
                          {JSON.stringify(
                            stageDetails.metadata?.inputs || 
                            (stageDetails.metadata && Object.keys(stageDetails.metadata).length > 0 && !("inputs" in stageDetails.metadata) && !("outputs" in stageDetails.metadata) ? stageDetails.metadata : { message: "No explicit input metadata recorded" }),
                            null,
                            2
                          )}
                        </pre>
                      </div>

                      {stageDetails.llm_traces?.length > 0 && (
                        <div className="space-y-3 pt-3 border-t border-slate-800 flex-1 min-h-0 flex flex-col">
                          <span className="text-xs font-bold text-slate-300 uppercase tracking-wide">LLM Prompts</span>
                          <div className="space-y-3 overflow-y-auto flex-1 min-h-0">
                            {stageDetails.llm_traces.map((trace: any, idx: number) => (
                              <div key={idx} className="bg-slate-950/80 p-3 rounded-lg border border-slate-850 space-y-2">
                                <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                                  <span>{trace.model} ({trace.provider})</span>
                                  <span>Trace ID: {trace.id?.slice(0, 8)}</span>
                                </div>
                                <div className="bg-slate-950 p-2.5 rounded border border-slate-900 max-h-[150px] overflow-y-auto text-[10px] font-mono text-slate-400 whitespace-pre-wrap">
                                  <strong>System:</strong> {trace.system_prompt || "N/A"}
                                </div>
                                <div className="bg-slate-950 p-2.5 rounded border border-slate-900 max-h-[150px] overflow-y-auto text-[10px] font-mono text-slate-400 whitespace-pre-wrap">
                                  <strong>User:</strong> {trace.user_prompt || "N/A"}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Outputs Tab */}
                  {activeTab === "outputs" && (
                    <div className="flex flex-col flex-1 min-h-0 space-y-4">
                      <span className="text-xs text-slate-400 block">Raw results and metadata payload</span>
                      <div className="bg-slate-950 p-4 rounded-xl border border-slate-850 font-mono text-[11px] text-slate-300 overflow-auto flex-1 min-h-0">
                        <pre>
                          {JSON.stringify(
                            stageDetails.metadata?.outputs ||
                            (stageDetails.metadata && Object.keys(stageDetails.metadata).length > 0 && !("inputs" in stageDetails.metadata) && !("outputs" in stageDetails.metadata) ? stageDetails.metadata : { message: "No output metadata recorded" }),
                            null,
                            2
                          )}
                        </pre>
                      </div>

                      {stageDetails.llm_traces?.length > 0 && (
                        <div className="space-y-3 pt-3 border-t border-slate-800 flex-1 min-h-0 flex flex-col">
                          <span className="text-xs font-bold text-slate-300 uppercase tracking-wide">LLM Output Responses</span>
                          <div className="space-y-3 overflow-y-auto flex-1 min-h-0">
                            {stageDetails.llm_traces.map((trace: any, idx: number) => (
                              <div key={idx} className="bg-slate-950/80 p-3 rounded-lg border border-slate-850 space-y-2">
                                <div className="flex items-center justify-between text-[10px] font-mono text-slate-500">
                                  <span>{trace.model} ({trace.provider})</span>
                                  <span>Status: {trace.status}</span>
                                </div>
                                <div className="bg-slate-950 p-2.5 rounded border border-slate-900 max-h-[200px] overflow-y-auto text-[10px] font-mono text-emerald-400 whitespace-pre-wrap">
                                  {trace.response_text || "N/A"}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Errors Tab */}
                  {activeTab === "errors" && (
                    <div className="space-y-4">
                      <span className="text-xs text-slate-400 block">Error details and retry outcomes</span>
                      {stageDetails.error ? (
                        <div className="space-y-3">
                          <div className="p-3 bg-red-950/20 border border-red-900/60 text-red-400 rounded-lg text-xs font-semibold">
                            {stageDetails.error_type || "RuntimeError"}: {stageDetails.error}
                          </div>
                          {stageDetails.metadata?.error_traceback && (
                            <div className="bg-slate-950 p-3 rounded-xl border border-slate-850 font-mono text-[10px] text-red-400 overflow-x-auto max-h-[300px]">
                              <pre>{stageDetails.metadata.error_traceback}</pre>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="text-slate-500 text-xs italic">Stage completed successfully without exceptions.</div>
                      )}
                    </div>
                  )}

                  {/* Metrics Tab */}
                  {activeTab === "metrics" && (
                    <div className="space-y-6">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">
                            Stage Latency
                          </span>
                          <span className="text-lg font-mono font-bold text-white block mt-1">
                            {stageDetails.latency_ms ? `${(stageDetails.latency_ms / 1000).toFixed(3)}s` : "0s"}
                          </span>
                        </div>
                        <div className="bg-slate-950/40 p-4 rounded-xl border border-slate-800">
                          <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold block">
                            Stage Retries
                          </span>
                          <span className="text-lg font-mono font-bold text-white block mt-1">
                            {stageDetails.retry_count ?? 0}
                          </span>
                        </div>
                      </div>

                      {stageDetails.llm_traces?.length > 0 && (
                        <div className="space-y-3 pt-3 border-t border-slate-800">
                          <span className="text-xs font-bold text-slate-300 uppercase tracking-wide">LLM Observability Traces</span>
                          <div className="space-y-3">
                            {stageDetails.llm_traces.map((trace: any, idx: number) => (
                              <div key={idx} className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-850 space-y-3.5">
                                <div className="flex items-center justify-between border-b border-slate-850 pb-2">
                                  <span className="text-xs font-bold text-slate-200">{trace.model}</span>
                                  <span className="text-[10px] font-mono text-slate-500 uppercase">{trace.provider}</span>
                                </div>
                                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                                  <div className="bg-slate-950 p-2 rounded border border-slate-900">
                                    <span className="text-[9px] text-slate-500 block">Cost</span>
                                    <span className="font-mono font-bold text-emerald-400 block mt-0.5">
                                      ${trace.cost_usd ? trace.cost_usd.toFixed(5) : "0.00"}
                                    </span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-900">
                                    <span className="text-[9px] text-slate-500 block">Tokens</span>
                                    <span className="font-mono font-bold text-slate-300 block mt-0.5">
                                      {trace.total_tokens || 0}
                                    </span>
                                  </div>
                                  <div className="bg-slate-950 p-2 rounded border border-slate-900">
                                    <span className="text-[9px] text-slate-500 block">Latency</span>
                                    <span className="font-mono font-bold text-slate-300 block mt-0.5">
                                      {trace.latency_ms ? `${(trace.latency_ms / 1000).toFixed(2)}s` : "0s"}
                                    </span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </>
        )}
      </div>
    </>,
    document.body
  )}

      {/* Pipeline Runs History */}
      <div className="glass rounded-2xl p-5 border border-slate-850">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-slate-200">
            Pipeline Execution History
          </h2>
          <button
            onClick={() => refetchHistory()}
            className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh History
          </button>
        </div>

        {!pipelineHistory || pipelineHistory.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-xs italic">
            No pipeline executions recorded in history.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-500 font-semibold">
                  <th className="text-left py-2 pr-4">Run ID</th>
                  <th className="text-left py-2 pr-4">Trigger</th>
                  <th className="text-left py-2 pr-4">Type</th>
                  <th className="text-left py-2 pr-4">Summary</th>
                  <th className="text-left py-2 pr-4">Status</th>
                  <th className="text-left py-2 pr-4">Started At</th>
                  <th className="text-right py-2 pr-4">Duration</th>
                  <th className="text-right py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {pipelineHistory.map((run: any) => {
                  const cfg = STATUS_CONFIG[run.status] ?? STATUS_CONFIG.pending;
                  const Icon = cfg.icon;
                  const isSelected = selectedRunId === run.id;
                  return (
                    <tr
                      key={run.id}
                      className={`border-b border-slate-800/40 hover:bg-slate-800/10 transition-colors ${
                        isSelected ? "bg-primary/5" : ""
                      }`}
                    >
                      <td className="py-2.5 pr-4 font-mono font-semibold text-slate-300">{run.id.slice(0, 18)}…</td>
                      <td className="py-2.5 pr-4 font-mono text-slate-400 capitalize">{run.trigger}</td>
                      <td className="py-2.5 pr-4 font-mono text-slate-400 capitalize">{run.pipeline_type}</td>
                      <td className="py-2.5 pr-4 text-slate-300 font-medium max-w-[200px] truncate" title={run.summary}>
                        {run.summary || "—"}
                      </td>
                      <td className="py-2.5 pr-4">
                        <span className={`flex items-center gap-1.5 font-bold uppercase text-[10px] ${cfg.cls}`}>
                          <Icon className={`w-3.5 h-3.5 ${cfg.iconCls || ""}`} />
                          {cfg.label}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-slate-400 font-mono">
                        {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-slate-400">
                        {run.total_latency_ms ? `${(run.total_latency_ms / 1000).toFixed(2)}s` : "—"}
                      </td>
                      <td className="py-2.5 text-right">
                        <button
                          onClick={() => setSelectedRunId(run.id)}
                          disabled={isSelected}
                          className="px-2.5 py-1 bg-slate-850 hover:bg-slate-800 text-[10px] text-slate-300 rounded font-semibold border border-slate-800 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                        >
                          {isSelected ? "Selected" : "Inspect Trace"}
                        </button>
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
