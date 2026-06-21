"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import {
  ArrowLeft,
  Layers,
  Users,
  Zap,
  Clock,
  DollarSign,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";

const TABS = ["Overview", "Articles", "Entities", "LLM Traces", "Replay"] as const;
type Tab = (typeof TABS)[number];

export default function StoryInspectorPage() {
  const params = useParams();
  const router = useRouter();
  const storyId = params.storyId as string;
  const [tab, setTab] = useState<Tab>("Overview");

  const { data: story, isLoading } = useQuery({
    queryKey: ["story-inspect", storyId],
    queryFn: async () => {
      const res = await apiClient.get(`/admin/stories/${storyId}/inspect`);
      return res.data;
    },
    enabled: !!storyId,
  });

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-8 w-64 shimmer rounded-xl" />
        <div className="h-40 shimmer rounded-2xl" />
      </div>
    );
  }

  if (!story) {
    return (
      <div className="text-center py-16">
        <AlertTriangle className="w-10 h-10 text-slate-600 mx-auto mb-3" />
        <p className="text-slate-500">Story not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors mb-4"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Stories
        </button>
        <h1 className="text-xl font-bold text-slate-100">
          {story.canonical_headline ?? "Story Inspector"}
        </h1>
        <p className="text-slate-500 text-xs mt-1 font-mono">ID: {storyId}</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            id={`story-tab-${t.toLowerCase().replace(" ", "-")}`}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-all ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "Overview" && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Article Count", value: story.article_count ?? "—", icon: Layers, color: "text-rose-450" },
            { label: "Cluster Confidence", value: story.cluster_confidence != null ? `${(story.cluster_confidence * 100).toFixed(1)}%` : "—", icon: CheckCircle2, color: "text-emerald-400" },
            { label: "Entity Count", value: story.entities?.length ?? "—", icon: Users, color: "text-blue-405" },
            { label: "LLM Calls", value: story.llm_calls?.length ?? "—", icon: Zap, color: "text-amber-400" },
          ].map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.label} className="glass rounded-xl p-4">
                <Icon className={`w-5 h-5 ${card.color} mb-2`} />
                <p className="text-xl font-bold text-slate-100">{card.value}</p>
                <p className="text-xs text-slate-550 mt-0.5">{card.label}</p>
              </div>
            );
          })}
          {story.summary && (
            <div className="col-span-2 lg:col-span-4 glass rounded-xl p-5">
              <h3 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">AI Summary</h3>
              <p className="text-sm text-slate-350 leading-relaxed">{story.summary}</p>
            </div>
          )}
          {story.contradictions?.length > 0 && (
            <div className="col-span-2 lg:col-span-4 glass rounded-xl p-5 border border-amber-500/20">
              <h3 className="text-xs font-semibold text-amber-400 mb-3 flex items-center gap-2 uppercase tracking-wider">
                <AlertTriangle className="w-3.5 h-3.5" />
                Contradictions Detected ({story.contradictions.length})
              </h3>
              <div className="space-y-2">
                {story.contradictions.map((c: { claim_a: string; claim_b: string; confidence: number }, i: number) => (
                  <div key={i} className="text-xs text-slate-400 p-3 bg-amber-500/5 rounded-lg border border-amber-500/10">
                    <p><span className="text-amber-400 font-semibold">A:</span> {c.claim_a}</p>
                    <p className="mt-1"><span className="text-amber-400 font-semibold">B:</span> {c.claim_b}</p>
                    <p className="mt-1 text-slate-600 font-mono">Confidence: {(c.confidence * 100).toFixed(1)}%</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "Articles" && (
        <div className="space-y-3">
          {(story.articles ?? []).length === 0 ? (
            <p className="text-slate-600 text-sm text-center py-8">No articles attached.</p>
          ) : (
            story.articles.map((a: { id: string; title: string; url: string; source_name: string; published_at: string; similarity_score: number }, i: number) => (
              <div key={i} className="glass rounded-xl p-4 flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-200 line-clamp-1">{a.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{a.source_name} · {a.published_at ? new Date(a.published_at).toLocaleDateString() : "—"}</p>
                </div>
                {a.similarity_score != null && (
                  <span className={`badge shrink-0 ${a.similarity_score > 0.8 ? "badge-success" : "badge-warning"}`}>
                    {(a.similarity_score * 100).toFixed(0)}% match
                  </span>
                )}
                {a.url && (
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/80 shrink-0">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {tab === "Entities" && (
        <div className="glass rounded-2xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="border-b border-border">
              <tr>
                <th className="text-left px-5 py-3 text-slate-500 font-semibold">Entity</th>
                <th className="text-left px-4 py-3 text-slate-500 font-semibold">Type</th>
                <th className="text-left px-4 py-3 text-slate-500 font-semibold">Wikidata</th>
                <th className="text-right px-4 py-3 text-slate-500 font-semibold">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {(story.entities ?? []).length === 0 ? (
                <tr><td colSpan={4} className="px-5 py-10 text-center text-slate-600">No entities found.</td></tr>
              ) : (
                story.entities.map((e: { name: string; type: string; wikidata_id?: string; confidence: number }, i: number) => (
                  <tr key={i} className="border-b border-border/50 hover:bg-white/2 transition-colors">
                    <td className="px-5 py-3 font-medium text-slate-200">{e.name}</td>
                    <td className="px-4 py-3"><span className="badge badge-neutral">{e.type}</span></td>
                    <td className="px-4 py-3">
                      {e.wikidata_id ? (
                        <a href={`https://www.wikidata.org/wiki/${e.wikidata_id}`} target="_blank" rel="noopener noreferrer" className="text-primary hover:text-primary/80 flex items-center gap-1 font-mono">
                          {e.wikidata_id} <ExternalLink className="w-3 h-3" />
                        </a>
                      ) : <span className="text-slate-650">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-400">{(e.confidence * 100).toFixed(1)}%</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "LLM Traces" && (
        <div className="space-y-4">
          {(story.llm_calls ?? []).length === 0 ? (
            <p className="text-slate-600 text-sm text-center py-8">No LLM traces recorded.</p>
          ) : (
            story.llm_calls.map((call: { model: string; stage: string; latency_ms: number; input_tokens: number; output_tokens: number; cost_usd: number; system_prompt?: string; user_prompt?: string; completion?: string }, i: number) => (
              <div key={i} className="glass rounded-xl p-5 space-y-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="badge badge-primary">{call.model}</span>
                  <span className="badge badge-neutral">{call.stage}</span>
                  <span className="text-xs text-slate-500 flex items-center gap-1 ml-auto">
                    <Clock className="w-3 h-3" /> {call.latency_ms}ms
                  </span>
                  <span className="text-xs text-slate-500 flex items-center gap-1">
                    <Zap className="w-3 h-3" /> {call.input_tokens + call.output_tokens} tokens
                  </span>
                  <span className="text-xs text-amber-400 flex items-center gap-1">
                    <DollarSign className="w-3 h-3" /> ${call.cost_usd?.toFixed(6)}
                  </span>
                </div>
                {call.system_prompt && (
                  <div>
                    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">System Prompt</p>
                    <pre className="text-[10px] text-slate-400 bg-background border border-border rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">{call.system_prompt}</pre>
                  </div>
                )}
                {call.completion && (
                  <div>
                    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">Completion</p>
                    <pre className="text-[10px] text-emerald-400 bg-emerald-500/5 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed border border-emerald-500/10">{call.completion}</pre>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {tab === "Replay" && (
        <div className="glass rounded-2xl p-6 space-y-4">
          <h3 className="text-sm font-semibold text-slate-200">Pipeline Replay</h3>
          <p className="text-xs text-slate-500">Re-run the story intelligence pipeline for this story cluster.</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {["full", "entity_linking", "summarization", "contradiction", "timeline"].map((stage) => (
              <button
                key={stage}
                id={`replay-${stage}`}
                className="flex items-center gap-2 px-4 py-3 rounded-xl glass border border-border text-xs text-slate-400 hover:text-slate-200 hover:border-primary/30 transition-all"
                onClick={async () => {
                  try {
                    await apiClient.post(`/admin/stories/${storyId}/replay`, { stage: stage === "full" ? null : stage });
                    alert(`Replay queued: ${stage}`);
                  } catch { alert("Failed to queue replay."); }
                }}
              >
                <RefreshCw className="w-3.5 h-3.5" />
                {stage === "full" ? "Full Pipeline" : stage.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
