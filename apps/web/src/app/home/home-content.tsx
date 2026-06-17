"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { CategoryTabs } from "@/components/layout/category-tabs";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { SidebarWidgets } from "@/components/sidebar/sidebar-widgets";
import { Newspaper } from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { Story } from "@/types";

const CATEGORIES = [
  { slug: "all", name: "All" },
  { slug: "personalized", name: "For You" },
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
  const router = useRouter();
  const [category, setCategory] = useState<string>("all");
  const { isAuthenticated, isLoading: isAuthLoading } = useAuthStore();

  // Serve personalized feed when authenticated + on the "personalized" tab.
  // We wait for auth initialization to be finished before deciding.
  const isPersonalized = !isAuthLoading && isAuthenticated && category === "personalized";

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: isPersonalized ? ["stories", "personalized"] : ["stories", category],
    queryFn: async () => {
      if (category === "personalized") {
        if (!isAuthenticated) {
          return [];
        }
        try {
          const res = await apiClient.get("/stories/feed/personalized");
          return res.data;
        } catch (err: any) {
          // If the personalized feed fails with 401 despite our auth state, 
          // we return empty array.
          if (err.response?.status !== 401) {
             throw err;
          }
          return [];
        }
      }
      const params: Record<string, string> = {};
      if (category !== "all") params.category = category;
      const response = await apiClient.get("/stories", { params });
      return response.data;
    },
    // Prevent query from running if we are still determining auth state for the personalized feed
    enabled: !isAuthLoading,
  });

  const { data: trendingStories = [], isLoading: isTrendingLoading } = useQuery<Story[]>({
    queryKey: ["stories", "trending-sidebar"],
    queryFn: async () => {
      const response = await apiClient.get("/stories", {
        params: {
          trending: "true",
          limit: 4,
        },
      });
      return response.data;
    },
  });

  const sidebar = <SidebarWidgets trendingStories={trendingStories} isLoading={isTrendingLoading} />;

  return (
    <AppShell
      sidebar={sidebar}
      categoryTabs={
        <CategoryTabs
          categories={CATEGORIES}
          activeCategory={category}
          onSelect={setCategory}
        />
      }
    >
      {/* Section label — fixed height, never changes */}
      <div className="slbl" style={{ marginTop: 24 }}>
        {category === "personalized" ? "Your Personalized Feed" : "Top Stories"}
      </div>

      {/* Feed Content — all states use .feed-list so dimensions are stable */}
      {isLoading ? (
        <div className="feed-list">
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
          title={
            category === "personalized" && !isAuthenticated
              ? "Personalized Feed"
              : "No stories found"
          }
          description={
            category === "personalized" && !isAuthenticated
              ? "Please sign in to customize your feed by category and country preferences."
              : category !== "all" && category !== "personalized"
              ? "No stories matched the selected filters. Try changing filters."
              : "No news stories have been clustered yet. Trigger ingestion to populate the feed."
          }
          actionLabel={
            category === "personalized" && !isAuthenticated
              ? "Sign In"
              : category !== "all"
              ? "Clear Filters"
              : "Trigger News Ingestion"
          }
          onAction={
            category === "personalized" && !isAuthenticated
              ? () => router.push("/login")
              : category !== "all"
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
        <div className="feed-list">
          {stories.map((story, index) => (
            <StoryCard key={story.id} story={story} index={index} />
          ))}
        </div>
      )}
    </AppShell>
  );
}
