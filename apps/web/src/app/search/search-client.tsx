"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { Search, SearchX } from "lucide-react";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";
import { Suspense, useState } from "react";

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
  const [prevUrlQuery, setPrevUrlQuery] = useState(urlQuery);

  // Keep local search input in sync when URL changes
  if (urlQuery !== prevUrlQuery) {
    setPrevUrlQuery(urlQuery);
    setSearchInput(urlQuery);
  }

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

  const sidebar = (
    <div className="sticky-p">
      <div className="widget">
        <div className="slbl">Recent Searches</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {RECENT_SEARCHES.map((term) => (
            <button
              key={term}
              type="button"
              onClick={() => handleRecentClick(term)}
              style={{
                textAlign: "left",
                padding: "10px 12px",
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--r6)",
                fontSize: 13,
                fontWeight: 500,
                color: "var(--ink2)",
                cursor: "pointer",
                width: "100%",
                transition: "border-color 0.15s, color 0.15s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--primary)";
                e.currentTarget.style.color = "var(--primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.color = "var(--ink2)";
              }}
            >
              {term}
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <AppShell sidebar={sidebar}>
      {/* Search Hero Section */}
      <div style={{ padding: "28px 0 20px" }}>
        <h1 style={{ fontFamily: "var(--fd)", fontSize: 26, fontWeight: 600, marginBottom: 12 }}>
          Find any story
        </h1>
        <form onSubmit={handleSearchSubmit} className="bigsch">
          <Search size={18} style={{ color: "var(--ink3)", flexShrink: 0 }} />
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
                color: "var(--ink3)",
                cursor: "pointer",
                padding: "4px 8px",
                border: "1px solid var(--border)",
                borderRadius: "var(--r4)",
                background: "var(--surface)",
                whiteSpace: "nowrap",
              }}
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Filters Row */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          marginBottom: 20,
        }}
      >
        <span style={{ fontSize: 12, color: "var(--ink3)", fontWeight: 600 }}>Filter:</span>
        {FILTER_CHIPS.map((chip) => (
          <button
            key={chip.slug}
            type="button"
            className={`fchp ${activeFilter === chip.slug ? "on" : ""}`}
            onClick={() => setActiveFilter(chip.slug)}
          >
            {chip.name}
          </button>
        ))}
      </div>

      {/* Results Section */}
      <div className="slbl">
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
        <div className="feed-list">
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
        <div className="feed-list" style={{ paddingBottom: 96 }}>
          {stories.map((story) => (
            <StoryCard key={story.id} story={story} />
          ))}
        </div>
      )}
    </AppShell>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div style={{ maxWidth: 800, margin: "0 auto", padding: "24px" }}>
            <StoryCardSkeleton />
          </div>
        </AppShell>
      }
    >
      <SearchResults />
    </Suspense>
  );
}
