"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { CategoryTabs } from "@/components/layout/category-tabs";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { BreakingBanner } from "@/components/ui/breaking-banner";
import { SidebarWidgets } from "@/components/sidebar/sidebar-widgets";
import { Newspaper } from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { Story } from "@/types";

const CATEGORIES = [
  { slug: "all", name: "All" },
  { slug: "politics", name: "Politics" },
  { slug: "technology", name: "Technology" },
  { slug: "business", name: "Business" },
  { slug: "sports", name: "Sports" },
  { slug: "health", name: "Health" },
  { slug: "science", name: "Science" },
  { slug: "weather", name: "Weather" },
  { slug: "world", name: "World" },
];

export function HomeContent() {
  const [category, setCategory] = useState<string>("all");
  const { isAuthenticated } = useAuthStore();

  // Serve personalized feed when authenticated + on the "all" tab.
  // Gracefully falls back to global /stories if the endpoint returns empty or errors.
  const isPersonalized = isAuthenticated && category === "all";

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: isPersonalized ? ["stories", "personalized"] : ["stories", category],
    queryFn: async () => {
      if (isPersonalized) {
        try {
          const res = await apiClient.get("/stories/feed/personalized");
          if (res.data && res.data.length > 0) return res.data;
        } catch {
          // Personalized endpoint unavailable — fall through to global feed
        }
      }
      const params: Record<string, string> = {};
      if (category !== "all") params.category = category;
      const response = await apiClient.get("/stories", { params });
      return response.data;
    },
  });

  // Use first few stories as trending sidebar data
  const trendingStories = stories?.slice(0, 4) || [];
  const sidebar = <SidebarWidgets trendingStories={trendingStories} />;

  return (
    <AppShell sidebar={sidebar}>
      {/* Category Tabs (rendered above the 2-col layout, full-width) */}
      <div style={{ marginLeft: -24, marginRight: -24, marginTop: -24, marginBottom: 24 }}>
        <CategoryTabs
          categories={CATEGORIES}
          activeCategory={category}
          onSelect={setCategory}
        />
      </div>

      {/* Breaking banner — driven by the top story, not hardcoded */}
      {stories && stories.length > 0 && (
        <BreakingBanner
          text={`${stories[0].headline} — ${stories[0].source_count ?? 1} sources covering`}
          time="Just now"
        />
      )}

      {/* Section label */}
      <div className="niq-section-label">
        {isPersonalized ? "Your Personalized Feed" : "Top Stories"}
      </div>

      {/* Feed Content */}
      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <StoryCardSkeleton />
          <StoryCardSkeleton />
          <StoryCardSkeleton />
        </div>
      ) : error ? (
        <EmptyState
          title="Failed to load stories"
          description="We encountered an issue connecting to the NewsIQ services. Please try again."
          actionLabel="Retry"
          onAction={refetch}
        />
      ) : !stories || stories.length === 0 ? (
        <EmptyState
          icon={Newspaper}
          title="No stories found"
          description={
            category !== "all"
              ? "No stories matched the selected filters. Try changing filters."
              : "No news stories have been clustered yet. Trigger ingestion to populate the feed."
          }
          actionLabel={category !== "all" ? "Clear Filters" : "Trigger News Ingestion"}
          onAction={
            category !== "all"
              ? () => setCategory("all")
              : async () => {
                  try {
                    await apiClient.post("/sources/trigger-ingestion");
                    alert("News ingestion triggered! Refresh in 30 seconds.");
                    refetch();
                  } catch {
                    alert("Sign in to trigger ingestion.");
                  }
                }
          }
        />
      ) : (
        <>
          {stories.map((story, index) => (
            <StoryCard key={story.id} story={story} index={index} />
          ))}

          {/* Loading indicator */}
          <div style={{
            textAlign: "center", padding: "28px 0", color: "var(--ink-3)",
            fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
          }}>
            <div style={{
              width: 18, height: 18, border: "2px solid var(--border)",
              borderTopColor: "var(--primary)", borderRadius: "50%",
              animation: "spin 0.8s linear infinite",
            }} />
            Loading more stories…
          </div>
        </>
      )}
    </AppShell>
  );
}
