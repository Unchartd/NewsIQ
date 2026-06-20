"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Activity, Play, RefreshCw, AlertTriangle, CheckCircle2, 
  Clock, Server, HelpCircle, ArrowRight, Zap, Info
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useEffect, useState } from "react";
import { useSSE } from "@/lib/useSSE";
import { toast } from "sonner";

interface StageStatus {
  stage: string;
  status: "pending" | "running" | "success" | "failed" | "skipped" | "retrying";
  started_at: string;
  completed_at: string | null;
  latency_ms: number | null;
  error: string | null;
}

interface PipelineStatus {
  run_id: string | null;
  status: string;
  stages: StageStatus[];
}

interface MetricsSummary {
  total_pipeline_runs: number;
  failed_runs_count: number;
  total_llm_cost: number;
  total_tokens_consumed: number;
  waiting_jobs_count: number;
  active_jobs_count: number;
}

// Canonical pipeline stages in order of execution
const PIPELINE_ORDER = [
  { key: "ingestion_rss", label: "RSS Ingest", description: "Fetch feeds" },
  { key: "ingestion_gnews", label: "GNews Ingest", description: "Google News API" },
  { key: "crawling", label: "Crawler", description: "Fulltext fetch" },
  { key: "deduplication", label: "Dedup", description: "MinHash check" },
  { key: "embedding", label: "Embedding", description: "text-embedding-004" },
  { key: "event_extraction", label: "Event Extract", description: "Structured events" },
  { key: "entity_extraction", label: "NER v2", description: "Named Entities" },
  { key: "entity_linking", label: "Wikidata Link", description: "Entity resolution" },
  { key: "knowledge_graph", label: "KG Builder", description: "Relation store" },
  { key: "clustering_incremental", label: "Clustering (Inc)", description: "HDBSCAN Incremental" },
  { key: "clustering_batch", label: "Clustering (Batch)", description: "Weekly rebuild" },
  { key: "contradiction_detection", label: "Contradictions", description: "Conflict check" },
  { key: "source_comparison", label: "Bias/Attribution", description: "Source analysis" },
  { key: "timeline_generation", label: "Timeline", description: "Chronology build" },
  { key: "summary_generation", label: "Summary", description: "Multi-depth synth" },
  { key: "difference_engine", label: "Diff Engine", description: "Editorial edits" },
  { key: "indexing", label: "Search Index", description: "Meilisearch push" },
  { key: "cache_invalidation", label: "Cache Inval", description: "Redis purge" }
];

