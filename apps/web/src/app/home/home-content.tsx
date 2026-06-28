"use client";

import { useState, useEffect, Suspense, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useInfiniteQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { CategoryTabs } from "@/components/layout/category-tabs";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { SidebarWidgets } from "@/components/sidebar/sidebar-widgets";
import { Newspaper } from "lucide-react";
import { BreakingBanner } from "@/components/ui/breaking-banner";
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
  { slug: "entertainment", name: "Entertainment" },
  { slug: "lifestyle", name: "Lifestyle" },
  { slug: "health", name: "Health" },
  { slug: "travel", name: "Travel" },
  { slug: "education", name: "Education" },
  { slug: "science", name: "Science" },
  { slug: "weather", name: "Weather" },
  { slug: "world", name: "World" },
];

function HomeContentInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [category, setCategory] = useState<string>(
    () => searchParams.get("category") ?? "all"
  );
  const [prevCategoryParam, setPrevCategoryParam] = useState<string | null>(null);
  const { isAuthenticated, isLoading: isAuthLoading } = useAuthStore();

  // Sync tab when URL param changes (e.g. back-navigation)
  const categoryParam = searchParams.get("category") ?? "all";
  if (categoryParam !== prevCategoryParam) {
    setPrevCategoryParam(categoryParam);
    setCategory(categoryParam);
  }

  // Serve personalized feed when authenticated + on the "personalized" tab.
  // We wait for auth initialization to be finished before deciding.
  const isPersonalized = !isAuthLoading && isAuthenticated && category === "personalized";

  const {
    data,
    isLoading,
    error,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery<Story[]>({
    queryKey: isPersonalized ? ["stories", "personalized"] : ["stories", category],
    queryFn: async ({ pageParam }) => {
      const offset = pageParam as number;
      const limit = 20;
      if (category === "personalized") {
        if (!isAuthenticated) {
          return [];
        }
        try {
          const res = await apiClient.get("/stories/feed/personalized", {
            params: { limit, offset },
          });
          return res.data;
        } catch (err) {
          const error = err as { response?: { status?: number } };
          // If the personalized feed fails with 401 despite our auth state, 
          // we return empty array.
          if (error.response?.status !== 401) {
             throw err;
          }
          return [];
        }
      }
      const params: Record<string, string | number> = { limit, offset };
      if (category !== "all") params.category = category;
      const response = await apiClient.get("/stories", { params });
      return response.data;
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || lastPage.length < 20) return undefined;
      return allPages.length * 20;
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

  const observerTarget = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hasNextPage || isFetchingNextPage) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const sidebar = <SidebarWidgets trendingStories={trendingStories} isLoading={isTrendingLoading} />;

  const allStories = data?.pages.flatMap((page) => page) ?? [];
  // Deduplicate stories by ID to prevent duplicate items from rendering
  const uniqueStories = Array.from(new Map(allStories.map((s) => [s.id, s])).values());
  const hasStories = !isLoading && !error && uniqueStories.length > 0;

  const handleCategorySelect = (slug: string) => {
    setCategory(slug);
    // Keep URL in sync so the browser back button and shareability work
    const params = new URLSearchParams(searchParams.toString());
    if (slug === "all") {
      params.delete("category");
    } else {
      params.set("category", slug);
    }
    const query = params.toString();
    router.replace(`/home${query ? `?${query}` : ""}`, { scroll: false });
  };

  return (
    <AppShell
      sidebar={sidebar}
      categoryTabs={
        <CategoryTabs
          categories={CATEGORIES}
          activeCategory={category}
          onSelect={handleCategorySelect}
        />
      }
    >
      {/* Breaking News Banner */}
      {hasStories && (
        <BreakingBanner
          text={`${uniqueStories[0].headline} — ${uniqueStories[0].source_count} sources covering`}
          time="Just now"
          onClick={() => router.push(`/story/${uniqueStories[0].id}`)}
        />
      )}

      {/* Section label — fixed height, never changes */}
      <div className="slbl" style={{ marginTop: hasStories ? 12 : 24 }}>
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
      ) : !uniqueStories || uniqueStories.length === 0 ? (
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
        <>
          <div className="feed-list">
            {uniqueStories.map((story, index) => (
              <StoryCard key={story.id} story={story} index={index} />
            ))}
          </div>
          
          {/* Scroll observer target */}
          <div ref={observerTarget} style={{ height: 40, display: "flex", alignItems: "center", justifyContent: "center" }}>
            {isFetchingNextPage && (
              <div className="feed-list" style={{ width: "100%", marginTop: 12 }}>
                <StoryCardSkeleton />
                <StoryCardSkeleton />
              </div>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}

// Wrap in Suspense because useSearchParams requires it in Next.js App Router
export function HomeContent() {
  return (
    <Suspense fallback={null}>
      <HomeContentInner />
    </Suspense>
  );
}
