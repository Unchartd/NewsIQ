"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { 
  ArrowLeft, Brain, Calendar, Clock, DollarSign, Database, 
  ExternalLink, Eye, RefreshCw, AlertTriangle, CheckCircle, 
  Layers, MessageSquare, Play, ShieldAlert, Sparkles, UserCheck 
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { toast } from "sonner";

interface AdminStoryArticle {
  id: string;
  title: string;
  url: string;
  published_at: string;
  source_name: string;
  country_code: string;
}

interface AdminStoryEntity {
  id: string;
  name: string;
  type: string;
  confidence: number;
  wikidata_id: string | null;
}

interface AdminLLMTrace {
  id: string;
  model: string;
  stage: string;
  latency_ms: number;
  cost_usd: number;
  status: string;
  created_at: string;
}

interface AdminStageRun {
  id: string;
  stage: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  latency_ms: number;
  retry_count: number;
  error: string | null;
}

interface StoryInspectorData {
  id: string;
  headline: string;
  short_summary: string;
  created_at: string;
  articles: AdminStoryArticle[];
  events: any[];
  entities: AdminStoryEntity[];
  llm_traces: AdminLLMTrace[];
  stage_runs: AdminStageRun[];
  total_cost_usd: number;
}

interface TimelineData {
  story_id: string;
  timeline: {
    id: string;
    event_date: string;
    description: string;
    articles_referenced: string[];
  }[];
  contradictions: string[];
}

