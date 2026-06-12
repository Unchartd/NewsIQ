"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { SearchX, Search } from "lucide-react";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";
import { Suspense } from "react";

function SearchResults() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["search-stories", query],
    queryFn: async () => {
      if (!query.trim()) return [];
      const response = await apiClient.get("/stories", {
        params: { q: query },
      });
      return response.data;
    },
    enabled: !!query,
  });

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 pb-24">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
          <Search className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Search Results</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {query ? `Showing results for "${query}"` : "Enter a search query to scan stories"}
          </p>
        </div>
      </div>

      {/* Stories List */}
      {!query ? (
        <EmptyState
          icon={Search}
          title="Start searching"
          description="Type keywords, topics, locations, or news publishers in the top search bar."
        />
      ) : isLoading ? (
        <div className="space-y-4">
          <StoryCardSkeleton />
          <StoryCardSkeleton />
        </div>
      ) : error ? (
        <EmptyState
          title="Search failed"
          description="We encountered an issue scanning for stories."
          actionLabel="Retry"
          onAction={refetch}
        />
      ) : !stories || stories.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title="No stories matched"
          description={`We couldn't find any clustered stories matching "${query}". Try different terms.`}
        />
      ) : (
        <div className="space-y-4">
          {stories.map((story, index) => (
            <StoryCard key={story.id} story={story} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <AppShell>
      <Suspense fallback={
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          <StoryCardSkeleton />
        </div>
      }>
        <SearchResults />
      </Suspense>
    </AppShell>
  );
}
