"use client";

import { useState, use } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/api-client";
import {
  AlertTriangle,
  ChevronLeft,
  Terminal,
  Activity,
  Layers,
  Database,
  RefreshCw,
  Cpu,
  Clock,
  CheckCircle,
  FileCode,
  CheckCircle2,
  Play,
  RotateCcw,
} from "lucide-react";

interface FailureDetail {
  failureId: string;
  traceId: string | null;
  runId: string | null;
  storyId: string | null;
  articleId: string | null;
  stage: string;
  provider: string | null;
  model: string | null;
  status: string;
  inputPayload: any;
  outputPayload: any;
  rawResponse: string | null;
  exception: string;
  stackTrace: string;
  errorCategory: string;
  errorCode: string | null;
  retryCount: number;
  latency: number;
  timestamp: string;
  resolved: boolean;
  resolutionNotes: string | null;
}

export default function FailureDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"stack" | "input" | "output" | "retry">("stack");
  
  // Resolution states
  const [isResolveOpen, setIsResolveOpen] = useState(false);
  const [resolutionNotes, setResolutionNotes] = useState("");
  
  // Replay states
  const [isReplayOpen, setIsReplayOpen] = useState(false);
  const [overrideProvider, setOverrideProvider] = useState("");
  const [overrideModel, setOverrideModel] = useState("");
  const [replayResult, setReplayResult] = useState<any>(null);

  const { data: failure, isLoading, refetch } = useQuery<FailureDetail>({
    queryKey: ["admin-failure-detail", id],
    queryFn: async () => {
      const res = await apiClient.get(`/admin/failures/${id}`);
      return res.data;
    },
  });

  const resolveMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/admin/failures/${id}/resolve`, {
        resolution_notes: resolutionNotes,
      });
    },
    onSuccess: () => {
      setIsResolveOpen(false);
      refetch();
    },
  });

  const replayMutation = useMutation({
    mutationFn: async () => {
      setReplayResult(null);
      const payload: Record<string, string> = {};
      if (overrideProvider) payload.provider = overrideProvider;
      if (overrideModel) payload.model = overrideModel;
      
      const res = await apiClient.post(`/admin/failures/${id}/replay`, payload);
      return res.data;
    },
    onSuccess: (resData) => {
      setReplayResult(resData);
      refetch();
    },
    onError: (err: any) => {
      setReplayResult({
        success: false,
        message: err.response?.data?.detail ?? "Execution failed.",
      });
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-2">
        <RefreshCw className="w-6 h-6 animate-spin text-primary" />
        Retrieving failure logs...
      </div>
    );
  }

  if (!failure) {
    return (
      <div className="text-center py-10 text-red-400">
        <AlertTriangle className="w-12 h-12 mx-auto mb-2 text-red-500" />
        Failure record not found.
      </div>
    );
  }

  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case "system_error":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      case "llm_error":
        return "text-red-400 bg-red-500/10 border-red-500/20";
      case "data_error":
        return "text-blue-400 bg-blue-500/10 border-blue-500/20";
      case "agent_error":
        return "text-purple-400 bg-purple-500/10 border-purple-500/20";
      default:
        return "text-slate-400 bg-slate-500/10 border-slate-500/20";
    }
  };

  const providers = ["google", "openai", "groq", "cerebras", "nvidia", "mock"];
  const modelsForProvider: Record<string, string[]> = {
    google: ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash-lite", "gemini-3.5-flash", "gemini-3.1-pro"],
    openai: ["gpt-4o-mini", "gpt-4o", "o1-mini"],
    groq: ["llama-3.3-70b-specdec", "mixtral-8x7b-32768"],
    cerebras: ["zai-glm-4.7", "gpt-oss-120b"],
    nvidia: ["mistralai/mistral-medium-3.5-128b", "deepseek-ai/deepseek-v4-flash", "nvidia/nemotron-3-super-120b-a12b"],
    mock: ["mock"],
  };

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-slate-200 transition-colors"
      >
        <ChevronLeft className="w-4 h-4" />
        Back to list
      </button>

      {/* Header Info */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-6">
        <div>
          <div className="flex items-center gap-3">
            <span
              className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border ${getCategoryColor(
                failure.errorCategory
              )}`}
            >
              {failure.errorCategory.replace("_", " ").toUpperCase()}
            </span>
            <span className="font-mono text-xs text-slate-500">ID: {failure.failureId}</span>
          </div>
          <h1 className="text-xl font-bold text-slate-100 mt-2 font-mono break-all leading-tight">
            {failure.exception}
          </h1>
          <p className="text-slate-500 text-xs mt-1.5">
            Occurred on: <span className="text-slate-400">{new Date(failure.timestamp).toLocaleString()}</span>
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3 shrink-0">
          {!failure.resolved && (
            <button
              onClick={() => setIsResolveOpen(true)}
              className="px-4 py-2 text-xs font-bold bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 text-slate-200 transition-all"
            >
              Mark Resolved
            </button>
          )}
          <button
            onClick={() => setIsReplayOpen(true)}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold bg-primary border border-primary/25 rounded-xl hover:bg-primary-hover text-white transition-all shadow-lg shadow-primary/20"
          >
            <Play className="w-3.5 h-3.5" /> Replay Stage
          </button>
        </div>
      </div>

      {/* Resolution box */}
      {failure.resolved && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-2xl p-4 flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <h4 className="text-sm font-semibold text-emerald-400">Resolved Error</h4>
            <p className="text-xs text-slate-400 mt-1">
              Notes: {failure.resolutionNotes || "No resolution details provided."}
            </p>
          </div>
        </div>
      )}

      {/* Summary grid cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Pipeline Stage", value: failure.stage.replace("_", " "), icon: Layers },
          { label: "Provider / Model", value: failure.provider ? `${failure.provider} / ${failure.model}` : "System failure", icon: Cpu },
          { label: "Latency", value: `${failure.latency.toFixed(2)} sec`, icon: Clock },
          { label: "Trace Context", value: failure.traceId ? `${failure.traceId.slice(0, 8)}...` : "—", icon: Database },
        ].map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} className="glass rounded-xl p-4 flex items-center gap-3">
              <div className="w-9 h-9 bg-white/5 border border-white/5 rounded-xl flex items-center justify-center shrink-0">
                <Icon className="w-4 h-4 text-slate-400" />
              </div>
              <div className="min-w-0">
                <p className="text-[10px] text-slate-500 uppercase tracking-wider">{c.label}</p>
                <p className="text-xs font-bold text-slate-200 truncate capitalize mt-0.5">{c.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Main content Tab panel */}
      <div className="glass rounded-2xl overflow-hidden border border-white/5">
        {/* Tabs Bar */}
        <div className="flex border-b border-white/5 bg-white/2">
          {[
            { id: "stack", label: "Stack Trace", icon: Terminal },
            { id: "input", label: "Inputs & Parameters", icon: FileCode },
            { id: "output", label: "Outputs & Response", icon: Activity },
            { id: "retry", label: "Retry History", icon: RotateCcw },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-5 py-4 border-b-2 text-xs font-semibold transition-all ${
                  isActive
                    ? "border-primary text-primary bg-white/5"
                    : "border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/2"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab contents */}
        <div className="p-5 min-h-[300px]">
          {/* Stack trace */}
          {activeTab === "stack" && (
            <div className="space-y-4">
              <div className="flex justify-between items-center bg-white/2 px-4 py-2.5 rounded-xl border border-white/5 text-[10px] text-slate-500">
                <span>Stack Trace Log ({failure.exception.split(":")[0]})</span>
              </div>
              <pre className="p-4 bg-[#0a0f1d] border border-white/5 rounded-xl text-xs text-red-300 font-mono overflow-auto max-h-[500px] leading-relaxed shadow-inner">
                {failure.stackTrace || "No traceback log recorded."}
              </pre>
            </div>
          )}

          {/* Inputs & Parameters */}
          {activeTab === "input" && (
            <div className="space-y-4">
              <div className="bg-white/2 px-4 py-2.5 rounded-xl border border-white/5 text-[10px] text-slate-500">
                Preserved Raw Inputs required to Replay this stage
              </div>
              <pre className="p-4 bg-[#0a0f1d] border border-white/5 rounded-xl text-xs text-blue-300 font-mono overflow-auto max-h-[500px] shadow-inner">
                {failure.inputPayload
                  ? JSON.stringify(failure.inputPayload, null, 2)
                  : "No input parameters logged."}
              </pre>
            </div>
          )}

          {/* Outputs */}
          {activeTab === "output" && (
            <div className="space-y-4">
              <div className="bg-white/2 px-4 py-2.5 rounded-xl border border-white/5 text-[10px] text-slate-500">
                Raw LLM Provider Output Response or Error Object
              </div>
              {failure.rawResponse ? (
                <pre className="p-4 bg-[#0a0f1d] border border-white/5 rounded-xl text-xs text-slate-300 font-mono overflow-auto max-h-[500px] shadow-inner">
                  {failure.rawResponse}
                </pre>
              ) : (
                <div className="text-slate-500 text-xs italic p-4 text-center">
                  No raw provider responses recorded.
                </div>
              )}
            </div>
          )}

          {/* Retry history */}
          {activeTab === "retry" && (
            <div className="space-y-6">
              <div className="bg-white/2 px-4 py-2.5 rounded-xl border border-white/5 text-[10px] text-slate-500">
                Execution Fallback Chain (Total Retries: {failure.retryCount})
              </div>

              {/* Retry steps visualizer */}
              <div className="relative pl-8 border-l border-white/10 space-y-8 py-2 ml-4">
                <div className="relative">
                  <span className="absolute -left-11 w-6 h-6 rounded-full bg-red-500/15 border border-red-500/35 flex items-center justify-center text-xs font-bold text-red-400">
                    1
                  </span>
                  <div className="glass rounded-xl p-4">
                    <h4 className="text-xs font-bold text-slate-200">
                      Primary Execution Attempt — Failed
                    </h4>
                    <p className="text-[10px] text-slate-500 mt-1 font-mono">
                      Stage: {failure.stage} | Provider: {failure.provider || "system"}
                    </p>
                    <p className="text-[10px] text-red-400 font-semibold mt-2">
                      Error: {failure.exception.split(":")[1] || failure.exception}
                    </p>
                  </div>
                </div>

                {failure.retryCount > 0 && (
                  <div className="relative">
                    <span className="absolute -left-11 w-6 h-6 rounded-full bg-amber-500/15 border border-amber-500/35 flex items-center justify-center text-xs font-bold text-amber-400 animate-pulse">
                      {failure.retryCount + 1}
                    </span>
                    <div className="glass rounded-xl p-4">
                      <h4 className="text-xs font-bold text-slate-200">
                        Gateway Fallback Attempt {failure.retryCount + 1} — Failed
                      </h4>
                      <p className="text-[10px] text-slate-500 mt-1 font-mono">
                        Fallback model and keys exhausted. Exiting.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* RESOLVE DIALOG MODAL */}
      {isResolveOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass rounded-2xl w-full max-w-md p-6 border border-white/10 shadow-2xl relative animate-fade-in">
            <h3 className="text-base font-bold text-slate-100 mb-2">Resolve Failure</h3>
            <p className="text-slate-500 text-xs mb-4">
              Enter notes describing how this error was resolved (e.g. key replaced, code fixed).
            </p>
            <textarea
              rows={3}
              value={resolutionNotes}
              onChange={(e) => setResolutionNotes(e.target.value)}
              placeholder="Enter resolution details..."
              className="w-full p-3 text-xs bg-white/5 border border-white/10 rounded-xl focus:outline-none focus:border-primary text-slate-100 placeholder-slate-655"
            />
            <div className="flex justify-end gap-3 mt-4">
              <button
                onClick={() => setIsResolveOpen(false)}
                className="px-3.5 py-2 rounded-xl text-xs font-bold border border-white/10 text-slate-400 hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                disabled={resolveMutation.isPending || !resolutionNotes.trim()}
                onClick={() => resolveMutation.mutate()}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-primary hover:bg-primary-hover text-white disabled:opacity-40"
              >
                {resolveMutation.isPending ? "Submitting..." : "Confirm Resolve"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* REPLAY CONTROLS MODAL */}
      {isReplayOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass rounded-2xl w-full max-w-xl p-6 border border-white/10 shadow-2xl relative animate-fade-in max-h-[90vh] overflow-y-auto">
            <h3 className="text-base font-bold text-slate-100 mb-2">Replay Stage</h3>
            <p className="text-slate-500 text-xs mb-4">
              Re-execute the failed stage of this pipeline. You can optionally override the model and provider.
            </p>

            <div className="grid grid-cols-2 gap-4 mb-4">
              {/* Provider Selection */}
              <div>
                <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-semibold">
                  Provider Override
                </label>
                <select
                  value={overrideProvider}
                  onChange={(e) => {
                    setOverrideProvider(e.target.value);
                    setOverrideModel(""); // Reset model when provider changes
                  }}
                  className="w-full px-3 py-2 text-xs bg-card border border-white/10 rounded-xl focus:outline-none text-slate-300"
                >
                  <option value="">Default Provider</option>
                  {providers.map((p) => (
                    <option key={p} value={p}>
                      {p.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              {/* Model Selection */}
              <div>
                <label className="block text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-semibold">
                  Model Override
                </label>
                <select
                  disabled={!overrideProvider}
                  value={overrideModel}
                  onChange={(e) => setOverrideModel(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-card border border-white/10 rounded-xl focus:outline-none text-slate-300 disabled:opacity-40"
                >
                  <option value="">Default Model</option>
                  {overrideProvider &&
                    modelsForProvider[overrideProvider]?.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                </select>
              </div>
            </div>

            {/* Replay Result section */}
            {replayMutation.isPending && (
              <div className="flex flex-col items-center justify-center p-8 bg-white/2 border border-white/5 rounded-xl gap-2 mb-4">
                <RefreshCw className="w-5 h-5 animate-spin text-primary" />
                <span className="text-xs text-slate-400">Replaying stage, please wait...</span>
              </div>
            )}

            {replayResult && (
              <div
                className={`p-4 rounded-xl border mb-4 text-xs font-mono max-h-[300px] overflow-auto ${
                  replayResult.success
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                    : "bg-red-500/10 border-red-500/20 text-red-300"
                }`}
              >
                <div className="flex items-center gap-2 font-bold mb-2">
                  {replayResult.success ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      Stage Replay Succeeded
                    </>
                  ) : (
                    <>
                      <AlertTriangle className="w-4 h-4 text-red-400" />
                      Stage Replay Failed
                    </>
                  )}
                </div>
                <p className="text-[11px] font-sans text-slate-400 mb-2">{replayResult.message}</p>
                {replayResult.output && (
                  <pre className="p-3 bg-black/30 rounded-lg text-[10px] leading-relaxed">
                    {JSON.stringify(replayResult.output, null, 2)}
                  </pre>
                )}
              </div>
            )}

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => {
                  setIsReplayOpen(false);
                  setReplayResult(null);
                }}
                className="px-3.5 py-2 rounded-xl text-xs font-bold border border-white/10 text-slate-400 hover:bg-white/5"
              >
                Close
              </button>
              <button
                disabled={replayMutation.isPending}
                onClick={() => replayMutation.mutate()}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-primary hover:bg-primary-hover text-white disabled:opacity-40"
              >
                <Play className="w-3.5 h-3.5" />
                {replayMutation.isPending ? "Executing..." : "Run Replay"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
