"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import { UserCheck, GitMerge, Scissors, Edit3, ExternalLink } from "lucide-react";

interface ReviewAction {
  id: string;
  action_type: string;
  story_id: string;
  user_email: string;
  created_at: string;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
  note?: string;
}

const ACTION_CONFIG: Record<string, { label: string; cls: string; icon: React.ElementType }> = {
  merge: { label: "Merge", cls: "badge-success", icon: GitMerge },
  split: { label: "Split", cls: "badge-warning", icon: Scissors },
  edit_summary: { label: "Edit", cls: "badge-primary", icon: Edit3 },
  wikidata_override: { label: "Wikidata", cls: "badge-neutral", icon: ExternalLink },
};

export default function ReviewPage() {
  const { data, isLoading } = useQuery<ReviewAction[]>({
    queryKey: ["admin-review"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/review");
      return Array.isArray(res.data) ? res.data : res.data?.actions ?? [];
    },
    refetchInterval: 30000,
  });

  const actions = data ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <UserCheck className="w-6 h-6 text-emerald-400" />
            Review Queue
          </h1>
          <p className="text-slate-500 text-sm mt-1">Human intervention audit log and override history</p>
        </div>
        <span className="text-xs text-slate-600 px-3 py-1.5 glass rounded-xl border border-[#1e2333]">
          {actions.length} actions
        </span>
      </div>

      <div className="space-y-3">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 shimmer rounded-2xl" />
          ))
        ) : actions.length === 0 ? (
          <div className="glass rounded-2xl py-16 text-center">
            <UserCheck className="w-10 h-10 text-slate-700 mx-auto mb-3" />
            <p className="text-slate-600 text-sm">No manual interventions recorded yet.</p>
          </div>
        ) : (
          actions.map((action) => {
            const cfg = ACTION_CONFIG[action.action_type] ?? {
              label: action.action_type,
              cls: "badge-neutral",
              icon: Edit3,
            };
            const Icon = cfg.icon;

            return (
              <div key={action.id} className="glass rounded-2xl p-5">
                <div className="flex items-start gap-4">
                  <div className="w-8 h-8 rounded-xl bg-[#1a1f2e] border border-[#1e2333] flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-slate-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`badge ${cfg.cls}`}>{cfg.label}</span>
                      <span className="text-xs text-slate-400 font-medium">{action.user_email}</span>
                      <span className="text-[10px] text-slate-600 ml-auto whitespace-nowrap">
                        {action.created_at ? new Date(action.created_at).toLocaleString() : "—"}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-600 font-mono mt-1">
                      Story: {action.story_id?.slice(0, 20)}…
                    </p>
                    {action.note && (
                      <p className="text-xs text-slate-400 mt-2 italic">&ldquo;{action.note}&rdquo;</p>
                    )}
                    {(action.before || action.after) && (
                      <div className="mt-3 grid grid-cols-2 gap-3">
                        {action.before && (
                          <div>
                            <p className="text-[9px] font-semibold text-red-400 uppercase tracking-wider mb-1">Before</p>
                            <pre className="text-[9px] text-slate-500 bg-[#1a1f2e] rounded-lg p-2 overflow-x-auto font-mono">
                              {JSON.stringify(action.before, null, 2)}
                            </pre>
                          </div>
                        )}
                        {action.after && (
                          <div>
                            <p className="text-[9px] font-semibold text-emerald-400 uppercase tracking-wider mb-1">After</p>
                            <pre className="text-[9px] text-slate-500 bg-[#1a1f2e] rounded-lg p-2 overflow-x-auto font-mono">
                              {JSON.stringify(action.after, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
