"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { 
  UserCheck, RefreshCw, Clock, ArrowRight, Eye, MessageSquare, 
  CheckCircle2, AlertTriangle, HelpCircle, ShieldAlert 
} from "lucide-react";
import apiClient from "@/lib/api-client";
import Link from "next/link";

interface HumanReviewItem {
  id: string;
  story_id: string;
  action: string;
  target_type: string | null;
  before_value: any;
  after_value: any;
  notes: string | null;
  created_at: string;
}

interface HumanReviewQueueResponse {
  reviews: HumanReviewItem[];
}

export default function ReviewPage() {
  // 1. Fetch human review audit trail
  const { data, isLoading, refetch } = useQuery<HumanReviewQueueResponse>({
    queryKey: ["admin-reviews"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/review/queue");
      return res.data;
    },
  });

  const reviews = data?.reviews || [];

  const getActionBadgeColor = (action: string) => {
    switch (action) {
      case "approve":
        return "bg-emerald-500/10 border-emerald-500 text-emerald-400";
      case "reject":
        return "bg-rose-500/10 border-rose-500 text-rose-400";
      case "merge":
        return "bg-sky-500/10 border-sky-500 text-sky-400";
      case "split":
        return "bg-amber-500/10 border-amber-500 text-amber-400";
      case "correct_entity":
        return "bg-purple-500/10 border-purple-500 text-purple-400";
      case "correct_summary":
        return "bg-indigo-500/10 border-indigo-500 text-indigo-400";
      default:
        return "bg-muted/10 border-muted text-muted-foreground";
    }
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex justify-between items-center bg-card/30 border border-border/50 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-primary" />
            Human Intervention & Review Logs
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Audit trail of human corrections, approvals, rejections, cluster overrides, and entity link overrides.
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()} className="rounded-xl">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Review Queue Feed */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="py-24 text-center text-xs text-muted-foreground">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
            Hydrating audit trail...
          </div>
        ) : reviews.length === 0 ? (
          <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl p-12 text-center text-muted-foreground">
            <HelpCircle className="w-12 h-12 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-sm">No intervention events recorded.</p>
            <p className="text-xs text-muted-foreground/60 mt-1 max-w-sm mx-auto">
              Any actions taken on story inspectors, cluster splits, or entity mappings will generate an audit trail here.
            </p>
          </Card>
        ) : (
          reviews.map((r) => (
            <Card key={r.id} className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden">
              <CardHeader className="p-5 border-b border-border/10 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className={`font-mono text-[9px] py-0 capitalize ${getActionBadgeColor(r.action)}`}>
                      {r.action.replace(/_/g, " ")}
                    </Badge>
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {new Date(r.created_at).toLocaleString()}
                    </span>
                  </div>
                  
                  {r.story_id && r.story_id !== "00000000-0000-0000-0000-000000000000" ? (
                    <div className="text-xs text-muted-foreground mt-1">
                      Target Story ID:{" "}
                      <Link 
                        href={`/admin/stories/${r.story_id}`}
                        className="font-mono text-primary hover:underline hover:text-primary-hover select-all"
                      >
                        {r.story_id}
                      </Link>
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground mt-1">
                      Target Scope: <span className="font-mono text-foreground font-semibold uppercase">Global Registry</span>
                    </div>
                  )}
                </div>

                {r.story_id && r.story_id !== "00000000-0000-0000-0000-000000000000" && (
                  <Link href={`/admin/stories/${r.story_id}`}>
                    <Button variant="outline" size="sm" className="rounded-xl text-[10px] h-8 px-2.5 flex items-center gap-1.5 ml-auto">
                      <Eye className="w-3.5 h-3.5" />
                      View Story Trace
                    </Button>
                  </Link>
                )}
              </CardHeader>

              <CardContent className="p-5 space-y-4">
                {/* Notes */}
                {r.notes && (
                  <div className="flex gap-2.5 p-3 rounded-xl border border-border bg-background/50 text-xs">
                    <MessageSquare className="w-4 h-4 shrink-0 text-primary mt-0.5" />
                    <div>
                      <span className="text-[10px] font-bold text-muted-foreground block uppercase">Intervention Justification</span>
                      <p className="text-foreground leading-relaxed mt-0.5">{r.notes}</p>
                    </div>
                  </div>
                )}

                {/* JSON Values Diff comparison box */}
                {(r.before_value || r.after_value) && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {r.before_value && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider block">Before State</span>
                        <pre className="p-3 rounded-xl bg-background border border-rose-500/10 text-[10px] font-mono text-rose-300 overflow-x-auto whitespace-pre-wrap max-h-[160px]">
                          {JSON.stringify(r.before_value, null, 2)}
                        </pre>
                      </div>
                    )}
                    {r.after_value && (
                      <div className="space-y-1">
                        <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block">After State</span>
                        <pre className="p-3 rounded-xl bg-background border border-emerald-500/10 text-[10px] font-mono text-emerald-300 overflow-x-auto whitespace-pre-wrap max-h-[160px]">
                          {JSON.stringify(r.after_value, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
