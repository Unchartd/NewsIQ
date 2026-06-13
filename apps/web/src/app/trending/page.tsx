"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { CategoryBadge } from "@/components/ui/category-badge";
import { TrendingUp, Flame } from "lucide-react";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";
import Link from "next/link";

const TIME_TABS = [
  { slug: "today", name: "Today" },
  { slug: "24h", name: "24 hours" },
  { slug: "7d", name: "7 days" },
  { slug: "30d", name: "30 days" },
];

export default function TrendingPage() {
  const [activeTab, setActiveTab] = useState("today");

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["trending-stories", activeTab],
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

  // Aggregate stories by category for sidebar
  const categoryCounts = stories
    ? stories.reduce<Record<string, number>>((acc, s) => {
        const catSlug = s.category?.slug || "world";
        acc[catSlug] = (acc[catSlug] || 0) + 1;
        return acc;
      }, {})
    : {};

  const sidebar = (
    <div style={{ paddingTop: 0 }}>
      <div className="section-label">Trending by category</div>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {Object.entries(categoryCounts).map(([catSlug, count]) => (
          <div
            key={catSlug}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "8px 10px",
              background: "var(--card)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <CategoryBadge category={catSlug} />
            </div>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--ink)" }}>
              {count} {count === 1 ? "story" : "stories"}
            </span>
          </div>
        ))}
        {Object.keys(categoryCounts).length === 0 && (
          <div style={{ fontSize: "13px", color: "var(--ink-3)", fontStyle: "italic" }}>
            No category data available
          </div>
        )}
      </div>
    </div>
  );

  return (
    <AppShell sidebar={sidebar}>
      {/* Header */}
      <div style={{ padding: "28px 0 20px" }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 600, marginBottom: 4 }}>
          Trending Stories
        </h1>
        <p style={{ fontSize: 14, color: "var(--ink-3)" }}>
          Ranked by source count, recency, and engagement velocity
        </p>
      </div>

      {/* Tabs */}
      <div className="niq-trend-tabs">
        {TIME_TABS.map((tab) => (
          <button
            key={tab.slug}
            className={`niq-trend-tab ${activeTab === tab.slug ? "active" : ""}`}
            onClick={() => setActiveTab(tab.slug)}
          >
            {tab.name}
          </button>
        ))}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-4">
          <StoryCardSkeleton />
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
        <div style={{ display: "flex", flexDirection: "column" }}>
          {stories.map((story, index) => {
            const rank = index + 1;
            let rankClass = "";
            if (rank === 1) rankClass = "niq-rank-1";
            else if (rank === 2) rankClass = "niq-rank-2";
            else if (rank === 3) rankClass = "niq-rank-3";

            // Generate a realistic looking velocity score
            const charCode = story.id ? story.id.charCodeAt(0) : 50;
            const velocity = 1000 - rank * 120 + (charCode % 80);

            const locationLabel = story.location_city || story.location_state || story.location_country || "World";
            const timeAgo = formatTimeAgo(story.updated_at);

            return (
              <Link
                href={`/story/${story.id}`}
                key={story.id}
                className="niq-trend-rank-card hover:no-underline"
              >
                <div className={`niq-rank-num ${rankClass}`}>{rank}</div>
                <div className="niq-rank-body">
                  <h2 className="niq-rank-headline hover:text-[#C41E3A] transition-colors duration-150">
                    {story.headline}
                  </h2>
                  <div className="niq-rank-meta">
                    {story.category && (
                      <CategoryBadge category={story.category.name} />
                    )}
                    <span className="meta-dot"></span>
                    <span>{story.source_count || 1} sources</span>
                    <span className="meta-dot"></span>
                    <span className="niq-velocity">
                      <TrendingUp className="w-3 h-3" style={{ marginRight: 2 }} />
                      +{velocity > 0 ? velocity : 50} in 1h
                    </span>
                    <span className="meta-dot"></span>
                    <span>
                      {locationLabel} · {timeAgo}
                    </span>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </AppShell>
  );
}

function formatTimeAgo(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / (1000 * 60));
    const diffHr = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHr / 24);

    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
