"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  Clock,
  Bookmark,
  Share2,
  Calendar,
  Layers,
  ChevronLeft,
  BookOpen,
  CheckCircle2,
  HelpCircle,
  FileWarning,
  ExternalLink,
  MessageSquare,
  Award,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { StoryDetail } from "@/types";

interface PageProps {
  params: Promise<{ storyId: string }>;
}

export default function StoryDetailPage({ params }: PageProps) {
  const { storyId } = use(params);
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const [summaryType, setSummaryType] = useState<"one_line" | "short" | "detailed">("short");

  // Fetch story detail
  const { data: story, isLoading, error } = useQuery<StoryDetail>({
    queryKey: ["story-detail", storyId],
    queryFn: async () => {
      const response = await apiClient.get(`/stories/${storyId}`);
      return response.data;
    },
  });

  // Check if story is bookmarked in user bookmarks
  const { data: bookmarkedStories } = useQuery<any[]>({
    queryKey: ["bookmarked-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories/bookmarks");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const isBookmarked = bookmarkedStories?.some((s: any) => s.id === storyId) || false;

  // Toggle bookmark mutation
  const bookmarkMutation = useMutation({
    mutationFn: async () => {
      if (isBookmarked) {
        await apiClient.delete(`/stories/${storyId}/bookmark`);
      } else {
        await apiClient.post(`/stories/${storyId}/bookmark`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bookmarked-stories"] });
      toast.success(
        isBookmarked ? "Removed bookmark." : "Story bookmarked for later reading."
      );
    },
    onError: () => {
      toast.error("Failed to update bookmark.");
    },
  });

  const handleShare = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      toast.success("Link copied to clipboard!");
    }
  };

  if (isLoading) {
    return (
      <AppShell showRightPanel={false}>
        <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-10 w-3/4 rounded-xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Skeleton className="h-80 col-span-2 rounded-2xl" />
            <Skeleton className="h-80 col-span-1 rounded-2xl" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !story) {
    return (
      <AppShell showRightPanel={false}>
        <div className="max-w-xl mx-auto px-4 py-16 text-center">
          <h2 className="text-xl font-bold text-foreground mb-2">Story Not Found</h2>
          <p className="text-muted-foreground mb-6">
            The story you are looking for does not exist or may have been deleted.
          </p>
          <Button render={<Link href="/home" />} className="rounded-xl">
            Go Back Home
          </Button>
        </div>
      </AppShell>
    );
  }

  // Determine active summary text
  const activeSummary =
    summaryType === "one_line"
      ? story.one_line_summary
      : summaryType === "detailed"
        ? story.detailed_summary
        : story.short_summary;

  return (
    <AppShell showRightPanel={false}>
      <div className="max-w-4xl mx-auto px-4 py-6 space-y-8 pb-32">
        {/* Back Link */}
        <Link
          href="/home"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors group"
        >
          <ChevronLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" />
          Back to feed
        </Link>

        {/* Story Title & Meta Header */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            {story.category && (
              <Badge variant="secondary" className="rounded-full text-xs font-semibold px-2.5 py-0.5">
                {story.category.name}
              </Badge>
            )}
            {story.location_country && (
              <Badge variant="outline" className="rounded-full text-xs font-normal">
                {story.location_country}
              </Badge>
            )}
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl leading-tight">
            {story.headline}
          </h1>

          <div className="flex items-center justify-between flex-wrap gap-4 pt-2 border-b border-border/40 pb-4">
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                Updated {new Date(story.updated_at).toLocaleDateString()}
              </span>
              <span className="flex items-center gap-1">
                <Layers className="w-3.5 h-3.5" />
                {story.articles?.length || 0} Sources Reporting
              </span>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (!isAuthenticated) {
                    toast.error("Please sign in to bookmark stories.");
                    return;
                  }
                  bookmarkMutation.mutate();
                }}
                className={`rounded-xl h-9 flex items-center gap-1.5 px-3 border-border/50 ${
                  isBookmarked ? "bg-primary/5 text-primary border-primary/20" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Bookmark className={`w-4 h-4 ${isBookmarked ? "fill-current" : ""}`} />
                {isBookmarked ? "Saved" : "Save"}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={handleShare}
                className="rounded-xl h-9 text-muted-foreground hover:text-foreground flex items-center gap-1.5 px-3 border-border/50"
              >
                <Share2 className="w-4 h-4" />
                Share
              </Button>
            </div>
          </div>
        </div>

        {/* AI Summarization Center Panel */}
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
              <BookOpen className="w-4 h-4 text-primary" />
              AI neutral synthesis
            </h3>

            {/* Summary Tabs */}
            <Tabs
              value={summaryType}
              onValueChange={(val: any) => setSummaryType(val)}
              className="w-full sm:w-auto"
            >
              <TabsList className="grid grid-cols-3 h-9 bg-muted/50 p-1 rounded-xl w-full sm:w-72">
                <TabsTrigger value="one_line" className="text-xs rounded-lg font-medium">1-Line</TabsTrigger>
                <TabsTrigger value="short" className="text-xs rounded-lg font-medium">Short</TabsTrigger>
                <TabsTrigger value="detailed" className="text-xs rounded-lg font-medium">Detailed</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <Card className="border-border/50 bg-secondary/15 rounded-2xl overflow-hidden shadow-xs">
            <CardContent className="p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={summaryType}
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -5 }}
                  transition={{ duration: 0.15 }}
                  className="text-foreground leading-relaxed text-base whitespace-pre-wrap"
                >
                  {activeSummary}
                </motion.div>
              </AnimatePresence>
            </CardContent>
          </Card>
        </div>

        {/* Key Facts list */}
        {story.entities && story.entities.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              Verified Key Facts
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {story.entities.slice(0, 6).map((fact, index) => (
                <Card key={fact.id || index} className="border-border/45 rounded-xl bg-background shadow-none">
                  <CardContent className="p-3.5 flex items-start gap-2.5">
                    <span className="w-5 h-5 rounded-full bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                      {index + 1}
                    </span>
                    <p className="text-sm font-medium leading-normal text-foreground">
                      {fact.entity_value} <span className="text-[10px] text-muted-foreground uppercase ml-1.5 font-normal px-1.5 py-0.5 rounded-sm bg-muted/65">{fact.entity_type}</span>
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Three-Column sections (Timeline | Publisher differences) */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
          {/* Left 3 columns: Timeline & Source coverage */}
          <div className="lg:col-span-3 space-y-8">
            {/* Timeline */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
                <Calendar className="w-4 h-4 text-primary" />
                Story Timeline
              </h3>

              <div className="relative border-l-2 border-border/70 pl-5 ml-2.5 space-y-6 py-2">
                {story.timeline?.map((ev, index) => (
                  <div key={ev.id || index} className="relative">
                    <div className="absolute -left-[27px] top-1 w-3 h-3 rounded-full border-2 border-background bg-primary" />
                    <p className="text-sm text-foreground font-medium leading-relaxed">
                      {ev.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Source Coverage */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
                <Award className="w-4 h-4 text-primary" />
                Publisher Focus
              </h3>
              <div className="border border-border/50 rounded-2xl overflow-hidden bg-background">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="border-b border-border/50 bg-secondary/20">
                      <th className="p-3 font-semibold text-muted-foreground">Source</th>
                      <th className="p-3 font-semibold text-muted-foreground">Focus/Coverage Angle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {story.source_coverage?.map((cov) => (
                      <tr key={cov.id} className="border-b border-border/40 hover:bg-muted/10 transition-colors">
                        <td className="p-3 font-semibold text-foreground">{cov.source?.name}</td>
                        <td className="p-3 text-muted-foreground leading-relaxed">{cov.focus_area}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Right 2 columns: Differences / contradictions panel */}
          <div className="lg:col-span-2 space-y-6">
            <div className="sticky top-20 space-y-6">
              <div className="space-y-3">
                <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
                  <FileWarning className="w-4 h-4 text-amber-500" />
                  Source Differences
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Contradictions, unique viewpoints, and omitted facts identified across publishers.
                </p>
              </div>

              {story.differences?.map((diff) => (
                <Card key={diff.id} className="border-border/50 rounded-2xl overflow-hidden">
                  <CardHeader className="p-4 bg-secondary/15 border-b border-border/40">
                    <CardTitle className="text-xs font-bold text-foreground">
                      {diff.source?.name} Analysis
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3 text-xs leading-relaxed">
                    {diff.unique_information && (
                      <div>
                        <p className="font-semibold text-foreground mb-0.5">Unique facts mentioned:</p>
                        <p className="text-muted-foreground">{diff.unique_information}</p>
                      </div>
                    )}
                    {diff.missing_information && (
                      <div>
                        <p className="font-semibold text-foreground mb-0.5">Omissions / missing context:</p>
                        <p className="text-muted-foreground">{diff.missing_information}</p>
                      </div>
                    )}
                    {diff.contradictions && (
                      <div className="bg-destructive/5 text-destructive p-2.5 rounded-xl border border-destructive/15">
                        <p className="font-bold mb-0.5">Contradiction warning:</p>
                        <p>{diff.contradictions}</p>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>

        {/* References list of real original articles */}
        <div className="space-y-4 border-t border-border/40 pt-8">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
            <MessageSquare className="w-4 h-4 text-primary" />
            Original reporting references
          </h3>
          <div className="space-y-3">
            {story.articles?.map((art) => (
              <Card
                key={art.id}
                className="border-border/40 hover:border-primary/20 transition-all rounded-xl overflow-hidden bg-background/50 hover:bg-background/80"
              >
                <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-primary">{art.source?.name}</span>
                      {art.author && (
                        <span className="text-[10px] text-muted-foreground font-medium">By {art.author}</span>
                      )}
                    </div>
                    <p className="text-sm font-semibold text-foreground mt-1 hover:underline">
                      <a href={art.url} target="_blank" rel="noopener noreferrer">
                        {art.title}
                      </a>
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    render={<a href={art.url} target="_blank" rel="noopener noreferrer" />}
                    className="rounded-lg hover:bg-muted text-xs flex items-center gap-1.5"
                  >
                    Original Article
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
