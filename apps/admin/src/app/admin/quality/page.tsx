"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import {
  Shield,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronUp,
  Terminal,
  AlertTriangle,
  Award,
  BookOpen,
  Info
} from "lucide-react";
import { toast } from "sonner";

interface ScenarioMetrics {
  headline_keyword_score: number;
  category_match_score: number;
  facts_score: number;
  forbidden_words_penalties: number;
  forbidden_words_found: string[];
}

interface ScenarioOutputs {
  headline: string;
  category: string;
  one_line_summary: string;
  key_facts_count: number;
}

interface ScenarioResult {
  scenario_id: string;
  description: string;
  duration_seconds: number;
  score: number;
  is_passed: boolean;
  metrics: ScenarioMetrics;
  outputs: ScenarioOutputs;
}

interface EvaluationReport {
  timestamp: string;
  summary: {
    total_scenarios: number;
    passed: number;
    failed: number;
    pass_rate_percent: number;
    average_score: number;
  };
  scenarios: ScenarioResult[];
}

export default function QualityPage() {
  const queryClient = useQueryClient();
  const [expandedScenario, setExpandedScenario] = useState<string | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<string | null>(null);

  const { data: report, isLoading, isError } = useQuery<EvaluationReport>({
    queryKey: ["evaluation-report"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/evaluation/report");
      return res.data;
    }
  });

  const runMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post("/admin/evaluation/run");
      return res.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        toast.success("Quality evaluation finished successfully!");
      } else {
        toast.error(`Evaluation failed with exit code ${data.exit_code}`);
      }
      if (data.stdout || data.stderr) {
        setConsoleLogs(data.stdout + "\n" + data.stderr);
      }
      queryClient.setQueryData(["evaluation-report"], data.report);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || "Failed to trigger evaluation run");
    }
  });

  function toggleScenario(id: string) {
    setExpandedScenario(expandedScenario === id ? null : id);
  }

  const summary = report?.summary;
  const scenarios = report?.scenarios ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Shield className="w-6 h-6 text-emerald-400" />
            Quality Evaluation Framework
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Ground-truth regression testing, keyword alignment, and fact extraction quality gates.
          </p>
        </div>
        
        <button
          onClick={() => {
            setConsoleLogs(null);
            runMutation.mutate();
          }}
          disabled={runMutation.isPending}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 disabled:opacity-50 text-white font-medium shadow-lg shadow-emerald-950/20 transition-all font-semibold"
        >
          {runMutation.isPending ? (
            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          ) : (
            <Play className="w-4 h-4 fill-current" />
          )}
          {runMutation.isPending ? "Executing Run..." : "Run Quality Evaluation"}
        </button>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-12 space-y-3">
          <div className="w-8 h-8 border-4 border-emerald-500/20 border-t-emerald-400 rounded-full animate-spin" />
          <p className="text-sm text-slate-500">Loading evaluation reports...</p>
        </div>
      ) : isError && !runMutation.isPending ? (
        <div className="glass border-red-500/20 rounded-2xl p-6 flex flex-col items-center text-center space-y-4">
          <AlertTriangle className="w-12 h-12 text-red-400" />
          <div>
            <h3 className="font-bold text-slate-200">No Evaluation Report Found</h3>
            <p className="text-slate-500 text-sm mt-1 max-w-md">
              The quality evaluation runner has not been executed yet. Click the button above to launch the initial offline test run.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* Metrics summary cards */}
          {summary && (
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
              {[
                { label: "Total Scenarios", value: summary.total_scenarios, icon: BookOpen, color: "text-blue-400 bg-blue-500/10 border-blue-500/25" },
                { label: "Passed", value: summary.passed, icon: CheckCircle2, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/25" },
                { label: "Failed", value: summary.failed, icon: XCircle, color: summary.failed > 0 ? "text-red-400 bg-red-500/10 border-red-500/25" : "text-slate-400 bg-slate-500/10 border-slate-500/25" },
                { label: "Pass Rate", value: `${summary.pass_rate_percent.toFixed(0)}%`, icon: Award, color: summary.pass_rate_percent >= 80 ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/25" : "text-amber-400 bg-amber-500/10 border-amber-500/25" },
                { label: "Average Score", value: `${summary.average_score.toFixed(1)}%`, icon: Info, color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/25" },
              ].map((c) => {
                const Icon = c.icon;
                return (
                  <div key={c.label} className={`glass rounded-2xl p-5 border ${c.color}`}>
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-2xl font-bold text-slate-100 tabular-nums">{c.value}</p>
                        <p className="text-xs text-slate-400 mt-1 font-medium">{c.label}</p>
                      </div>
                      <Icon className="w-5 h-5 opacity-80" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Console stdout view */}
          {consoleLogs && (
            <div className="glass border-slate-800 rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 border-b border-slate-800 pb-2">
                <Terminal className="w-4 h-4 text-emerald-400" />
                Console Output Log
              </div>
              <pre className="bg-slate-950/80 border border-slate-900 rounded-xl p-4 font-mono text-[11px] text-emerald-400 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                {consoleLogs}
              </pre>
            </div>
          )}

          {/* Scenario results list */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-400 px-1">Scenario Breakdown</h3>
            {scenarios.map((sc) => {
              const isExpanded = expandedScenario === sc.scenario_id;
              return (
                <div
                  key={sc.scenario_id}
                  className={`glass border rounded-2xl overflow-hidden transition-all duration-200 ${
                    sc.is_passed ? "border-slate-800 hover:border-emerald-500/30" : "border-red-500/20 hover:border-red-500/30"
                  }`}
                >
                  {/* Scenario Header */}
                  <div
                    onClick={() => toggleScenario(sc.scenario_id)}
                    className="p-5 flex items-center justify-between gap-4 cursor-pointer select-none"
                  >
                    <div className="flex items-center gap-3">
                      {sc.is_passed ? (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-400 shrink-0" />
                      )}
                      <div>
                        <h4 className="font-bold text-slate-200 text-sm leading-snug">
                          {sc.description}
                        </h4>
                        <p className="text-xs text-slate-500 mt-1 font-mono">{sc.scenario_id}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span
                          className={`text-sm font-extrabold tabular-nums ${
                            sc.is_passed ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {sc.score.toFixed(0)}%
                        </span>
                        <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                          {sc.duration_seconds.toFixed(2)}s
                        </p>
                      </div>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Scenario Details */}
                  {isExpanded && (
                    <div className="px-5 pb-5 pt-2 border-t border-slate-900 bg-slate-950/20 space-y-4 text-xs">
                      {/* Metric Scores */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {[
                          { label: "Keyword Match", val: sc.metrics.headline_keyword_score },
                          { label: "Category Match", val: sc.metrics.category_match_score },
                          { label: "Facts Coverage", val: sc.metrics.facts_score },
                          { label: "Penalties", val: -sc.metrics.forbidden_words_penalties, isPenalty: true }
                        ].map((m) => (
                          <div key={m.label} className="bg-slate-950/40 border border-slate-900 rounded-xl p-3 text-center">
                            <p className="text-slate-500 font-medium mb-1">{m.label}</p>
                            <span
                              className={`font-bold tabular-nums text-sm ${
                                m.isPenalty && m.val < 0
                                  ? "text-red-400"
                                  : m.val === 100
                                  ? "text-emerald-400"
                                  : "text-slate-300"
                              }`}
                            >
                              {m.val.toFixed(0)}%
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Forbidden words penalty alerts */}
                      {sc.metrics.forbidden_words_found.length > 0 && (
                        <div className="flex items-center gap-2 p-3 bg-red-950/25 border border-red-500/20 text-red-400 rounded-xl">
                          <AlertTriangle className="w-4 h-4 shrink-0" />
                          <span>
                            Forbidden words detected in generated outputs:{" "}
                            <strong className="font-mono">{sc.metrics.forbidden_words_found.join(", ")}</strong>
                          </span>
                        </div>
                      )}

                      {/* Outputs */}
                      <div className="space-y-3 bg-slate-950/50 border border-slate-900 rounded-xl p-4">
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">Generated Headline</p>
                          <p className="text-slate-200 font-semibold">{sc.outputs.headline || "—"}</p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">Generated Category</p>
                          <span className="px-2 py-0.5 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-md">
                            {sc.outputs.category || "—"}
                          </span>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">One Line Summary</p>
                          <p className="text-slate-400 italic leading-relaxed">
                            {sc.outputs.one_line_summary || "—"}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">Key Facts Count</p>
                          <p className="text-slate-300 font-medium">{sc.outputs.key_facts_count} facts generated</p>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
