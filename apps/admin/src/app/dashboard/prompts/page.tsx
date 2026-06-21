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
}

export default function PromptsPage() {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState("all");

  const { data: prompts, isLoading } = useQuery<PromptVersion[]>({
    queryKey: ["admin-prompts"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/prompts");
      const raw = Array.isArray(res.data) ? res.data : res.data?.prompts ?? [];
      return raw.map((p: any) => ({
        id: p.id,
        stage: p.stage,
        version: p.version,
        hash: p.prompt_hash,
        system_template: p.system_prompt,
        user_template: p.user_prompt_template,
        is_active: p.is_active,
        created_at: p.created_at,
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
        <p className="text-slate-500 text-sm mt-1">Browse versioned prompt templates by pipeline stage</p>
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
        <div className="text-center py-12 text-slate-655">No prompts found.</div>
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
                  <ChevronUp className="w-4 h-4 text-slate-550 shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-550 shrink-0" />
                )}
              </button>

              {/* Expanded content */}
              {expandedId === prompt.id && (
                <div className="border-t border-border px-5 py-4 space-y-4">
                  {prompt.system_template && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] font-semibold text-slate-550 uppercase tracking-wider">System Prompt</span>
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
                        <span className="text-[10px] font-semibold text-slate-555 uppercase tracking-wider">User Template</span>
                        <button
                          onClick={() => copyToClipboard(prompt.user_template, "User template")}
                          className="text-slate-655 hover:text-slate-400 transition-colors"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <pre className="text-[11px] text-rose-350 bg-primary/5 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed border border-primary/10">
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
