"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { CategoryBadge } from "@/components/ui/category-badge";
import { Bookmark, Lock, Search, Share2, Trash2 } from "lucide-react";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { Story } from "@/types";
import { useState } from "react";
import { toast } from "sonner";
import Link from "next/link";

export default function BookmarksPage() {
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["bookmarked-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories/bookmarks");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const removeBookmarkMutation = useMutation({
    mutationFn: async (storyId: string) => {
      await apiClient.delete(`/stories/${storyId}/bookmark`);
    },
    onSuccess: () => {
      toast.success("Story removed from bookmarks");
      queryClient.invalidateQueries({ queryKey: ["bookmarked-stories"] });
    },
    onError: () => {
      toast.error("Failed to remove bookmark");
    },
  });

  const handleShare = (story: Story, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (navigator.share) {
      navigator.share({
        title: story.headline,
        text: story.one_line_summary,
        url: `${window.location.origin}/story/${story.id}`,
      })
      .then(() => toast.success("Shared successfully"))
      .catch(() => {});
    } else {
      navigator.clipboard.writeText(`${window.location.origin}/story/${story.id}`);
      toast.success("Link copied to clipboard!");
    }
  };

  const handleRemove = (storyId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    removeBookmarkMutation.mutate(storyId);
  };

  // Filter bookmarks locally by headline or category
  const filteredStories = stories?.filter((story) => {
    const matchesSearch = story.headline.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (story.category?.name && story.category.name.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesSearch;
  }) || [];

  return (
    <AppShell>
      <div style={{ maxWidth: 800, margin: "0 auto", padding: "0 24px" }}>
        {/* Bookmarks Header */}
        <div style={{ padding: "28px 0 20px" }}>
          <h1 style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 600, marginBottom: 4 }}>
            Saved stories
          </h1>
          <p style={{ fontSize: 14, color: "var(--ink-3)" }}>
            {stories ? `${stories.length} bookmarked stories` : "0 bookmarked stories"}
          </p>
        </div>

        {/* Search Saved Stories Input */}
        <div
          className="bk-search"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            padding: "0 14px",
            height: 40,
            marginBottom: 20,
          }}
        >
          <Search className="w-4 h-4 text-gray-400 shrink-0" />
          <input
            type="text"
            placeholder="Search saved stories…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1,
              border: "none",
              background: "none",
              outline: "none",
              fontSize: 13,
              fontFamily: "var(--font-inter), sans-serif",
              color: "var(--ink)",
            }}
          />
        </div>

        {/* Main Content */}
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
        ) : filteredStories.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No matches found"
            description={`We couldn't find any bookmarks matching "${searchQuery}".`}
          />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingBottom: 60 }}>
            {filteredStories.map((story) => (
              <Link
                href={`/story/${story.id}`}
                key={story.id}
                className="niq-bk-card"
              >
                <div className="niq-bk-body">
                  <div style={{ marginBottom: 6 }}>
                    {story.category && <CategoryBadge category={story.category.name} />}
                  </div>
                  <div className="niq-bk-headline">{story.headline}</div>
                  <div className="niq-bk-meta">
                    <span>{story.source_count || 1} sources</span>
                    <span>•</span>
                    <span>Saved recently</span>
                  </div>
                </div>
                
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 6,
                    alignItems: "flex-end",
                    justifyContent: "center",
                  }}
                >
                  <button
                    type="button"
                    onClick={(e) => handleShare(story, e)}
                    style={{
                      padding: "5px 10px",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      fontSize: 11,
                      fontWeight: 500,
                      color: "var(--ink-3)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                      transition: "all 150ms",
                      background: "none",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--ink-2)";
                      e.currentTarget.style.color = "var(--ink)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.color = "var(--ink-3)";
                    }}
                  >
                    Share
                  </button>
                  <button
                    type="button"
                    onClick={(e) => handleRemove(story.id, e)}
                    style={{
                      padding: "5px 10px",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      fontSize: 11,
                      fontWeight: 500,
                      color: "var(--ink-3)",
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                      transition: "all 150ms",
                      background: "none",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = "var(--error)";
                      e.currentTarget.style.color = "var(--error)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = "var(--border)";
                      e.currentTarget.style.color = "var(--ink-3)";
                    }}
                  >
                    Remove
                  </button>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
