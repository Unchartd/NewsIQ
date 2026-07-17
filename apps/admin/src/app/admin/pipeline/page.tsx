"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  Sparkles,
  Cpu,
  History,
  GitCommit,
} from "lucide-react";
import { toast } from "sonner";

// Frontend Node configuration
const PIPELINE_STAGES = [
  { id: "RSS", label: "RSS Ingestion", group: "ingestion", isAi: false },
  { id: "DISCOVERY", label: "Discovery Search", group: "discovery", isAi: false },
  { id: "CRAWL", label: "Crawl Queue", group: "discovery", isAi: false },
  { id: "CANDIDATE_RETRIEVAL", label: "Candidate Retrieval", group: "processing", isAi: false },
  { id: "STAGE_A", label: "Stage A Filters", group: "processing", isAi: false },
  { id: "STAGE_B", label: "Stage B LLM", group: "processing", isAi: true },
  { id: "CLUSTERING", label: "Story Clustering", group: "processing", isAi: false },
  { id: "SYNTHESIS", label: "Story Synthesis", group: "generation", isAi: true },
  { id: "FEEDBACK", label: "Feedback Agent", group: "generation", isAi: true },
  { id: "PUBLISHER", label: "Publisher Engine", group: "output", isAi: false },
];

const GROUP_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  ingestion: { bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-400" },
  discovery: { bg: "bg-cyan-500/10", border: "border-cyan-500/30", text: "text-cyan-400" },
  processing: { bg: "bg-indigo-500/10", border: "border-indigo-500/30", text: "text-indigo-400" },
  generation: { bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-400" },
  output: { bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-400" },
};

const STATUS_CONFIG: Record<string, { icon: React.ElementType; cls: string; label: string; iconCls?: string }> = {
  success: { icon: CheckCircle2, cls: "text-emerald-400", label: "Success" },
  failed: { icon: XCircle, cls: "text-red-400", label: "Failed" },
  running: { icon: Loader2, cls: "text-blue-400", iconCls: "animate-spin", label: "Running" },
  pending: { icon: Clock, cls: "text-slate-500", label: "Pending" },
  skipped: { icon: SkipForward, cls: "text-slate-655", label: "Skipped" },
  retrying: { icon: RotateCw, cls: "text-amber-400", iconCls: "animate-pulse", label: "Retrying" },
};

// Stage normalization helper mappings
const BACKEND_TO_FRONTEND_STAGE: Record<string, string> = {
  ingestion_rss: "RSS",
  discovery_search: "DISCOVERY",
  discovery_crawl: "CRAWL",
  crawling: "CRAWL",
  deduplication: "CANDIDATE_RETRIEVAL",
  embedding: "CANDIDATE_RETRIEVAL",
  stage_a: "STAGE_A",
  "stage a (pre-embedding)": "STAGE_A",
  stage_b: "STAGE_B",
  "stage b (post-embedding)": "STAGE_B",
  clustering_batch: "CLUSTERING",
  clustering_incremental: "CLUSTERING",
  entity_linking: "CLUSTERING",
  summary_generation: "SYNTHESIS",
  timeline_generation: "SYNTHESIS",
  contradiction_detection: "SYNTHESIS",
  difference_engine: "SYNTHESIS",
  knowledge_graph: "SYNTHESIS",
  synthesis_orchestrator: "SYNTHESIS",
  feedback_agent: "FEEDBACK",
  publisher: "PUBLISHER",
  indexing: "PUBLISHER",
};

const FRONTEND_TO_BACKEND_STAGES: Record<string, string[]> = {
  RSS: ["ingestion_rss"],
  DISCOVERY: ["discovery_search"],
  CRAWL: ["discovery_crawl", "crawling"],
  CANDIDATE_RETRIEVAL: ["deduplication", "embedding"],
  STAGE_A: ["stage_a", "stage a (pre-embedding)"],
  STAGE_B: ["stage_b", "stage b (post-embedding)"],
  CLUSTERING: ["clustering_batch", "clustering_incremental", "entity_linking"],
  SYNTHESIS: ["summary_generation", "timeline_generation", "contradiction_detection", "difference_engine", "knowledge_graph", "synthesis_orchestrator"],
  FEEDBACK: ["feedback_agent"],
  PUBLISHER: ["publisher", "indexing"],
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
  isDimmed,
}: {
  stage: (typeof PIPELINE_STAGES)[0];
  stageStatus?: string;
  onClick: () => void;
  isActive: boolean;
  isDimmed: boolean;
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
      className={`flex flex-col gap-1 p-4 rounded-xl border text-left transition-all duration-200 glass-hover ${stateCls} ${
        isDimmed ? "opacity-25 blur-[0.3px] scale-[0.97] pointer-events-none select-none" : ""
      }`}
    >
      <div className="flex items-center justify-between gap-2 w-full">
        <span className="text-[12px] font-bold tracking-tight">
          {stage.label}
        </span>
        <Icon className={`w-3.5 h-3.5 shrink-0 ${cfg.iconCls || ""}`} />
      </div>
      
      <div className="flex items-center justify-between w-full mt-1">
        <span className="text-[9px] font-mono text-slate-550 uppercase">{stage.id}</span>
        {stage.isAi ? (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-semibold bg-purple-500/15 text-purple-400 border border-purple-500/20">
            <Sparkles className="w-2 h-2 shrink-0" />
            AI Stage
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[8px] font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/20">
            <Cpu className="w-2 h-2 shrink-0" />
            Rule-Based
          </span>
        )}
      </div>

      <div className="flex items-center gap-1.5 mt-2.5">
        <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-black/30">
          {status}
        </span>
      </div>
    </button>
  );
}

function buildTraceTree(traces: any[]): any[] {
  if (!traces || traces.length === 0) return [];
  const traceMap = new Map();
  traces.forEach(t => traceMap.set(t.id, { ...t, children: [] }));
  const roots: any[] = [];
  traces.forEach(t => {
    const node = traceMap.get(t.id);
    if (t.parent_llm_trace_id && traceMap.has(t.parent_llm_trace_id)) {
      traceMap.get(t.parent_llm_trace_id).children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

function AIReasoningNode({ node, depth = 0 }: { node: any; depth: number }) {
  const [expanded, setExpanded] = useState(depth === 0);
  const hasChildren = node.children && node.children.length > 0;
  
  return (
    <div className="border border-slate-800 bg-slate-950/60 rounded-xl overflow-hidden shadow-sm" style={{ marginLeft: `${depth * 16}px` }}>
      <div 
        onClick={() => hasChildren && setExpanded(!expanded)}
        className={`p-3 flex items-center justify-between text-xs cursor-pointer select-none hover:bg-slate-900/40 transition-colors ${hasChildren ? "font-semibold" : ""}`}
      >
        <div className="flex items-center gap-2">
          {hasChildren && (
            <span className="text-slate-500 font-mono text-[10px] mr-1">
              {expanded ? "▼" : "▶"}
            </span>
          )}
          <span className="px-1.5 py-0.5 rounded text-[8px] bg-purple-500/15 text-purple-400 font-mono font-bold">
            {node.provider.toUpperCase()}
          </span>
          <span className="text-slate-200 font-semibold">{node.model}</span>
        </div>
        <div className="flex items-center gap-3 text-slate-400 font-mono text-[10px]">
          <span>Cost: <strong className="text-emerald-400">${node.cost_usd ? node.cost_usd.toFixed(5) : "0.00"}</strong></span>
          <span>Tokens: <strong>{node.total_tokens}</strong></span>
          <span>Latency: <strong>{(node.latency_ms / 1000).toFixed(2)}s</strong></span>
        </div>
      </div>
      
      {expanded && (
        <div className="p-3 bg-slate-950 border-t border-slate-900 space-y-3">
          {node.system_prompt && (
            <div className="space-y-1">
              <span className="text-[9px] uppercase font-bold text-slate-550 block font-mono">System Prompt</span>
              <pre className="p-2 bg-black/40 rounded border border-slate-900 text-[10px] font-mono text-slate-400 whitespace-pre-wrap max-h-[120px] overflow-y-auto">
                {node.system_prompt}
              </pre>
            </div>
          )}
          <div className="space-y-1">
            <span className="text-[9px] uppercase font-bold text-slate-550 block font-mono">User Prompt</span>
            <pre className="p-2 bg-black/40 rounded border border-slate-900 text-[10px] font-mono text-slate-400 whitespace-pre-wrap max-h-[150px] overflow-y-auto">
              {node.user_prompt || "N/A"}
            </pre>
          </div>
          <div className="space-y-1">
            <span className="text-[9px] uppercase font-bold text-slate-550 block font-mono">Response</span>
            <pre className="p-2 bg-black/40 rounded border border-slate-900 text-[10px] font-mono text-emerald-400 whitespace-pre-wrap max-h-[200px] overflow-y-auto">
              {node.response_text || "N/A"}
            </pre>
          </div>
        </div>
      )}
      
      {expanded && hasChildren && (
        <div className="p-2 bg-slate-950/20 border-t border-slate-900/60 space-y-2">
          {node.children.map((child: any) => (
            <AIReasoningNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

function InvestigationView({
  selectedRunId,
  setSelectedRunId,
  pipelineHistory,
  pipelineStatus,
  mapBackendToFrontendStage,
  getBackendStagesForFrontend,
}: any) {
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [inspectStoryId, setInspectStoryId] = useState<string>("");
  const [storyIdQuery, setStoryIdQuery] = useState<string | null>(null);

  const { data: storyEvolution, isLoading: isLoadingEvo, error: evoError } = useQuery<any>({
    queryKey: ["story-evolution", storyIdQuery],
    queryFn: async () => {
      if (!storyIdQuery) return null;
      const res = await apiClient.get(`/admin/pipeline/story/${storyIdQuery}/evolution`);
      return res.data;
    },
    enabled: !!storyIdQuery,
  });

  const { data: stageDetails, isLoading: isLoadingDetails } = useQuery<any>({
    queryKey: ["investigation-stage-details", selectedRunId, selectedStage],
    queryFn: async () => {
      if (!selectedRunId || !selectedStage) return null;
      const res = await apiClient.get(`/admin/pipeline/runs/${selectedRunId}/stages/${selectedStage}`);
      return res.data;
    },
    enabled: !!selectedRunId && !!selectedStage,
  });

  const activeRun = pipelineHistory?.find((r: any) => r.id === selectedRunId);
  const metadata = activeRun?.metadata_payload || pipelineStatus?.metadata_payload || {};
  const roots = stageDetails?.llm_traces ? buildTraceTree(stageDetails.llm_traces) : [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4 lg:col-span-1">
        <h2 className="text-sm font-bold text-slate-200">Execution Stepper</h2>
        
        <div className="space-y-2">
          <label className="text-[10px] uppercase font-bold text-slate-500 tracking-wider font-mono">Select Run</label>
          <select 
            value={selectedRunId || ""}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedRunId(val || null);
              setSelectedStage(null);
            }}
            className="w-full bg-slate-950 border border-slate-850 rounded-xl px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-primary/50"
          >
            <option value="">-- Active Run (Live Mode) --</option>
            {pipelineHistory?.map((run: any) => (
              <option key={run.id} value={run.id}>
                {run.started_at ? new Date(run.started_at).toLocaleTimeString() : run.id.slice(0, 8)} - {run.trigger} ({run.status})
              </option>
            ))}
          </select>
        </div>

        {selectedRunId ? (
          <div className="space-y-2.5 pt-2">
            <label className="text-[10px] uppercase font-bold text-slate-500 tracking-wider font-mono">Executed Stages</label>
            {pipelineStatus?.stages && pipelineStatus.stages.length > 0 ? (
              <div className="relative border-l border-slate-800 pl-4 ml-2.5 space-y-4">
                {pipelineStatus.stages.map((stg: any) => {
                  const isSelected = selectedStage === stg.stage;
                  const cfg = STATUS_CONFIG[stg.status] || STATUS_CONFIG.pending;
                  return (
                    <div key={stg.stage} className="relative group">
                      <div className={`absolute -left-[22.5px] top-1.5 w-3 h-3 rounded-full border bg-slate-955 ${cfg.cls} flex items-center justify-center`} />
                      <button
                        onClick={() => setSelectedStage(stg.stage)}
                        className={`flex flex-col text-left w-full p-2.5 rounded-xl border transition-all ${
                          isSelected
                            ? "bg-primary/10 border-primary text-white font-semibold"
                            : "bg-slate-900/30 border-slate-850 text-slate-400 hover:border-slate-800 hover:text-slate-200"
                        }`}
                      >
                        <span className="text-[11px] font-bold">{mapBackendToFrontendStage(stg.stage)}</span>
                        <span className="text-[9px] font-mono text-slate-550 lowercase mt-0.5">{stg.stage}</span>
                        <div className="flex items-center justify-between w-full mt-1.5 text-[9px] text-slate-500 font-mono">
                          <span>{(stg.latency_ms / 1000).toFixed(2)}s</span>
                          <span className={`font-bold uppercase ${cfg.cls}`}>{stg.status}</span>
                        </div>
                      </button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-slate-550 text-xs italic py-4">No stages found for this run.</div>
            )}
          </div>
        ) : (
          <div className="text-slate-550 text-xs italic py-6 text-center">
            Select a run from history to trace its executed stages.
          </div>
        )}
      </div>

      {/* Story Evolution Timeline Card */}
      <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
        <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <History className="w-4 h-4 text-primary" />
          Story Evolution Inspector
        </h2>

        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Enter Story UUID..."
              value={inspectStoryId}
              onChange={(e) => setInspectStoryId(e.target.value)}
              className="flex-1 bg-slate-950 border border-slate-850 rounded-xl px-3 py-2 text-xs font-mono text-slate-300 focus:outline-none focus:border-primary/50"
            />
            <button
              onClick={() => setStoryIdQuery(inspectStoryId.trim() || null)}
              className="px-3 py-2 bg-primary/20 hover:bg-primary/30 border border-primary/30 rounded-xl text-xs font-bold text-primary transition-all"
            >
              Inspect
            </button>
          </div>

          {isLoadingEvo && (
            <div className="flex items-center gap-2 justify-center py-4 text-xs text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Loading evolution timeline...
            </div>
          )}

          {evoError && (
            <div className="text-xs text-red-400 bg-red-950/20 p-2 border border-red-900/40 rounded-lg">
              Failed to load evolution: {String(evoError)}
            </div>
          )}

          {!storyIdQuery && !isLoadingEvo && (
            <div className="text-xs text-slate-550 italic py-4 text-center">
              No story selected. Enter a Story UUID to inspect its cluster mutation timeline.
            </div>
          )}

          {storyIdQuery && storyEvolution && storyEvolution.length === 0 && (
            <div className="text-xs text-slate-550 italic py-4 text-center">
              No evolution records found for this story.
            </div>
          )}

          {storyEvolution && storyEvolution.length > 0 && (
            <div className="relative border-l border-slate-800 pl-4 ml-2.5 space-y-5 pt-2">
              {storyEvolution.map((evt: any) => {
                let dotCls = "bg-slate-550 border-slate-650";
                let title = evt.event_type;
                let desc = evt.notes || "";

                if (evt.event_type === "created") {
                  dotCls = "bg-emerald-500/20 border-emerald-500 text-emerald-400";
                  title = "Story Created";
                  desc = `Created with ${evt.after_state?.article_count || 1} articles. ${evt.notes || ""}`;
                } else if (evt.event_type === "article_merged") {
                  dotCls = "bg-blue-500/20 border-blue-500 text-blue-400";
                  title = "Article Merged";
                  desc = `Article ${evt.article_id?.slice(0, 8)}... incrementally merged. Cluster size: ${evt.before_state?.article_count || 0} -> ${evt.after_state?.article_count || 1}.`;
                } else if (evt.event_type === "split") {
                  dotCls = "bg-purple-500/20 border-purple-500 text-purple-400";
                  title = "Cluster Split";
                  desc = `Story split into ${evt.after_state?.sub_clusters_count || 2} sub-clusters. Child IDs: ${evt.child_story_ids?.map((c: string) => c.slice(0, 8)).join(", ")}.`;
                } else if (evt.event_type === "merged") {
                  dotCls = "bg-amber-500/20 border-amber-500 text-amber-400";
                  title = "Merged Target";
                  desc = `Target story merged with parent story: ${evt.parent_story_ids?.map((p: string) => p.slice(0, 8)).join(", ")}.`;
                } else if (evt.event_type === "merged_away") {
                  dotCls = "bg-slate-800 border-slate-750 text-slate-500";
                  title = "Merged Away";
                  desc = `Merged away into target story ${evt.parent_story_ids?.map((p: string) => p.slice(0, 8)).join(", ")}. (Story deleted).`;
                } else if (evt.event_type === "promoted") {
                  dotCls = "bg-rose-500/20 border-rose-500 text-rose-400";
                  title = "Lifecycle Transition";
                  desc = `Transitioned: ${evt.before_state?.lifecycle_state || "unknown"} -> ${evt.after_state?.lifecycle_state || "unknown"}. ${evt.notes || ""}`;
                }

                return (
                  <div key={evt.id} className="relative group text-xs">
                    <div className={`absolute -left-[22.5px] top-1 w-3 h-3 rounded-full border bg-slate-955 flex items-center justify-center ${dotCls}`}>
                      <span className="w-1.5 h-1.5 rounded-full bg-current" />
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-bold text-slate-200">{title}</span>
                      <span className="text-slate-400">{desc}</span>
                      <div className="flex items-center gap-2 text-[10px] text-slate-550 font-mono mt-1">
                        <span>{new Date(evt.created_at).toLocaleString()}</span>
                        {evt.run_id && (
                          <span>• Run: {evt.run_id.slice(0, 8)}...</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="lg:col-span-2 space-y-6">
        {selectedRunId ? (
          <>
            <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
              <div className="flex items-center justify-between gap-4">
                <h3 className="text-xs font-bold text-slate-200 flex items-center gap-2 uppercase tracking-wide">
                  <GitBranch className="w-4 h-4 text-slate-400" />
                  Environment Version Lock
                </h3>
                <button
                  onClick={async () => {
                    try {
                      await apiClient.post(`/admin/pipeline/runs/${selectedRunId}/export-otel`);
                      toast.success("Successfully exported trace data to OTLP collector!");
                    } catch (err: any) {
                      toast.error("Failed to export trace: " + (err.response?.data?.detail || err.message));
                    }
                  }}
                  className="px-2.5 py-1 bg-primary/20 hover:bg-primary/30 border border-primary/30 rounded-lg text-[10px] font-bold text-primary flex items-center gap-1 transition-all"
                >
                  <RefreshCw className="w-3 h-3" />
                  Export Trace to OTel
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-850 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Git Commit SHA</span>
                    {metadata.git_sha ? (
                      <a
                        href={`https://github.com/Unchartd/NewsIQ/commit/${metadata.git_sha}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-primary hover:underline text-[11px] font-bold"
                      >
                        {metadata.git_sha.slice(0, 7)}
                      </a>
                    ) : (
                      <span className="text-slate-400">N/A (Dirty/Local)</span>
                    )}
                  </div>
                </div>

                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-850 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Alembic Database HEAD</span>
                    <span className="text-slate-300 text-[11px] font-bold">
                      {metadata.alembic_revision ? metadata.alembic_revision.slice(0, 12) : "585a02b2a32c"}
                    </span>
                  </div>
                </div>

                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-850 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Docker Image Tag</span>
                    <span className="text-slate-300 text-[11px]">
                      {metadata.docker_image || "newsiq-processing-api-dev:latest"}
                    </span>
                  </div>
                </div>

                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-850 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-[9px] text-slate-500 block uppercase font-bold">Config Version</span>
                    <span className="text-slate-300 text-[11px] font-bold">
                      v{metadata.config_version || "1.2.0"}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {selectedStage ? (
              isLoadingDetails ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 gap-2">
                  <Loader2 className="w-8 h-8 animate-spin text-primary" />
                  <span className="text-xs">Loading stage details...</span>
                </div>
              ) : stageDetails ? (
                <>
                  {/* RCA Failures Classifier Report */}
                  {stageDetails.rca_report && (
                    <div className="glass bg-red-950/10 border border-red-500/20 rounded-2xl p-5 space-y-3.5">
                      <div className="flex items-center gap-2 text-red-400 font-bold text-xs uppercase tracking-wider font-mono">
                        <AlertTriangle className="w-4 h-4" />
                        Root Cause Analysis: {stageDetails.rca_report.category}
                        <span className="ml-auto bg-red-500/10 text-[9px] px-2 py-0.5 rounded border border-red-500/20">
                          {(stageDetails.rca_report.confidence * 100).toFixed(0)}% Conf
                        </span>
                      </div>
                      <div className="text-xs space-y-2">
                        <div className="space-y-1">
                          <span className="text-[10px] text-slate-500 block uppercase font-bold tracking-wide">Diagnosis</span>
                          <p className="text-slate-350 leading-relaxed">{stageDetails.rca_report.description}</p>
                        </div>
                        <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-900 space-y-1.5 mt-2">
                          <span className="text-[10px] text-emerald-400 block uppercase font-bold tracking-wide font-mono">Remediation Guide</span>
                          <p className="text-slate-300 leading-relaxed font-sans">{stageDetails.rca_report.remediation}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  {stageDetails.metadata && Object.keys(stageDetails.metadata).length > 0 && (
                    <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
                      <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wide">
                        Tiered Artifact Storage
                      </h3>
                      
                      <div className="space-y-3">
                        {Object.entries(stageDetails.metadata).map(([key, val]: any) => {
                          const isArtifact = val && typeof val === "object";
                          if (!isArtifact && key !== "discovery" && key !== "inputs" && key !== "outputs") return null;
                          
                          let tier = 2;
                          let tierDesc = "Tier 2: Intermediate telemetry (saved on failures only)";
                          if (key === "discovery_report" || key === "events_summary" || key === "embedding_metrics" || key === "results") {
                            tier = 1;
                            tierDesc = "Tier 1: Vital metrics & matrices (permanently archived)";
                          } else if (key === "embeddings" || key === "vectors") {
                            tier = 3;
                            tierDesc = "Tier 3: Temporary buffer (never saved to filesystem)";
                          }

                          return (
                            <div key={key} className="bg-slate-950/50 p-4 rounded-xl border border-slate-850/80 space-y-2">
                              <div className="flex items-center justify-between text-xs">
                                <span className="font-mono font-bold text-slate-300">{key}.json</span>
                                <span className={`px-2 py-0.5 rounded-[4px] text-[8px] font-bold font-mono uppercase tracking-wider ${
                                  tier === 1 ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                                  tier === 2 ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" :
                                  "bg-slate-800 text-slate-500"
                                }`}>
                                  Tier {tier}
                                </span>
                              </div>
                              <p className="text-[10px] text-slate-550">{tierDesc}</p>
                              
                              <div className="bg-slate-950 p-3 rounded-lg border border-slate-900 max-h-[160px] overflow-auto text-[10px] font-mono text-slate-400">
                                <pre>{JSON.stringify(val, null, 2)}</pre>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
                    <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wide">
                      AI Reasoning Hierarchy
                    </h3>
                    {roots.length > 0 ? (
                      <div className="space-y-3">
                        {roots.map((root: any) => (
                          <AIReasoningNode key={root.id} node={root} depth={0} />
                        ))}
                      </div>
                    ) : (
                      <div className="text-slate-505 text-xs italic py-4 text-center bg-slate-950/20 border border-dashed border-slate-850 rounded-xl">
                        No LLM generation calls traced for this stage.
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <div className="text-slate-505 text-xs italic py-10 text-center">
                  Stage telemetry not available.
                </div>
              )
            ) : (
              <div className="text-slate-550 text-xs italic py-20 text-center bg-slate-900/10 border border-dashed border-slate-850 rounded-2xl">
                Select an executed stage from the left menu to view detailed telemetry.
              </div>
            )}
          </>
        ) : (
          <div className="text-slate-550 text-xs italic py-20 text-center bg-slate-900/10 border border-dashed border-slate-850 rounded-2xl">
            Select a run from the history stepper to trace environment variables, artifacts, and LLM reasoning hierarchies.
          </div>
        )}
      </div>
    </div>
  );
}

function AnalyticsView({ pipelineHistory, metricsSummary }: any) {
  const runCount = pipelineHistory?.length || 0;
  const avgLatency = runCount > 0 
    ? (pipelineHistory.reduce((acc: number, r: any) => acc + (r.total_latency_ms || 0), 0) / runCount / 1000).toFixed(2)
    : "0.00";

  const [compareRunIdA, setCompareRunIdA] = useState<string>("");
  const [compareRunIdB, setCompareRunIdB] = useState<string>("");

  const { data: compareData, isLoading: isLoadingCompare } = useQuery<any>({
    queryKey: ["compare-runs", compareRunIdA, compareRunIdB],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (compareRunIdA) params.append("run_id_a", compareRunIdA);
      if (compareRunIdB) params.append("run_id_b", compareRunIdB);
      const res = await apiClient.get(`/admin/pipeline/compare?${params.toString()}`);
      return res.data;
    },
  });

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass rounded-2xl p-5 border border-slate-850 flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block font-mono">Total Tokens Consumed</span>
          <span className="text-2xl font-bold font-mono text-slate-100 block mt-2">
            {metricsSummary?.total_tokens_consumed ? metricsSummary.total_tokens_consumed.toLocaleString() : "0"}
          </span>
          <span className="text-[10px] text-slate-505 block mt-1">Across all historical pipeline executions</span>
        </div>

        <div className="glass rounded-2xl p-5 border border-slate-850 flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block font-mono">Aggregated LLM Cost</span>
          <span className="text-2xl font-bold font-mono text-emerald-400 block mt-2">
            {metricsSummary?.total_llm_cost ? `$${metricsSummary.total_llm_cost.toFixed(4)}` : "$0.0000"}
          </span>
          <span className="text-[10px] text-slate-505 block mt-1">USD incurred based on current API model pricing</span>
        </div>

        <div className="glass rounded-2xl p-5 border border-slate-850 flex flex-col justify-between">
          <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider block font-mono">Average Run Latency</span>
          <span className="text-2xl font-bold font-mono text-slate-100 block mt-2">
            {avgLatency}s
          </span>
          <span className="text-[10px] text-slate-505 block mt-1">Mean duration computed from {runCount} runs</span>
        </div>
      </div>

      {/* Compare Runs Panel */}
      <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-slate-800/60">
          <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <ArrowRightLeft className="w-4 h-4 text-primary" />
            Performance Diff Comparison (Latest vs Yesterday)
          </h2>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-500 font-medium">Run A (New):</span>
              <select
                value={compareRunIdA}
                onChange={(e) => setCompareRunIdA(e.target.value)}
                className="bg-slate-950 border border-slate-850 rounded-xl px-2.5 py-1 text-[11px] font-mono text-slate-300 focus:outline-none focus:border-primary/50"
              >
                <option value="">-- Latest Run --</option>
                {pipelineHistory?.map((run: any) => (
                  <option key={run.id} value={run.id}>
                    {run.started_at ? new Date(run.started_at).toLocaleTimeString() : run.id.slice(0, 8)} ({run.pipeline_type})
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-500 font-medium">Run B (Base):</span>
              <select
                value={compareRunIdB}
                onChange={(e) => setCompareRunIdB(e.target.value)}
                className="bg-slate-950 border border-slate-850 rounded-xl px-2.5 py-1 text-[11px] font-mono text-slate-300 focus:outline-none focus:border-primary/50"
              >
                <option value="">-- Yesterday's Run --</option>
                {pipelineHistory?.map((run: any) => (
                  <option key={run.id} value={run.id}>
                    {run.started_at ? new Date(run.started_at).toLocaleTimeString() : run.id.slice(0, 8)} ({run.pipeline_type})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {isLoadingCompare ? (
          <div className="flex items-center justify-center py-10 text-xs text-slate-550 gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            Comparing runs performance...
          </div>
        ) : compareData ? (
          <div className="space-y-5">
            {/* Run Level Diffs */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                {
                  label: "Execution Latency",
                  a: `${(compareData.run_a?.total_latency_ms / 1000).toFixed(2)}s`,
                  b: `${(compareData.run_b?.total_latency_ms / 1000).toFixed(2)}s`,
                  diff: compareData.diffs?.total_latency_ms,
                  format: (v: number) => `${(v / 1000).toFixed(2)}s`
                },
                {
                  label: "Incurred LLM Cost",
                  a: `$${compareData.run_a?.cost_usd.toFixed(4)}`,
                  b: `$${compareData.run_b?.cost_usd.toFixed(4)}`,
                  diff: compareData.diffs?.cost_usd,
                  format: (v: number) => `$${v.toFixed(4)}`
                },
                {
                  label: "Tokens Consumed",
                  a: compareData.run_a?.total_tokens.toLocaleString(),
                  b: compareData.run_b?.total_tokens.toLocaleString(),
                  diff: compareData.diffs?.total_tokens,
                  format: (v: number) => v.toLocaleString()
                },
                {
                  label: "Successful Outputs",
                  a: compareData.run_a?.success_count,
                  b: compareData.run_b?.success_count,
                  diff: compareData.diffs?.success_count,
                  format: (v: number) => v
                }
              ].map((item, idx) => {
                const diffVal = item.diff?.diff || 0;
                const pct = item.diff?.percent || 0;
                const isPositive = diffVal > 0;
                const isZero = diffVal === 0;

                const isBad = idx < 3 ? isPositive : !isPositive;
                const badgeCls = isZero ? "bg-slate-800 text-slate-400" :
                  isBad ? "bg-red-500/10 text-red-400 border border-red-500/20" :
                  "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";

                return (
                  <div key={idx} className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-850 flex flex-col justify-between">
                    <div>
                      <span className="text-[9px] uppercase font-bold text-slate-555 block font-mono">{item.label}</span>
                      <div className="flex items-baseline gap-2 mt-2">
                        <span className="text-base font-bold text-slate-200 font-mono">{item.a}</span>
                        <span className="text-[10px] text-slate-550 font-mono">vs {item.b}</span>
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between">
                      <span className={`px-2 py-0.5 rounded-[4px] text-[9px] font-bold font-mono ${badgeCls}`}>
                        {isZero ? "±0" : `${isPositive ? "+" : ""}${item.format(diffVal)} (${pct}%)`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Stage Level Diffs Table */}
            <div className="overflow-x-auto pt-2">
              <span className="text-[9px] uppercase font-bold text-slate-500 tracking-wider font-mono block mb-2">Stage-by-Stage Telemetry Compare</span>
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-500 font-semibold text-left">
                    <th className="py-2 pr-4">Pipeline Stage</th>
                    <th className="py-2 pr-4 text-right">Run A Latency</th>
                    <th className="py-2 pr-4 text-right">Run B Latency</th>
                    <th className="py-2 pr-4 text-right">Latency Diff</th>
                    <th className="py-2 pr-4 text-right">Run A Output</th>
                    <th className="py-2 pr-4 text-right">Run B Output</th>
                    <th className="py-2 text-right">Output Diff</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(compareData.run_a?.stages || {}).map((stageKey) => {
                    const stgA = compareData.run_a?.stages[stageKey];
                    const stgB = compareData.run_b?.stages[stageKey] || {};
                    const latDiff = compareData.diffs?.stages?.[stageKey]?.latency_ms;
                    const outDiff = compareData.diffs?.stages?.[stageKey]?.output_count;

                    const isLatPos = (latDiff?.diff || 0) > 0;
                    const isOutPos = (outDiff?.diff || 0) > 0;

                    return (
                      <tr key={stageKey} className="border-b border-slate-855 hover:bg-slate-900/10 text-slate-350">
                        <td className="py-2.5 pr-4 text-slate-200 font-bold">{stageKey}</td>
                        <td className="py-2.5 pr-4 text-right">{(stgA.latency_ms / 1000).toFixed(2)}s</td>
                        <td className="py-2.5 pr-4 text-right">{stgB.latency_ms ? `${(stgB.latency_ms / 1000).toFixed(2)}s` : "—"}</td>
                        <td className={`py-2.5 pr-4 text-right font-bold ${
                          !latDiff ? "text-slate-500" :
                          latDiff.diff === 0 ? "text-slate-400" :
                          isLatPos ? "text-red-400" : "text-emerald-400"
                        }`}>
                          {latDiff ? `${isLatPos ? "+" : ""}${(latDiff.diff / 1000).toFixed(2)}s` : "—"}
                        </td>
                        <td className="py-2.5 pr-4 text-right">{stgA.output_count}</td>
                        <td className="py-2.5 pr-4 text-right">{stgB.output_count ?? "—"}</td>
                        <td className={`py-2.5 text-right font-bold ${
                          !outDiff ? "text-slate-550" :
                          outDiff.diff === 0 ? "text-slate-400" :
                          isOutPos ? "text-emerald-400" : "text-red-400"
                        }`}>
                          {outDiff ? `${isOutPos ? "+" : ""}${outDiff.diff}` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="text-xs text-slate-550 italic py-6 text-center">
            Unable to fetch comparison data. Check database connections.
          </div>
        )}
      </div>

      <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
        <h2 className="text-sm font-bold text-slate-200">Latency Budgets by Pipeline Stage</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-500 font-semibold text-left">
                <th className="py-2 pr-4">Pipeline Stage</th>
                <th className="py-2 pr-4">Model Route</th>
                <th className="py-2 pr-4">Average Latency</th>
                <th className="py-2 pr-4">Budget / Threshold</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {[
                { stage: "Ingestion RSS", route: "Rule-Based (cURL)", avg: "1.2s", limit: "5.0s", ok: true },
                { stage: "Crawl Queue", route: "Rule-Based (Scraper)", avg: "4.8s", limit: "15.0s", ok: true },
                { stage: "Embeddings Generator", route: "gemini-embedding-001", avg: "0.8s", limit: "2.0s", ok: true },
                { stage: "Event Extraction", route: "gemini-2.5-flash", avg: "2.3s", limit: "5.0s", ok: true },
                { stage: "Clustering Batch", route: "Rule-Based (Cosine)", avg: "0.4s", limit: "2.0s", ok: true },
                { stage: "Story Synthesis", route: "gemini-2.5-flash", avg: "3.5s", limit: "8.0s", ok: true },
                { stage: "Feedback Agent", route: "gemini-2.5-flash", avg: "5.1s", limit: "10.0s", ok: true },
              ].map((item, idx) => (
                <tr key={idx} className="border-b border-slate-855 hover:bg-slate-900/10">
                  <td className="py-2.5 pr-4 text-slate-300 font-bold">{item.stage}</td>
                  <td className="py-2.5 pr-4 text-slate-400 text-[11px]">{item.route}</td>
                  <td className="py-2.5 pr-4 text-slate-300">{item.avg}</td>
                  <td className="py-2.5 pr-4 text-slate-500">{item.limit}</td>
                  <td className="py-2.5">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Within Budget
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
          <h2 className="text-sm font-bold text-slate-200">LLM Model Utilization</h2>
          <div className="space-y-3">
            {[
              { model: "gemini-2.5-flash", count: "82%", cost: "$0.0125", tokens: "680k" },
              { model: "gemini-embedding-001", count: "15%", cost: "$0.0000", tokens: "185k" },
              { model: "gemini-2.0-pro-exp", count: "3%", cost: "$0.0042", tokens: "25k" },
            ].map((item, idx) => (
              <div key={idx} className="bg-slate-950/60 p-3 rounded-xl border border-slate-850/80 flex items-center justify-between text-xs">
                <div className="space-y-0.5">
                  <span className="font-bold text-slate-300">{item.model}</span>
                  <span className="text-[10px] text-slate-550 block font-mono">{item.tokens} tokens</span>
                </div>
                <div className="text-right space-y-0.5">
                  <span className="font-mono font-bold text-slate-300 block">{item.count}</span>
                  <span className="font-mono text-emerald-400 text-[10px] block">{item.cost}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass rounded-2xl p-5 border border-slate-850 space-y-4">
          <h2 className="text-sm font-bold text-slate-200">Failure Frequency by Stage</h2>
          <div className="space-y-3">
            {[
              { stage: "Ingestion RSS", rate: "1.2%", status: "Healthy" },
              { stage: "Crawl Queue", rate: "4.5%", status: "Degraded" },
              { stage: "Event Extraction", rate: "0.2%", status: "Healthy" },
            ].map((item, idx) => (
              <div key={idx} className="bg-slate-950/60 p-3 rounded-xl border border-slate-850/80 flex items-center justify-between text-xs">
                <span className="font-bold text-slate-300">{item.stage}</span>
                <div className="flex items-center gap-3 font-mono">
                  <span className="text-slate-400">Rate: <strong className="text-red-400">{item.rate}</strong></span>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${
                    item.status === "Healthy" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                  }`}>
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const PIPELINE_PHASES = [
  {
    title: "1. Ingestion & Discovery",
    desc: "Fetch feeds & scrape content",
    stages: ["RSS", "DISCOVERY", "CRAWL"],
  },
  {
    title: "2. Deduplication & Extraction",
    desc: "Filter duplicates & run entities",
    stages: ["CANDIDATE_RETRIEVAL", "STAGE_A", "STAGE_B"],
  },
  {
    title: "3. Clustering & Synthesis",
    desc: "Group stories & generate summary",
    stages: ["CLUSTERING", "SYNTHESIS"],
  },
  {
    title: "4. Verification & Output",
    desc: "Human review & database commit",
    stages: ["FEEDBACK", "PUBLISHER"],
  },
];

export default function PipelinePage() {
  const { lastEvent, events, status: sseStatus } = useSSE();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [wasAutoPinned, setWasAutoPinned] = useState(false);
  const [dagFilter, setDagFilter] = useState<"all" | "ai" | "deterministic">("all");
  const [currentView, setCurrentView] = useState<"operations" | "investigation" | "analytics">("operations");

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

  const queryClient = useQueryClient();

  const togglePauseMutation = useMutation({
    mutationFn: async () => {
      const isPaused = !!pausedData?.paused;
      const endpoint = isPaused ? "/admin/pipeline/resume" : "/admin/pipeline/pause";
      // Optimistic update — flip the state immediately before the server responds
      queryClient.setQueryData(["pipeline-paused"], { paused: !isPaused });
      const res = await apiClient.post(endpoint);
      return res.data;
    },
    onSuccess: (resData) => {
      toast.success(resData.message);
      // Confirm with server state after optimistic update
      refetchPaused();
    },
    onError: () => {
      // Revert optimistic update on failure
      refetchPaused();
      toast.error("Failed to update pipeline status.");
    },
  });

  const triggerMutation = useMutation({
    mutationFn: async ({ force = false }: { force?: boolean } = {}) => {
      const res = await apiClient.post(
        `/admin/pipeline/trigger${force ? "?force=true" : ""}`
      );
      return res.data;
    },
    onSuccess: (resData) => {
      if (resData.forced) {
        toast.success("Pipeline force-triggered while paused — ingest + cluster queued.");
      } else {
        toast.success("Pipeline triggered — ingest + cluster tasks queued!");
      }
      setTimeout(() => {
        refetch();
        refetchHistory();
      }, 1500);
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409 && detail?.paused) {
        // Pipeline is paused — offer a force-trigger
        toast.warning(
          "Pipeline is paused. Click \"Force Trigger\" in the warning banner to override.",
          { duration: 6000 }
        );
      } else {
        toast.error("Failed to trigger pipeline.");
      }
    },
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
            onClick={() => triggerMutation.mutate({})}
            disabled={triggerMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary hover:bg-primary/95 text-white text-xs font-semibold transition-all shadow-lg shadow-primary/20 disabled:opacity-40"
          >
            {triggerMutation.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Play className="w-3.5 h-3.5" />
            )}
            Run Pipeline
          </button>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex items-center gap-1.5 bg-slate-900/40 p-1.5 rounded-2xl border border-slate-800/80 w-fit">
        <button
          onClick={() => setCurrentView("operations")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
            currentView === "operations"
              ? "bg-slate-800 text-white shadow-md border border-slate-700/50"
              : "text-slate-450 hover:text-slate-200"
          }`}
        >
          <GitBranch className="w-4 h-4 shrink-0" />
          Operations
        </button>
        <button
          onClick={() => setCurrentView("investigation")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
            currentView === "investigation"
              ? "bg-slate-800 text-white shadow-md border border-slate-700/50"
              : "text-slate-450 hover:text-slate-200"
          }`}
        >
          <Terminal className="w-4 h-4 shrink-0" />
          Investigation
        </button>
        <button
          onClick={() => setCurrentView("analytics")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-bold transition-all ${
            currentView === "analytics"
              ? "bg-slate-800 text-white shadow-md border border-slate-700/50"
              : "text-slate-450 hover:text-slate-200"
          }`}
        >
          <BarChart3 className="w-4 h-4 shrink-0" />
          Analytics
        </button>
      </div>

      {pausedData?.paused && (
        <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <span className="font-semibold text-white">Pipeline suspended:</span> Background ingestion, embedding, event extraction, and clustering tasks are currently paused.
            </div>
          </div>
          <button
            onClick={() => triggerMutation.mutate({ force: true })}
            disabled={triggerMutation.isPending}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-xs font-semibold border border-amber-500/40 transition-all shrink-0 disabled:opacity-40"
          >
            {triggerMutation.isPending ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Play className="w-3 h-3" />
            )}
            Force Trigger
          </button>
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

      {currentView === "operations" && (
        <>
          {/* Pipeline DAG */}
      <div className="glass rounded-2xl p-6 border border-slate-850">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 pb-4 border-b border-slate-800/60">
          <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
            <span>Pipeline Stage Execution DAG</span>
            {pipelineStatus?.status === "running" && (
              <span className="flex items-center gap-1.5 text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full font-normal animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                Executing
              </span>
            )}
          </h2>

          {/* AI vs Deterministic Filter Toggles */}
          <div className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-xl border border-slate-850 self-start">
            <button
              onClick={() => setDagFilter("all")}
              className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                dagFilter === "all"
                  ? "bg-slate-800 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setDagFilter("ai")}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                dagFilter === "ai"
                  ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Sparkles className="w-2.5 h-2.5" />
              AI Stages
            </button>
            <button
              onClick={() => setDagFilter("deterministic")}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all ${
                dagFilter === "deterministic"
                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Cpu className="w-2.5 h-2.5" />
              Rule-Based
            </button>
          </div>
        </div>

        {/* Columns DAG Flow */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 relative">
          {PIPELINE_PHASES.map((phase, phaseIdx) => (
            <div key={phase.title} className="bg-slate-900/10 rounded-2xl p-4 border border-slate-800/80 flex flex-col gap-4 relative">
              {/* Phase Header */}
              <div>
                <h3 className="text-xs font-bold text-slate-300">{phase.title}</h3>
                <p className="text-[10px] text-slate-500 mt-0.5">{phase.desc}</p>
              </div>

              {/* Phase Stages */}
              <div className="flex flex-col gap-3.5 flex-grow">
                {phase.stages.map((stageId) => {
                  const stage = PIPELINE_STAGES.find((s) => s.id === stageId)!;
                  const status = stageStatusMap[stageId];
                  return (
                    <StageNode
                      key={stage.id}
                      stage={stage}
                      stageStatus={status}
                      onClick={() => handleOpenDrawer(stage.id)}
                      isActive={activeStageId === stage.id && isDrawerOpen}
                      isDimmed={
                        dagFilter === "ai" ? !stage.isAi :
                        dagFilter === "deterministic" ? stage.isAi :
                        false
                      }
                    />
                  );
                })}
              </div>

              {/* Connector arrow between columns on desktop */}
              {phaseIdx < 3 && (
                <div className="hidden xl:flex absolute top-1/2 -right-3.5 transform -translate-y-1/2 z-10 items-center justify-center w-7 h-7 rounded-full bg-slate-950 border border-slate-800 text-slate-500 font-mono text-xs">
                  →
                </div>
              )}
            </div>
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
        </>
      )}

      {currentView === "investigation" && (
        <InvestigationView
          selectedRunId={selectedRunId}
          setSelectedRunId={setSelectedRunId}
          pipelineHistory={pipelineHistory}
          pipelineStatus={pipelineStatus}
          mapBackendToFrontendStage={mapBackendToFrontendStage}
          getBackendStagesForFrontend={getBackendStagesForFrontend}
        />
      )}

      {currentView === "analytics" && (
        <AnalyticsView
          pipelineHistory={pipelineHistory}
          metricsSummary={metricsSummary}
        />
      )}
    </div>
  );
}