export default function PipelinePage() {
  const queryClient = useQueryClient();
  const [selectedStage, setSelectedStage] = useState<StageStatus | null>(null);
  const { lastEvent } = useSSE();

  // 1. Fetch initial pipeline status
  const { data: pipelineData, isLoading: isPipelineLoading } = useQuery<PipelineStatus>({
    queryKey: ["pipeline-status"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/pipeline/status");
      return res.data;
    },
    refetchInterval: 10000, // Poll fallback every 10s
  });

  // 2. Fetch summary metrics
  const { data: metrics, isLoading: isMetricsLoading } = useQuery<MetricsSummary>({
    queryKey: ["metrics-summary"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/metrics/summary");
      return res.data;
    },
    refetchInterval: 15000,
  });

  // Local state to track real-time changes from SSE
  const [activeRun, setActiveRun] = useState<PipelineStatus | null>(null);

  useEffect(() => {
    if (pipelineData) {
      setActiveRun(pipelineData);
    }
  }, [pipelineData]);

  // Handle SSE event stream updates
  useEffect(() => {
    if (lastEvent) {
      setActiveRun((prev) => {
        if (!prev) return prev;
        
        // If event is for a different run, we could refresh, but let's update current
        const updatedStages = [...prev.stages];
        const existingIdx = updatedStages.findIndex((s) => s.stage === lastEvent.stage);

        const updatedStage: StageStatus = {
          stage: lastEvent.stage,
          status: lastEvent.status as any,
          started_at: lastEvent.timestamp,
          completed_at: lastEvent.status === "completed" || lastEvent.status === "failed" ? lastEvent.timestamp : null,
          latency_ms: lastEvent.latency_ms || null,
          error: lastEvent.error || null,
        };

        if (existingIdx >= 0) {
          updatedStages[existingIdx] = updatedStage;
        } else {
          updatedStages.push(updatedStage);
        }

        // Auto update selected stage details if open
        if (selectedStage && selectedStage.stage === lastEvent.stage) {
          setSelectedStage(updatedStage);
        }

        return {
          ...prev,
          run_id: lastEvent.run_id,
          status: lastEvent.status === "running" ? "running" : prev.status,
          stages: updatedStages,
        };
      });
      
      // Toast notification for stage completions/failures
      if (lastEvent.status === "failed") {
        toast.error(`Stage "${lastEvent.stage}" failed: ${lastEvent.error || "Unknown error"}`);
      } else if (lastEvent.status === "completed") {
        toast.success(`Stage "${lastEvent.stage}" completed in ${lastEvent.latency_ms?.toFixed(0) || 0}ms`);
      }
    }
  }, [lastEvent]);

  // Manual Ingestion trigger
  const triggerIngestion = useMutation({
    mutationFn: async () => {
      await apiClient.post("/sources/trigger-ingestion");
    },
    onSuccess: () => {
      toast.success("News pipeline run triggered!");
      queryClient.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || "Failed to trigger pipeline.");
    }
  });

  const getStageStatus = (stageKey: string) => {
    return activeRun?.stages.find((s) => s.stage === stageKey);
  };

  const getStageColor = (status?: string) => {
    switch (status) {
      case "running":
        return "bg-sky-500/10 border-sky-500 text-sky-500 shadow-[0_0_15px_rgba(14,165,233,0.3)] animate-pulse";
      case "success":
      case "completed":
        return "bg-emerald-500/10 border-emerald-500 text-emerald-400";
      case "failed":
        return "bg-rose-500/10 border-rose-500 text-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.3)]";
      case "skipped":
        return "bg-muted/10 border-muted text-muted-foreground";
      case "retrying":
        return "bg-amber-500/10 border-amber-500 text-amber-500 animate-pulse";
      default:
        return "bg-card border-border/60 text-muted-foreground";
    }
  };

  return (
    <div className="space-y-8">
      {/* Metrics Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Total Pipeline Runs</CardDescription>
            <CardTitle className="text-2xl font-bold flex items-center justify-between">
              {metrics?.total_pipeline_runs ?? "—"}
              <Activity className="w-4 h-4 text-primary" />
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Failure Rate</CardDescription>
            <CardTitle className="text-2xl font-bold text-rose-400 flex items-center justify-between">
              {metrics 
                ? `${((metrics.failed_runs_count / (metrics.total_pipeline_runs || 1)) * 100).toFixed(1)}%` 
                : "—"
              }
              <AlertTriangle className="w-4 h-4 text-rose-400" />
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Accumulated LLM Spend</CardDescription>
            <CardTitle className="text-2xl font-bold text-emerald-400 flex items-center justify-between">
              ${metrics?.total_llm_cost?.toFixed(2) ?? "—"}
              <Zap className="w-4 h-4 text-emerald-400" />
            </CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/50 bg-card/40 backdrop-blur-sm">
          <CardHeader className="p-4 pb-2">
            <CardDescription className="text-xs">Waiting Celery Jobs</CardDescription>
            <CardTitle className="text-2xl font-bold flex items-center justify-between">
              {metrics?.waiting_jobs_count ?? "—"}
              <Server className="w-4 h-4 text-muted-foreground" />
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Pipeline Control Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card/30 border border-border/50 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            Active Run Trace
            {activeRun?.run_id && (
              <Badge variant="outline" className="font-mono text-[10px] py-0 px-2 select-all">
                Run ID: {activeRun.run_id}
              </Badge>
            )}
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Status: <span className="font-semibold text-foreground uppercase">{activeRun?.status || "Idle"}</span>
          </p>
        </div>
        <Button
          onClick={() => triggerIngestion.mutate()}
          disabled={triggerIngestion.isPending || activeRun?.status === "running"}
          className="rounded-xl flex items-center gap-2 shadow-lg shadow-primary/10"
        >
          <Play className="w-4 h-4" />
          Trigger Pipeline Run
        </Button>
      </div>

      {/* DAG Node Graph Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <Card className="xl:col-span-2 border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden">
          <CardHeader className="border-b border-border/30">
            <CardTitle className="text-base font-semibold">Intelligence Pipeline Flow</CardTitle>
            <CardDescription>
              Click a stage box to view trace variables, latencies, errors, and metadata.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            {isPipelineLoading ? (
              <div className="py-24 text-center">
                <RefreshCw className="w-8 h-8 text-primary animate-spin mx-auto mb-4" />
                <p className="text-sm text-muted-foreground">Loading pipeline DAG status...</p>
              </div>
            ) : (
              <div className="relative">
                {/* SVG connection lines representing DAG edges */}
                <div className="hidden lg:block absolute inset-0 pointer-events-none opacity-20">
                  {/* Visual helper lines */}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 relative">
                  {PIPELINE_ORDER.map((node, index) => {
                    const stageRun = getStageStatus(node.key);
                    const isSelected = selectedStage?.stage === node.key;
                    
                    return (
                      <button
                        key={node.key}
                        onClick={() => setSelectedStage(stageRun || {
                          stage: node.key,
                          status: "pending",
                          started_at: "",
                          completed_at: null,
                          latency_ms: null,
                          error: null
                        })}
                        className={`flex flex-col text-left p-4 rounded-xl border transition-all duration-300 relative group overflow-hidden ${getStageColor(stageRun?.status)} ${
                          isSelected ? "ring-2 ring-primary ring-offset-2 ring-offset-background scale-[1.02]" : "hover:border-primary/40 hover:scale-[1.01]"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                            Step {String(index + 1).padStart(2, "0")}
                          </span>
                          {stageRun?.status === "success" || stageRun?.status === "completed" ? (
                            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                          ) : stageRun?.status === "failed" ? (
                            <AlertTriangle className="w-4 h-4 text-rose-400" />
                          ) : stageRun?.status === "running" ? (
                            <RefreshCw className="w-4 h-4 text-sky-400 animate-spin" />
                          ) : stageRun?.status === "skipped" ? (
                            <Info className="w-4 h-4 text-muted-foreground" />
                          ) : (
                            <Clock className="w-4 h-4 text-muted-foreground/40" />
                          )}
                        </div>

                        <h3 className="font-bold text-sm text-foreground mt-2 group-hover:text-primary transition-colors">
                          {node.label}
                        </h3>
                        <p className="text-[11px] text-muted-foreground mt-1 line-clamp-1">
                          {node.description}
                        </p>

                        {stageRun && stageRun.latency_ms !== null && (
                          <div className="flex items-center gap-1 mt-3 text-[10px] font-mono text-muted-foreground bg-background/50 px-2 py-0.5 rounded w-fit">
                            <Clock className="w-3 h-3" />
                            {stageRun.latency_ms >= 1000 
                              ? `${(stageRun.latency_ms / 1000).toFixed(2)}s` 
                              : `${stageRun.latency_ms.toFixed(0)}ms`
                            }
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Stage Inspector Detail sidebar */}
        <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl h-fit">
          <CardHeader className="border-b border-border/30">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Server className="w-4 h-4 text-primary" />
              Stage Inspector
            </CardTitle>
            <CardDescription>
              Detailed logs and variables for the selected execution node.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-6">
            {selectedStage ? (
              <div className="space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-foreground capitalize">
                    {selectedStage.stage.replace(/_/g, " ")}
                  </h3>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant={selectedStage.status === "success" || selectedStage.status === "completed" ? "secondary" : "outline"} className="capitalize">
                      {selectedStage.status}
                    </Badge>
                    {selectedStage.latency_ms !== null && (
                      <span className="text-xs font-mono text-muted-foreground">
                        Duration: {selectedStage.latency_ms.toFixed(1)}ms
                      </span>
                    )}
                  </div>
                </div>

                <div className="space-y-3.5 border-t border-border/20 pt-4">
                  <div className="grid grid-cols-3 text-xs">
                    <span className="text-muted-foreground">Started At:</span>
                    <span className="col-span-2 text-foreground font-mono truncate">
                      {selectedStage.started_at ? new Date(selectedStage.started_at).toLocaleString() : "Pending run"}
                    </span>
                  </div>
                  {selectedStage.completed_at && (
                    <div className="grid grid-cols-3 text-xs">
                      <span className="text-muted-foreground">Completed At:</span>
                      <span className="col-span-2 text-foreground font-mono truncate">
                        {new Date(selectedStage.completed_at).toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>

                {selectedStage.error && (
                  <div className="border border-rose-500/20 bg-rose-500/5 p-4 rounded-xl space-y-2">
                    <div className="flex items-center gap-2 text-rose-400 text-xs font-bold">
                      <AlertTriangle className="w-4 h-4" />
                      Execution Failed Error
                    </div>
                    <pre className="text-[10px] font-mono text-rose-300 p-2 bg-rose-950/20 rounded overflow-x-auto whitespace-pre-wrap max-h-[180px]">
                      {selectedStage.error}
                    </pre>
                  </div>
                )}

                <div className="bg-background/40 p-4 rounded-xl space-y-3">
                  <h4 className="text-xs font-bold text-foreground">Trace Correlation Context</h4>
                  <div className="space-y-2 text-[11px] font-mono text-muted-foreground">
                    <div className="flex justify-between border-b border-border/10 pb-1.5">
                      <span>Trace ID:</span>
                      <span className="text-foreground select-all">{activeRun?.run_id ? "correlation-active" : "—"}</span>
                    </div>
                    <div className="flex justify-between border-b border-border/10 pb-1.5">
                      <span>Worker Pool:</span>
                      <span className="text-foreground">Celery (prefork)</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Engine:</span>
                      <span className="text-foreground">news-pipeline-worker</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-16 text-center text-muted-foreground space-y-2">
                <HelpCircle className="w-8 h-8 mx-auto text-muted-foreground/40" />
                <p className="text-xs">No stage selected.</p>
                <p className="text-[10px] text-muted-foreground/60 max-w-[180px] mx-auto">
                  Select a pipeline stage on the left grid to inspect execution variables.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
