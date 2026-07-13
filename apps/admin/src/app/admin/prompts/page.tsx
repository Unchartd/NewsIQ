"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { FileText, Copy, ChevronDown, ChevronUp, Hash } from "lucide-react";
import { toast } from "sonner";

interface PromptVersion {
  id: string;
  stage: string;
  version: number;
  hash: string;
  system_template: string;
  user_template: string;
  is_active: boolean;
  created_at: string;
  prompt_uri?: string;
  schema_version?: string;
  preferred_model?: string;
  lifecycle_state?: string;
  parent_uri?: string;
  deprecated_at?: string;
  deprecated_reason?: string;
  superseded_by?: string;
}

export default function PromptsPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState("all");

  const { data: prompts, isLoading } = useQuery<PromptVersion[]>({
    queryKey: ["admin-prompts"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/prompts");
      const raw = Array.isArray(res.data) ? res.data : res.data?.prompts ?? [];
      return raw.map((p: Record<string, unknown>) => ({
        id: p.id,
        stage: p.stage,
        version: p.version,
        hash: p.prompt_hash,
        system_template: p.system_prompt,
        user_template: p.user_prompt_template,
        is_active: p.is_active,
        created_at: p.created_at,
        prompt_uri: p.prompt_uri,
        schema_version: p.schema_version,
        preferred_model: p.preferred_model,
        lifecycle_state: p.lifecycle_state,
        parent_uri: p.parent_uri,
        deprecated_at: p.deprecated_at,
        deprecated_reason: p.deprecated_reason,
        superseded_by: p.superseded_by,
      }));
    },
  });

  const stages = prompts ? ["all", ...new Set(prompts.map((p) => p.stage))] : ["all"];
  const filtered =
    stageFilter === "all" ? (prompts ?? []) : (prompts ?? []).filter((p) => p.stage === stageFilter);

  function copyToClipboard(text: string, label: string) {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
          <FileText className="w-6 h-6 text-primary" />
          Prompt Viewer
        </h1>
        <p className="text-slate-500 text-sm mt-1">Browse versioned prompt templates and prompt platform governance</p>
      </div>

      {/* Stage filter */}
      <div className="flex gap-2 flex-wrap">
        {stages.map((s) => (
          <button
            key={s}
            id={`prompt-filter-${s}`}
            onClick={() => setStageFilter(s)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all capitalize ${
              stageFilter === s
                ? "bg-primary text-white shadow-lg shadow-primary/20"
                : "glass border border-border text-slate-400 hover:text-slate-200"
            }`}
          >
            {s.replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Prompt cards */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 shimmer rounded-2xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-500">No prompts found.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((prompt) => (
            <div key={prompt.id} className="glass rounded-2xl overflow-hidden">
              {/* Header */}
              <button
                className="w-full flex items-center gap-3 px-5 py-4 hover:bg-white/2 transition-colors text-left"
                onClick={() => setExpandedId(expandedId === prompt.id ? null : prompt.id)}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="badge badge-primary capitalize">{prompt.stage.replace("_", " ")}</span>
                    <span className="badge badge-neutral">v{prompt.version}</span>
                    {prompt.is_active && <span className="badge badge-success">Active</span>}
                    {prompt.lifecycle_state && (
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-xl text-[10px] font-semibold capitalize ${
                        prompt.lifecycle_state === "production" ? "bg-emerald-500/10 text-emerald-400" :
                        prompt.lifecycle_state === "testing" ? "bg-amber-500/10 text-amber-400" :
                        "bg-rose-500/10 text-rose-400"
                      }`}>
                        {prompt.lifecycle_state}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <Hash className="w-3 h-3 text-slate-600" />
                    <span className="text-[10px] text-slate-600 font-mono">{prompt.hash?.slice(0, 16)}…</span>
                    <span className="text-[10px] text-slate-600">·</span>
                    <span className="text-[10px] text-slate-600">
                      {prompt.created_at ? new Date(prompt.created_at).toLocaleDateString() : "—"}
                    </span>
                  </div>
                </div>
                {expandedId === prompt.id ? (
                  <ChevronUp className="w-4 h-4 text-slate-500 shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-500 shrink-0" />
                )}
              </button>

              {/* Expanded content */}
              {expandedId === prompt.id && (
                <div className="border-t border-border px-5 py-4 space-y-4">
                  {/* Governance Metadata */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 bg-slate-950/40 rounded-xl p-4 border border-border">
                    {prompt.prompt_uri && (
                      <div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Prompt URI</div>
                        <div className="text-xs text-slate-300 font-mono mt-0.5 break-all">{prompt.prompt_uri}</div>
                      </div>
                    )}
                    {prompt.schema_version && (
                      <div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Schema Version</div>
                        <div className="text-xs text-slate-300 font-mono mt-0.5">{prompt.schema_version}</div>
                      </div>
                    )}
                    {prompt.preferred_model && (
                      <div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Preferred Model</div>
                        <div className="text-xs text-slate-300 font-mono mt-0.5">{prompt.preferred_model}</div>
                      </div>
                    )}
                    {prompt.lifecycle_state && (
                      <div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Lifecycle State</div>
                        <div className="mt-0.5">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold capitalize ${
                            prompt.lifecycle_state === "production" ? "bg-emerald-500/10 text-emerald-400" :
                            prompt.lifecycle_state === "testing" ? "bg-amber-500/10 text-amber-400" :
                            "bg-rose-500/10 text-rose-400"
                          }`}>
                            {prompt.lifecycle_state}
                          </span>
                        </div>
                      </div>
                    )}
                    {prompt.parent_uri && (
                      <div className="col-span-1 md:col-span-2">
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Parent URI</div>
                        <div className="text-xs text-slate-300 font-mono mt-0.5 break-all">{prompt.parent_uri}</div>
                      </div>
                    )}
                    {prompt.superseded_by && (
                      <div className="col-span-1 md:col-span-2">
                        <div className="text-[10px] font-semibold text-slate-500 uppercase text-rose-400">Superseded By</div>
                        <div className="text-xs text-rose-300 font-mono mt-0.5 break-all">{prompt.superseded_by}</div>
                      </div>
                    )}
                    {prompt.deprecated_reason && (
                      <div className="col-span-1 md:col-span-2 lg:col-span-3">
                        <div className="text-[10px] font-semibold text-rose-400 uppercase">Deprecation Reason</div>
                        <div className="text-xs text-rose-300 mt-0.5 leading-relaxed">{prompt.deprecated_reason}</div>
                      </div>
                    )}
                  </div>

                  {prompt.system_template && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">System Prompt</span>
                        <button
                          onClick={() => copyToClipboard(prompt.system_template, "System prompt")}
                          className="text-slate-600 hover:text-slate-400 transition-colors"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <pre className="text-[11px] text-slate-400 bg-background rounded-xl p-4 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed border border-border">
                        {prompt.system_template}
                      </pre>
                    </div>
                  )}
                  {prompt.user_template && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">User Template</span>
                        <button
                          onClick={() => copyToClipboard(prompt.user_template, "User template")}
                          className="text-slate-500 hover:text-slate-400 transition-colors"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <pre className="text-[11px] text-rose-300 bg-primary/5 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed border border-primary/10">
                        {prompt.user_template}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
