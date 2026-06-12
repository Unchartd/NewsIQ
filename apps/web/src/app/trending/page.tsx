"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { TrendingUp, Clock, Flame } from "lucide-react";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";

export default function TrendingPage() {
  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["trending-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories", {
        params: {
          trending: "true",
          limit: 15,
        },
      });
      return response.data;
    },
  });

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 pb-24">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-600 dark:text-purple-400">
            <Flame className="w-5 h-5 fill-current" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Trending Stories</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              The fastest-growing stories based on publisher volume and engagement.
            </p>
          </div>
        </div>

        {/* Stories List */}
        {isLoading ? (
          <div className="space-y-4">
            <StoryCardSkeleton />
            <StoryCardSkeleton />
          </div>
        ) : error ? (
          <EmptyState
            title="Failed to load trending stories"
            description="We encountered an issue connecting to the NewsIQ services."
            actionLabel="Retry"
            onAction={refetch}
          />
        ) : !stories || stories.length === 0 ? (
          <EmptyState
            icon={TrendingUp}
            title="No trending stories"
            description="Trending scores will update once more news is ingested and clustered."
          />
        ) : (
          <div className="space-y-4">
            {stories.map((story, index) => (
              <StoryCard key={story.id} story={story} index={index} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