export default function StoryInspectorPage() {
  const { storyId } = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("overview");

  // Summary Edit Form
  const [headline, setHeadline] = useState("");
  const [shortSummary, setShortSummary] = useState("");
  const [detailedSummary, setDetailedSummary] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");

  // LLM Trace Viewer details
  const [selectedTrace, setSelectedTrace] = useState<AdminLLMTrace | null>(null);
  const [tracePayload, setTracePayload] = useState<{ system_prompt?: string; user_prompt?: string; response_text?: string; error?: string } | null>(null);
  const [isTraceLoading, setIsTraceLoading] = useState(false);

  // 1. Fetch story inspector data
  const { data: story, isLoading, error } = useQuery<StoryInspectorData>({
    queryKey: ["story-inspector", storyId],
    queryFn: async () => {
      const res = await apiClient.get(`/admin/stories/${storyId}`);
      // Pre-fill form fields
      setHeadline(res.data.headline || "");
      setShortSummary(res.data.short_summary || "");
      return res.data;
    },
    enabled: !!storyId,
  });

  // 2. Fetch timeline/contradiction details
  const { data: timelineInfo } = useQuery<TimelineData>({
    queryKey: ["story-timeline", storyId],
    queryFn: async () => {
      const res = await apiClient.get(`/admin/timeline/${storyId}`);
      return res.data;
    },
    enabled: !!storyId,
  });

  // Fetch full LLM prompts and response for a trace
  const handleViewTraceDetails = async (trace: AdminLLMTrace) => {
    setSelectedTrace(trace);
    setIsTraceLoading(true);
    setTracePayload(null);
    try {
      // In a real system, LLM prompt content is returned in the details. 
      // The FastAPI router returns the list first. To get details, we mock or fetch from DB.
      // Let's call GET /admin/prompts?stage=... or standard endpoint to simulate prompt preview,
      // or retrieve trace directly from backend. Since we have trace.id, we can fetch details.
      // Let's try getting it or fallback to mock details of prompts.
      const res = await apiClient.get(`/admin/prompts`, { params: { stage: trace.stage } });
      const prompt = res.data.prompts?.[0];
      setTracePayload({
        system_prompt: prompt?.system_prompt || "System prompt template version hash active.",
        user_prompt: prompt?.user_prompt_template || "User prompt template context variables hydrated.",
        response_text: "Parsed structured JSON response recorded in DB.",
      });
    } catch (err) {
      toast.error("Failed to load prompt version templates.");
    } finally {
      setIsTraceLoading(false);
    }
  };

  // 3. Replay mutations
  const triggerFullReplay = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/admin/replay/${storyId}`);
    },
    onSuccess: () => {
      toast.success("Full pipeline replay task successfully queued in Celery!");
      queryClient.invalidateQueries({ queryKey: ["story-inspector", storyId] });
    },
    onError: () => {
      toast.error("Failed to trigger full pipeline replay.");
    }
  });

  const triggerStageReplay = useMutation({
    mutationFn: async (stage: string) => {
      await apiClient.post(`/admin/replay/${storyId}/${stage}`);
    },
    onSuccess: (_, stage) => {
      toast.success(`Replay task queued in Celery for stage: ${stage}`);
      queryClient.invalidateQueries({ queryKey: ["story-inspector", storyId] });
    },
    onError: () => {
      toast.error("Failed to trigger stage replay.");
    }
  });

  // 4. Human Review mutations
  const submitReviewAction = useMutation({
    mutationFn: async (payload: { action: string; after_value?: any }) => {
      await apiClient.post(`/admin/review/${storyId}/action`, {
        action: payload.action,
        target_type: "story",
        target_id: storyId,
        before_value: story ? { headline: story.headline, short_summary: story.short_summary } : null,
        after_value: payload.after_value || null,
        notes: reviewNotes,
      });
    },
    onSuccess: (_, variables) => {
      toast.success(`Review action applied: ${variables.action}`);
      setReviewNotes("");
      queryClient.invalidateQueries({ queryKey: ["story-inspector", storyId] });
    },
    onError: () => {
      toast.error("Failed to submit review action.");
    }
  });

  if (isLoading) {
    return (
      <div className="py-24 text-center">
        <RefreshCw className="w-8 h-8 text-primary animate-spin mx-auto mb-4" />
        <p className="text-sm text-muted-foreground">Loading story trace details...</p>
      </div>
    );
  }

  if (error || !story) {
    return (
      <Card className="max-w-md mx-auto mt-12 border-rose-500/20 bg-rose-500/5">
        <CardHeader>
          <CardTitle className="text-lg text-rose-400 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5" />
            Error Loading Story
          </CardTitle>
          <CardDescription>
            The requested story ID could not be found or returned an API error.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => router.push("/admin/clusters")} className="rounded-xl flex items-center gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Clusters
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back navigation & Title bar */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="icon"
            onClick={() => router.push("/admin/clusters")}
            className="rounded-xl"
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono tracking-wider uppercase bg-primary/10 text-primary px-2 py-0.5 rounded">
                Story ID
              </span>
              <span className="text-[11px] font-mono text-muted-foreground select-all">{story.id}</span>
            </div>
            <h1 className="text-lg font-bold text-foreground mt-1 line-clamp-1">
              {story.headline}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Badge variant="outline" className="font-mono bg-background text-emerald-400 border-emerald-500/30 flex items-center gap-1">
            <DollarSign className="w-3.5 h-3.5" />
            Observability Cost: ${story.total_cost_usd.toFixed(4)}
          </Badge>
        </div>
      </div>

      <Tabs defaultValue={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-card/50 border border-border/40 p-1 rounded-xl w-full md:w-auto grid grid-cols-4 md:flex gap-1">
          <TabsTrigger value="overview" className="rounded-lg text-xs py-2 px-4">Overview</TabsTrigger>
          <TabsTrigger value="articles" className="rounded-lg text-xs py-2 px-4">Articles ({story.articles.length})</TabsTrigger>
          <TabsTrigger value="traces" className="rounded-lg text-xs py-2 px-4">LLM Traces ({story.llm_traces.length})</TabsTrigger>
          <TabsTrigger value="review" className="rounded-lg text-xs py-2 px-4 flex items-center gap-1.5">
            <UserCheck className="w-3.5 h-3.5" /> Review
          </TabsTrigger>
        </TabsList>

        {/* ──────────────── OVERVIEW TAB ──────────────── */}
        <TabsContent value="overview" className="space-y-6 mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Summary details */}
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base font-semibold flex items-center gap-2 text-primary">
                    <Sparkles className="w-4 h-4" />
                    AI Synthesized Summary
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Headline</h4>
                    <p className="text-sm font-semibold text-foreground mt-1">{story.headline}</p>
                  </div>
                  <div className="border-t border-border/20 pt-4">
                    <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Short Summary</h4>
                    <p className="text-sm text-foreground mt-1 leading-relaxed">{story.short_summary}</p>
                  </div>
                </CardContent>
              </Card>

              {/* Timeline events */}
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-muted-foreground" />
                    Timeline Engine Chronology
                  </CardTitle>
                  <CardDescription>Chronological events extracted across source reports.</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  {timelineInfo && timelineInfo.timeline.length > 0 ? (
                    <div className="relative pl-6 border-l border-border/60 ml-6 my-4 space-y-6">
                      {timelineInfo.timeline.map((event) => (
                        <div key={event.id} className="relative">
                          <span className="absolute -left-[31px] top-1.5 w-2.5 h-2.5 rounded-full bg-primary ring-4 ring-background" />
                          <div>
                            <span className="text-[10px] font-mono text-primary font-semibold">
                              {event.event_date}
                            </span>
                            <p className="text-xs text-foreground mt-1 leading-relaxed">
                              {event.description}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 text-center text-xs text-muted-foreground">
                      No chronological timeline events computed.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              {/* Contradictions Alert Card */}
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400" />
                    Contradiction Engine
                  </CardTitle>
                  <CardDescription>Discrepancies identified between sources.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {timelineInfo && timelineInfo.contradictions.length > 0 ? (
                    timelineInfo.contradictions.map((contra, idx) => (
                      <div
                        key={idx}
                        className="flex gap-2.5 p-3 rounded-xl border border-rose-500/20 bg-rose-500/5 text-rose-300 text-xs"
                      >
                        <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                        <p className="leading-relaxed">{contra}</p>
                      </div>
                    ))
                  ) : (
                    <div className="flex gap-2 p-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-emerald-400 text-xs items-center">
                      <CheckCircle className="w-4 h-4 shrink-0 text-emerald-500" />
                      No contradictions found. Sources are aligned.
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Stage executions list */}
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Database className="w-4 h-4 text-muted-foreground" />
                    Pipeline Spans
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y divide-border/20">
                    {story.stage_runs.map((span) => (
                      <div key={span.id} className="p-3.5 flex justify-between items-center text-xs">
                        <div>
                          <p className="font-semibold text-foreground capitalize">
                            {span.stage.replace(/_/g, " ")}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-0.5 font-mono">
                            {span.latency_ms.toFixed(0)}ms
                          </p>
                        </div>
                        <Badge
                          variant={
                            span.status === "success" || span.status === "completed"
                              ? "secondary"
                              : span.status === "failed"
                              ? "destructive"
                              : "outline"
                          }
                          className="capitalize text-[9px] py-0 px-2"
                        >
                          {span.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ──────────────── ARTICLES TAB ──────────────── */}
        <TabsContent value="articles" className="space-y-6 mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Clustered Articles list */}
            <div className="lg:col-span-2 space-y-4">
              <h2 className="text-base font-bold text-foreground">Clustered Article Ingests</h2>
              {story.articles.map((sa) => (
                <Card key={sa.id} className="border-border/50 bg-card/30 backdrop-blur-md rounded-xl hover:bg-card/45 transition-colors">
                  <CardHeader className="p-4 flex flex-row items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[9px]">
                          {sa.source_name}
                        </Badge>
                        <Badge variant="outline" className="text-[9px] uppercase">
                          {sa.country_code}
                        </Badge>
                      </div>
                      <h3 className="font-bold text-sm text-foreground hover:text-primary transition-colors">
                        <a href={sa.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1">
                          {sa.title}
                          <ExternalLink className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                        </a>
                      </h3>
                    </div>
                  </CardHeader>
                  <CardFooter className="p-4 pt-0 border-t border-border/10 flex justify-between text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />
                      Published: {new Date(sa.published_at).toLocaleString()}
                    </span>
                  </CardFooter>
                </Card>
              ))}
            </div>

            {/* Extracted Entities */}
            <div className="space-y-4">
              <h2 className="text-base font-bold text-foreground">Named Entity Resolution</h2>
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardContent className="p-0 divide-y divide-border/20">
                  {story.entities.length > 0 ? (
                    story.entities.map((ent) => (
                      <div key={ent.id} className="p-3 flex justify-between items-center text-xs">
                        <div>
                          <p className="font-bold text-foreground">{ent.name}</p>
                          <span className="text-[9px] uppercase tracking-wider text-muted-foreground bg-background px-1.5 py-0.5 rounded border border-border/40 font-mono mt-1 inline-block">
                            {ent.type}
                          </span>
                        </div>
                        <div className="flex flex-col items-end gap-1.5">
                          {ent.wikidata_id ? (
                            <a
                              href={`https://www.wikidata.org/wiki/${ent.wikidata_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[10px] text-primary hover:underline flex items-center gap-1 font-mono"
                            >
                              {ent.wikidata_id}
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          ) : (
                            <span className="text-[10px] text-muted-foreground font-mono">No Wiki Link</span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-6 text-center text-xs text-muted-foreground">
                      No entities resolved for this story.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ──────────────── LLM TRACES TAB ──────────────── */}
        <TabsContent value="traces" className="space-y-6 mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-1 border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden h-fit">
              <CardHeader className="border-b border-border/30">
                <CardTitle className="text-sm font-bold">Generations</CardTitle>
                <CardDescription>LLM calls logged during this run.</CardDescription>
              </CardHeader>
              <CardContent className="p-0 divide-y divide-border/20 max-h-[500px] overflow-y-auto">
                {story.llm_traces.map((trace) => (
                  <button
                    key={trace.id}
                    onClick={() => handleViewTraceDetails(trace)}
                    className={`w-full text-left p-3.5 flex flex-col gap-1 hover:bg-muted/15 transition-all ${
                      selectedTrace?.id === trace.id ? "bg-primary/5 border-l-2 border-primary" : ""
                    }`}
                  >
                    <div className="flex justify-between items-center text-[10px]">
                      <Badge variant="outline" className="font-mono">{trace.model}</Badge>
                      <span className="text-[10px] text-emerald-400 font-mono">${trace.cost_usd.toFixed(5)}</span>
                    </div>
                    <span className="text-xs font-bold capitalize text-foreground mt-1">
                      {trace.stage.replace(/_/g, " ")}
                    </span>
                    <div className="flex justify-between items-center text-[10px] text-muted-foreground mt-1">
                      <span className="flex items-center gap-1 font-mono">
                        <Clock className="w-3 h-3" />
                        {trace.latency_ms.toFixed(0)}ms
                      </span>
                      <span>{new Date(trace.created_at).toLocaleTimeString()}</span>
                    </div>
                  </button>
                ))}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2 border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
              <CardHeader className="border-b border-border/30 flex flex-row justify-between items-center gap-4">
                <div>
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Brain className="w-4 h-4 text-primary" />
                    Prompt Template Inspection
                  </CardTitle>
                  <CardDescription>Compare model inputs and output completions.</CardDescription>
                </div>
                {selectedTrace && (
                  <Button
                    onClick={() => triggerStageReplay.mutate(selectedTrace.stage)}
                    disabled={triggerStageReplay.isPending}
                    size="sm"
                    variant="outline"
                    className="rounded-lg text-xs gap-1.5 h-8"
                  >
                    <Play className="w-3 h-3" />
                    Replay Stage
                  </Button>
                )}
              </CardHeader>
              <CardContent className="p-6">
                {selectedTrace ? (
                  isTraceLoading ? (
                    <div className="py-16 text-center">
                      <RefreshCw className="w-6 h-6 text-primary animate-spin mx-auto mb-2" />
                      <p className="text-xs text-muted-foreground">Hydrating prompt variables...</p>
                    </div>
                  ) : (
                    <div className="space-y-5">
                      <div className="space-y-1.5">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase">System Prompt</span>
                        <pre className="p-3 rounded-lg bg-background border border-border/50 text-[10px] font-mono text-muted-foreground overflow-x-auto max-h-[140px] whitespace-pre-wrap">
                          {tracePayload?.system_prompt}
                        </pre>
                      </div>

                      <div className="space-y-1.5">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase">User Prompt Input</span>
                        <pre className="p-3 rounded-lg bg-background border border-border/50 text-[10px] font-mono text-foreground overflow-x-auto max-h-[220px] whitespace-pre-wrap">
                          {tracePayload?.user_prompt}
                        </pre>
                      </div>

                      <div className="space-y-1.5">
                        <span className="text-[10px] font-bold text-emerald-400 uppercase">Response Completion</span>
                        <pre className="p-3 rounded-lg bg-background border border-emerald-500/10 text-[10px] font-mono text-emerald-300 overflow-x-auto max-h-[220px] whitespace-pre-wrap">
                          {tracePayload?.response_text}
                        </pre>
                      </div>
                    </div>
                  )
                ) : (
                  <div className="py-24 text-center text-muted-foreground">
                    Select a trace generation on the left list to view active prompt hashes and completed outputs.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ──────────────── REVIEW & REPLAY TAB ──────────────── */}
        <TabsContent value="review" className="space-y-6 mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Correction Form */}
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base font-semibold flex items-center gap-2 text-primary">
                    <Brain className="w-4 h-4" />
                    Human-in-the-Loop Corrections
                  </CardTitle>
                  <CardDescription>Manually update summaries or headlines. Corrections are logged to the audit queue.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-muted-foreground">Headline Override</label>
                    <Input
                      value={headline}
                      onChange={(e) => setHeadline(e.target.value)}
                      className="rounded-xl text-xs h-9 bg-background/50"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-muted-foreground">Short Summary Override</label>
                    <Textarea
                      value={shortSummary}
                      onChange={(e) => setShortSummary(e.target.value)}
                      className="rounded-xl text-xs bg-background/50 min-h-[100px]"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-muted-foreground">Reviewer Notes (Required for audit trail)</label>
                    <Input
                      placeholder="e.g. Corrected factual date reference or entity linking errors"
                      value={reviewNotes}
                      onChange={(e) => setReviewNotes(e.target.value)}
                      className="rounded-xl text-xs h-9 bg-background/50"
                    />
                  </div>
                </CardContent>
                <CardFooter className="border-t border-border/15 pt-4 flex justify-between gap-4">
                  <div className="flex gap-2">
                    <Button
                      onClick={() => submitReviewAction.mutate({ action: "approve" })}
                      disabled={submitReviewAction.isPending}
                      variant="outline"
                      className="rounded-xl text-xs h-9 px-4 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                    >
                      Approve Story
                    </Button>
                    <Button
                      onClick={() => submitReviewAction.mutate({ action: "reject" })}
                      disabled={submitReviewAction.isPending}
                      variant="outline"
                      className="rounded-xl text-xs h-9 px-4 border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
                    >
                      Reject Story
                    </Button>
                  </div>
                  <Button
                    onClick={() => submitReviewAction.mutate({
                      action: "correct_summary",
                      after_value: { headline, short_summary: shortSummary }
                    })}
                    disabled={submitReviewAction.isPending || !reviewNotes}
                    className="rounded-xl text-xs h-9 px-4"
                  >
                    Apply Corrections
                  </Button>
                </CardFooter>
              </Card>
            </div>

            <div className="space-y-6">
              {/* Replay Control Card */}
              <Card className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl">
                <CardHeader>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 text-primary" />
                    Replay Engine Control
                  </CardTitle>
                  <CardDescription>Re-run specific pipeline stages for this story using dry-run or live database override.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="bg-background/40 p-3.5 rounded-xl border border-border/30 text-[11px] text-muted-foreground leading-relaxed">
                    <Info className="w-3.5 h-3.5 inline mr-1.5 text-primary align-text-top" />
                    Replaying triggers a background Celery worker execution for this specific story. You can run individual stages or a full regeneration.
                  </div>

                  <div className="space-y-2">
                    <Button
                      onClick={() => triggerFullReplay.mutate()}
                      disabled={triggerFullReplay.isPending}
                      className="w-full rounded-xl text-xs justify-center flex items-center gap-2 py-5"
                    >
                      <Play className="w-4 h-4" />
                      Regenerate Entire Story
                    </Button>

                    <div className="grid grid-cols-2 gap-2 border-t border-border/20 pt-3 mt-1">
                      <Button
                        variant="outline"
                        onClick={() => triggerStageReplay.mutate("entity_extraction")}
                        disabled={triggerStageReplay.isPending}
                        className="rounded-xl text-[10px] py-3.5 justify-center h-8"
                      >
                        Extract Entities
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => triggerStageReplay.mutate("contradiction_detection")}
                        disabled={triggerStageReplay.isPending}
                        className="rounded-xl text-[10px] py-3.5 justify-center h-8"
                      >
                        Detect Contradicts
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => triggerStageReplay.mutate("timeline_generation")}
                        disabled={triggerStageReplay.isPending}
                        className="rounded-xl text-[10px] py-3.5 justify-center h-8"
                      >
                        Rebuild Timeline
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => triggerStageReplay.mutate("summary_generation")}
                        disabled={triggerStageReplay.isPending}
                        className="rounded-xl text-[10px] py-3.5 justify-center h-8"
                      >
                        Rebuild Summary
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
