"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { Search, SearchX, X } from "lucide-react";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";
import { Suspense, useState, useEffect } from "react";

const RECENT_SEARCHES = [
  "OpenAI GPT-5",
  "India elections",
  "Bengaluru rain",
  "RBI interest rate",
];

const FILTER_CHIPS = [
  { slug: "all", name: "All" },
  { slug: "technology", name: "Technology" },
  { slug: "politics", name: "Politics" },
  { slug: "business", name: "Business" },
  { slug: "india", name: "India" },
  { slug: "today", name: "Today" },
  { slug: "trending", name: "Trending only" },
];

function SearchResults() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("q") || "";
  
  const [searchInput, setSearchInput] = useState(urlQuery);
  const [activeFilter, setActiveFilter] = useState("all");

  // Keep local search input in sync when URL changes (e.g. from navbar search)
  useEffect(() => {
    setSearchInput(urlQuery);
  }, [urlQuery]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/search?q=${encodeURIComponent(searchInput.trim())}`);
  };

  const handleRecentClick = (term: string) => {
    setSearchInput(term);
    router.push(`/search?q=${encodeURIComponent(term)}`);
  };

  const handleClear = () => {
    setSearchInput("");
    router.push("/search");
  };

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["search-stories", urlQuery, activeFilter],
    queryFn: async () => {
      if (!urlQuery.trim()) return [];
      const params: Record<string, string> = { q: urlQuery };
      
      if (activeFilter !== "all") {
        if (activeFilter === "trending") {
          params.trending = "true";
        } else if (activeFilter === "today") {
          // Mock or real filter for today
          params.limit = "5";
        } else {
          params.category = activeFilter;
        }
      }
      
      const response = await apiClient.get("/stories", { params });
      return response.data;
    },
    enabled: !!urlQuery,
  });

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 24px" }}>
      {/* Search Hero Section */}
      <div className="niq-search-hero">
        <h1 className="niq-search-hero-title">Find any story</h1>
        <form onSubmit={handleSearchSubmit} className="niq-search-big">
          <Search className="w-5 h-5 text-gray-400 shrink-0" />
          <input
            type="text"
            placeholder="Bengaluru floods, RBI rate, GPT-5…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
          {searchInput && (
            <button
              type="button"
              onClick={handleClear}
              style={{
                fontSize: 12,
                color: "var(--ink-3)",
                cursor: "pointer",
                padding: "4px 8px",
                border: "1px solid var(--border)",
                borderRadius: 4,
                background: "var(--surface)",
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: 2,
              }}
            >
              <X className="w-3 h-3" />
              Clear
            </button>
          )}
        </form>

        {/* Recent Searches */}
        <div className="niq-recent-chips">
          <span style={{ fontSize: 11, color: "var(--ink-3)", alignSelf: "center", marginRight: 4 }}>
            Recent:
          </span>
          {RECENT_SEARCHES.map((term) => (
            <button
              key={term}
              type="button"
              className="niq-recent-chip"
              onClick={() => handleRecentClick(term)}
            >
              {term}
            </button>
          ))}
        </div>
      </div>

      {/* Filters Row */}
      <div className="niq-filter-row">
        <span style={{ fontSize: 12, color: "var(--ink-3)", fontWeight: 600 }}>Filter:</span>
        {FILTER_CHIPS.map((chip) => (
          <button
            key={chip.slug}
            type="button"
            className={`niq-filter-chip ${activeFilter === chip.slug ? "active" : ""}`}
            onClick={() => setActiveFilter(chip.slug)}
          >
            {chip.name}
          </button>
        ))}
      </div>

      {/* Results Section */}
      <div className="section-label">
        {isLoading
          ? "Searching..."
          : stories
          ? `${stories.length} ${stories.length === 1 ? "story" : "stories"} found`
          : "0 stories found"}
      </div>

      {!urlQuery ? (
        <div style={{ padding: "40px 0" }}>
          <EmptyState
            icon={Search}
            title="Start searching"
            description="Type keywords, topics, locations, or news publishers in the search bar above."
          />
        </div>
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
          description={`We couldn't find any clustered stories matching "${urlQuery}". Try different terms.`}
        />
      ) : (
        <div className="space-y-4 pb-24">
          {stories.map((story) => (
            <StoryCard key={story.id} story={story} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SearchPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div style={{ maxWidth: 800, margin: "0 auto", padding: "24px" }}>
            <StoryCardSkeleton />
          </div>
        }
      >
        <SearchResults />
      </Suspense>
    </AppShell>
  );
}
