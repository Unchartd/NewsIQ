"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { Bookmark, Lock } from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { Story } from "@/types";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function BookmarksPage() {
  const { isAuthenticated } = useAuthStore();

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["bookmarked-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories/bookmarks");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 pb-24">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-600 dark:text-blue-400">
            <Bookmark className="w-5 h-5 fill-current" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Bookmarked Stories</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              Stories you have saved for reading later.
            </p>
          </div>
        </div>

        {/* Auth Check */}
        {!isAuthenticated ? (
          <EmptyState
            icon={Lock}
            title="Sign in to save bookmarks"
            description="You need a NewsIQ account to bookmark stories and sync them across devices."
            actionLabel="Sign In"
            onAction={() => {
              window.location.href = "/login";
            }}
          />
        ) : isLoading ? (
          <div className="space-y-4">
            <StoryCardSkeleton />
            <StoryCardSkeleton />
          </div>
        ) : error ? (
          <EmptyState
            title="Failed to load bookmarks"
            description="We encountered an issue connecting to the NewsIQ services."
            actionLabel="Retry"
            onAction={refetch}
          />
        ) : !stories || stories.length === 0 ? (
          <EmptyState
            icon={Bookmark}
            title="No bookmarks yet"
            description="Bookmark interesting stories from your feed to save them here."
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
