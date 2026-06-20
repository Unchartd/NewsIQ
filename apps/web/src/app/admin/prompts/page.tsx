"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  FileText, Hash, CheckCircle, RefreshCw, Layers, Clock, AlertTriangle, 
  HelpCircle, Columns, ChevronRight, Eye 
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useState } from "react";

interface PromptVersion {
  id: string;
  prompt_hash: string;
  stage: string;
  system_prompt: string;
  user_prompt_template: string;
  version: number;
  is_active: boolean;
  created_at: string;
}

interface PromptComparisonResponse {
  prompts: PromptVersion[];
}

export default function PromptsPage() {
  const [selectedStage, setSelectedStage] = useState<string>("all");
  const [viewingPrompt, setViewingPrompt] = useState<PromptVersion | null>(null);
  const [comparePrompt, setComparePrompt] = useState<PromptVersion | null>(null);

  // 1. Fetch prompts list
  const { data, isLoading, refetch } = useQuery<PromptComparisonResponse>({
    queryKey: ["admin-prompts", selectedStage],
    queryFn: async () => {
      const params = selectedStage !== "all" ? { stage: selectedStage } : {};
      const res = await apiClient.get("/admin/prompts", { params });
      return res.data;
    },
  });

  const prompts = data?.prompts || [];

  // Group prompts by stage for easy navigation
  const stages = Array.from(new Set(prompts.map((p) => p.stage)));

  const handleSelectPrompt = (prompt: PromptVersion) => {
    setViewingPrompt(prompt);
    // Auto-select a previous version of the same stage for comparison if exists
    const previous = prompts.find(
      (p) => p.stage === prompt.stage && p.version === prompt.version - 1
    );
    setComparePrompt(previous || null);
  };

  return (
    <div className="space-y-6">
      {/* Title & Filter Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-card/30 border border-border/50 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            Prompt Version Registry
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Browse, inspect, and compare versioned prompt templates registered in the DB.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Filter Stage:</span>
          <Select value={selectedStage} onValueChange={(value) => {
            setSelectedStage(value);
            setViewingPrompt(null);
            setComparePrompt(null);
          }}>
            <SelectTrigger className="w-[180px] rounded-xl text-xs h-9 bg-background/50">
              <SelectValue placeholder="All Stages" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Stages</SelectItem>
              <SelectItem value="event_extraction">Event Extract</SelectItem>
              <SelectItem value="entity_extraction">Entity Extract</SelectItem>
              <SelectItem value="contradiction_detection">Contradictions</SelectItem>
              <SelectItem value="source_comparison">Bias Analysis</SelectItem>
              <SelectItem value="timeline_generation">Timeline</SelectItem>
              <SelectItem value="summary_generation">Summarization</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Prompts list */}
        <Card className="lg:col-span-1 border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden h-fit">
          <CardHeader className="border-b border-border/30">
            <CardTitle className="text-sm font-semibold">Registered Prompt Hashes</CardTitle>
            <CardDescription>Templates ordered by version history.</CardDescription>
          </CardHeader>
          <CardContent className="p-0 divide-y divide-border/20 max-h-[500px] overflow-y-auto">
            {isLoading ? (
              <div className="py-12 text-center text-xs text-muted-foreground">
                <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-primary" />
                Loading version registry...
              </div>
            ) : prompts.length === 0 ? (
              <div className="p-6 text-center text-xs text-muted-foreground">
                No prompt templates found.
              </div>
            ) : (
              prompts.map((p) => (
                <button
                  key={p.id}
                  onClick={() => handleSelectPrompt(p)}
                  className={`w-full text-left p-4 flex flex-col gap-1.5 hover:bg-muted/10 transition-all ${
                    viewingPrompt?.id === p.id ? "bg-primary/5 border-l-2 border-primary" : ""
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="text-[10px] font-mono uppercase bg-background px-1.5 py-0.5 rounded border border-border/40 text-muted-foreground truncate max-w-[120px]">
                      v{p.version}
                    </span>
                    {p.is_active && (
                      <Badge variant="secondary" className="text-[9px] py-0 px-1.5 flex items-center gap-1">
                        <CheckCircle className="w-2.5 h-2.5" />
                        Active
                      </Badge>
                    )}
                  </div>

                  <h3 className="font-bold text-xs text-foreground capitalize mt-1">
                    {p.stage.replace(/_/g, " ")}
                  </h3>

                  <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground mt-0.5">
                    <Hash className="w-3 h-3 text-muted-foreground/60" />
                    <span className="font-mono text-foreground truncate select-all">{p.prompt_hash.substring(0, 12)}...</span>
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        {/* Prompt detail / side-by-side compare pane */}
        <Card className="lg:col-span-2 border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
          <CardHeader className="border-b border-border/30 flex flex-row justify-between items-center gap-4">
            <div>
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Columns className="w-4 h-4 text-primary" />
                Template Inspector & Comparator
              </CardTitle>
            </div>
            {viewingPrompt && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Compare with:</span>
                <Select
                  value={comparePrompt?.id || "none"}
                  onValueChange={(val) => {
                    if (val === "none") setComparePrompt(null);
                    else {
                      const p = prompts.find((pr) => pr.id === val);
                      setComparePrompt(p || null);
                    }
                  }}
                >
                  <SelectTrigger className="w-[110px] rounded-lg text-[10px] h-7 bg-background/50">
                    <SelectValue placeholder="No comparison" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {prompts
                      .filter((pr) => pr.stage === viewingPrompt.stage && pr.id !== viewingPrompt.id)
                      .map((pr) => (
                        <SelectItem key={pr.id} value={pr.id} className="text-[10px]">
                          v{pr.version} ({pr.prompt_hash.substring(0, 6)})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </CardHeader>
          <CardContent className="p-6">
            {viewingPrompt ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Panel 1: Primary viewing prompt */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                      Active Template (v{viewingPrompt.version})
                    </h3>
                    <span className="text-[10px] font-mono text-muted-foreground">
                      Hash: {viewingPrompt.prompt_hash.substring(0, 8)}
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold text-muted-foreground">System Directive</span>
                    <pre className="p-3.5 rounded-xl bg-background/50 border border-border/40 text-[10px] font-mono text-muted-foreground overflow-y-auto max-h-[160px] whitespace-pre-wrap">
                      {viewingPrompt.system_prompt}
                    </pre>
                  </div>

                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold text-muted-foreground">User Template Variables</span>
                    <pre className="p-3.5 rounded-xl bg-background/50 border border-border/40 text-[10px] font-mono text-foreground overflow-y-auto max-h-[260px] whitespace-pre-wrap">
                      {viewingPrompt.user_prompt_template}
                    </pre>
                  </div>
                </div>

                {/* Panel 2: Comparative prompt (if selected) */}
                {comparePrompt ? (
                  <div className="space-y-4 border-t md:border-t-0 md:border-l border-border/20 md:pl-6 pt-4 md:pt-0">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-xs uppercase tracking-wider text-muted-foreground">
                        Comparative Template (v{comparePrompt.version})
                      </h3>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        Hash: {comparePrompt.prompt_hash.substring(0, 8)}
                      </span>
                    </div>

                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-muted-foreground">System Directive</span>
                      <pre className="p-3.5 rounded-xl bg-background/50 border border-border/40 text-[10px] font-mono text-muted-foreground overflow-y-auto max-h-[160px] whitespace-pre-wrap">
                        {comparePrompt.system_prompt}
                      </pre>
                    </div>

                    <div className="space-y-1.5">
                      <span className="text-[10px] font-bold text-muted-foreground">User Template Variables</span>
                      <pre className="p-3.5 rounded-xl bg-background/50 border border-border/40 text-[10px] font-mono text-foreground overflow-y-auto max-h-[260px] whitespace-pre-wrap">
                        {comparePrompt.user_prompt_template}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="hidden md:flex flex-col items-center justify-center border-l border-border/20 pl-6 text-muted-foreground text-center space-y-2">
                    <HelpCircle className="w-8 h-8 text-muted-foreground/30" />
                    <p className="text-xs">No version selected for side-by-side diff.</p>
                    <p className="text-[10px] text-muted-foreground/50 max-w-[160px]">
                      Select a previous prompt version from the top dropdown to compare.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-28 text-center text-muted-foreground">
                Select a registered prompt template on the left panel to inspect system variables and directives.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
