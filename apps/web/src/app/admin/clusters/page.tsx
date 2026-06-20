"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { 
  Layers, GitMerge, Scissors, ExternalLink, RefreshCw, AlertTriangle, 
  HelpCircle, ChevronDown, ChevronUp, Eye, Calendar, Clock 
} from "lucide-react";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { toast } from "sonner";
import Link from "next/link";

interface ClusterArticle {
  id: string;
  title: string;
  source_name: string;
  published_at: string;
}

interface ClusterDebuggerItem {
  story_id: string;
  headline: string;
  article_count: number;
  avg_similarity: number;
  articles: ClusterArticle[];
}

interface ClusterDebuggerResponse {
  clusters: ClusterDebuggerItem[];
}

export default function ClustersPage() {
  const queryClient = useQueryClient();
  const [expandedStoryId, setExpandedStoryId] = useState<string | null>(null);
  
  // Merge dialog states
  const [mergingStory, setMergingStory] = useState<ClusterDebuggerItem | null>(null);
  const [targetStoryId, setTargetStoryId] = useState<string>("");
  const [mergeNotes, setMergeNotes] = useState("");

  // Split dialog states
  const [splittingStory, setSplittingStory] = useState<ClusterDebuggerItem | null>(null);
  const [selectedArticles, setSelectedArticles] = useState<string[]>([]);
  const [splitNotes, setSplitNotes] = useState("");

  // 1. Fetch cluster debugger data
  const { data, isLoading, refetch } = useQuery<ClusterDebuggerResponse>({
    queryKey: ["admin-clusters"],
    queryFn: async () => {
      const res = await apiClient.get("/admin/clusters");
      return res.data;
    },
  });

  const clusters = data?.clusters || [];

  // 2. Merge mutation
  const mergeMutation = useMutation({
    mutationFn: async (payload: { sourceId: string; targetId: string; notes: string }) => {
      await apiClient.post(`/admin/review/${payload.sourceId}/action`, {
        action: "merge",
        target_type: "story",
        target_id: payload.targetId,
        notes: payload.notes,
      });
    },
    onSuccess: () => {
      toast.success("Stories merged successfully! Tasks queued to regenerate summary.");
      setMergingStory(null);
      setTargetStoryId("");
      setMergeNotes("");
      queryClient.invalidateQueries({ queryKey: ["admin-clusters"] });
    },
    onError: () => {
      toast.error("Failed to merge stories.");
    }
  });

  // 3. Split mutation
  const splitMutation = useMutation({
    mutationFn: async (payload: { storyId: string; articleIds: string[]; notes: string }) => {
      await apiClient.post(`/admin/review/${payload.storyId}/action`, {
        action: "split",
        target_type: "articles",
        before_value: { article_ids: payload.articleIds },
        notes: payload.notes,
      });
    },
    onSuccess: () => {
      toast.success("Articles split successfully! Initiating new story extraction.");
      setSplittingStory(null);
      setSelectedArticles([]);
      setSplitNotes("");
      queryClient.invalidateQueries({ queryKey: ["admin-clusters"] });
    },
    onError: () => {
      toast.error("Failed to split articles.");
    }
  });

  const handleToggleExpand = (storyId: string) => {
    setExpandedStoryId(expandedStoryId === storyId ? null : storyId);
  };

  const handleOpenMerge = (cluster: ClusterDebuggerItem) => {
    setMergingStory(cluster);
    setTargetStoryId("");
    setMergeNotes("");
  };

  const handleOpenSplit = (cluster: ClusterDebuggerItem) => {
    setSplittingStory(cluster);
    setSelectedArticles([]);
    setSplitNotes("");
  };

  const handleToggleArticleSelection = (articleId: string) => {
    setSelectedArticles((prev) => 
      prev.includes(articleId) 
        ? prev.filter((id) => id !== articleId) 
        : [...prev, articleId]
    );
  };

  const executeMerge = () => {
    if (!mergingStory || !targetStoryId) return;
    mergeMutation.mutate({
      sourceId: mergingStory.story_id,
      targetId: targetStoryId,
      notes: mergeNotes.trim(),
    });
  };

  const executeSplit = () => {
    if (!splittingStory || selectedArticles.length === 0) return;
    splitMutation.mutate({
      storyId: splittingStory.story_id,
      articleIds: selectedArticles,
      notes: splitNotes.trim(),
    });
  };

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex justify-between items-center bg-card/30 border border-border/50 p-6 rounded-2xl backdrop-blur-md">
        <div>
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
            <Layers className="w-5 h-5 text-primary" />
            Story Clustering Debugger
          </h2>
          <p className="text-xs text-muted-foreground mt-1">
            Audit HDBSCAN grouping parameters, examine similarity scores, and adjust story clusters manually.
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={() => refetch()} className="rounded-xl">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Cluster List */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="py-24 text-center text-xs text-muted-foreground">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-primary" />
            Analyzing active story clusters...
          </div>
        ) : clusters.length === 0 ? (
          <div className="py-16 text-center text-xs text-muted-foreground bg-card/10 border border-border/40 rounded-2xl">
            No clusters detected in database.
          </div>
        ) : (
          clusters.map((c) => {
            const isExpanded = expandedStoryId === c.story_id;
            return (
              <Card key={c.story_id} className="border-border/50 bg-card/30 backdrop-blur-md rounded-2xl overflow-hidden">
                <CardHeader className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border/10">
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="font-mono text-[9px] py-0">
                        {c.article_count} Articles
                      </Badge>
                      <Badge variant="outline" className="font-mono text-[9px] text-primary py-0">
                        Avg Sim: {c.avg_similarity.toFixed(2)}
                      </Badge>
                      <Badge variant="outline" className="font-mono text-[8px] py-0 select-all text-muted-foreground">
                        ID: {c.story_id}
                      </Badge>
                    </div>
                    <h3 className="font-bold text-sm text-foreground hover:text-primary transition-colors">
                      <Link href={`/admin/stories/${c.story_id}`}>{c.headline}</Link>
                    </h3>
                  </div>

                  <div className="flex items-center gap-1.5 self-end md:self-auto">
                    <Link href={`/admin/stories/${c.story_id}`}>
                      <Button variant="outline" size="sm" className="rounded-xl text-[10px] h-8 px-2.5 flex items-center gap-1.5">
                        <Eye className="w-3.5 h-3.5" />
                        Observe
                      </Button>
                    </Link>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => handleOpenMerge(c)}
                      className="rounded-xl text-[10px] h-8 px-2.5 flex items-center gap-1.5 border-primary/20 text-primary hover:bg-primary/10"
                    >
                      <GitMerge className="w-3.5 h-3.5" />
                      Merge
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={() => handleOpenSplit(c)}
                      className="rounded-xl text-[10px] h-8 px-2.5 flex items-center gap-1.5 border-rose-500/20 text-rose-400 hover:bg-rose-500/10"
                    >
                      <Scissors className="w-3.5 h-3.5" />
                      Split
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleToggleExpand(c.story_id)}
                      className="rounded-xl h-8 w-8"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </Button>
                  </div>
                </CardHeader>

                {isExpanded && (
                  <CardContent className="p-0 bg-background/20 divide-y divide-border/20">
                    {c.articles.map((art) => (
                      <div key={art.id} className="p-4 flex justify-between items-start gap-4 text-xs">
                        <div className="space-y-1">
                          <p className="font-semibold text-foreground">{art.title}</p>
                          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                            <span className="font-semibold">{art.source_name}</span>
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {new Date(art.published_at).toLocaleString()}
                            </span>
                          </div>
                        </div>
                        <Badge variant="outline" className="font-mono text-[8px] text-muted-foreground select-all mt-0.5">
                          ID: {art.id}
                        </Badge>
                      </div>
                    ))}
                  </CardContent>
                )}
              </Card>
            );
          })
        )}
      </div>

      {/* MERGE DIALOG */}
      <Dialog open={!!mergingStory} onOpenChange={(open) => !open && setMergingStory(null)}>
        <DialogContent className="rounded-2xl border-border bg-card">
          <DialogHeader>
            <DialogTitle className="text-base font-bold">Merge Story Clusters</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Select a target story to merge this cluster into. All articles will be grouped under the destination cluster.
            </DialogDescription>
          </DialogHeader>

          {mergingStory && (
            <div className="space-y-4 py-4">
              <div>
                <span className="text-[10px] font-bold text-muted-foreground uppercase">Source Story</span>
                <p className="text-xs font-semibold text-foreground mt-0.5">{mergingStory.headline}</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground">Target Story (Merge Destination)</label>
                <Select value={targetStoryId} onValueChange={setTargetStoryId}>
                  <SelectTrigger className="rounded-xl text-xs h-9 bg-background/50">
                    <SelectValue placeholder="Select target story..." />
                  </SelectTrigger>
                  <SelectContent>
                    {clusters
                      .filter((cl) => cl.story_id !== mergingStory.story_id)
                      .map((cl) => (
                        <SelectItem key={cl.story_id} value={cl.story_id} className="text-xs">
                          {cl.headline.substring(0, 60)}...
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground">Reason/Notes (Required for audit log)</label>
                <Input
                  placeholder="e.g. Ingestion overlap between reports"
                  value={mergeNotes}
                  onChange={(e) => setMergeNotes(e.target.value)}
                  className="rounded-xl text-xs h-9 bg-background/50"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setMergingStory(null)} className="rounded-xl text-xs h-9">
              Cancel
            </Button>
            <Button
              onClick={executeMerge}
              disabled={mergeMutation.isPending || !targetStoryId || !mergeNotes.trim()}
              className="rounded-xl text-xs h-9"
            >
              Merge Clusters
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* SPLIT DIALOG */}
      <Dialog open={!!splittingStory} onOpenChange={(open) => !open && setSplittingStory(null)}>
        <DialogContent className="rounded-2xl border-border bg-card max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-base font-bold">Split Articles From Cluster</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              Select one or more articles to split into a new independent story cluster.
            </DialogDescription>
          </DialogHeader>

          {splittingStory && (
            <div className="space-y-4 py-4">
              <div>
                <span className="text-[10px] font-bold text-muted-foreground uppercase">Current Story</span>
                <p className="text-xs font-semibold text-foreground mt-0.5">{splittingStory.headline}</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground">Select Articles to Split Out:</label>
                <div className="max-h-[200px] overflow-y-auto space-y-2 border border-border/40 p-2.5 rounded-xl bg-background/30">
                  {splittingStory.articles.map((art) => {
                    const isSelected = selectedArticles.includes(art.id);
                    return (
                      <button
                        key={art.id}
                        onClick={() => handleToggleArticleSelection(art.id)}
                        className={`w-full text-left p-2 rounded-lg border transition-colors flex items-center justify-between text-xs ${
                          isSelected 
                            ? "bg-rose-500/10 border-rose-500 text-rose-300" 
                            : "border-border/30 hover:bg-muted/10"
                        }`}
                      >
                        <div className="flex-1 pr-4">
                          <p className="font-semibold truncate">{art.title}</p>
                          <span className="text-[9px] text-muted-foreground font-mono">{art.source_name}</span>
                        </div>
                        <Badge variant={isSelected ? "destructive" : "outline"} className="text-[9px] py-0 shrink-0">
                          {isSelected ? "Selected" : "Keep"}
                        </Badge>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-muted-foreground">Reason/Notes (Required for audit log)</label>
                <Input
                  placeholder="e.g. Irrelevant article matched by text content"
                  value={splitNotes}
                  onChange={(e) => setSplitNotes(e.target.value)}
                  className="rounded-xl text-xs h-9 bg-background/50"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setSplittingStory(null)} className="rounded-xl text-xs h-9">
              Cancel
            </Button>
            <Button
              onClick={executeSplit}
              disabled={splitMutation.isPending || selectedArticles.length === 0 || !splitNotes.trim()}
              className="rounded-xl text-xs h-9"
            >
              Split Articles
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
