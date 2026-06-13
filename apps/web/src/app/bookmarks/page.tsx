"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { CategoryBadge } from "@/components/ui/category-badge";
import { Bookmark, Lock, Search } from "lucide-react";
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

  // Filter bookmarks locally
  const filteredStories = stories?.filter((story) => {
    const matchesSearch = story.headline.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (story.category?.name && story.category.name.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesSearch;
  }) || [];

  return (
    <AppShell>
      <div style={{ maxWidth: 660, margin: "0 auto", padding: "0 24px" }}>
        {/* Bookmarks Header */}
        <div style={{ padding: "28px 0 20px" }}>
          <h1 style={{ fontFamily: "var(--fd)", fontSize: 26, fontWeight: 600, marginBottom: 4 }}>
            Saved stories
          </h1>
          <p style={{ fontSize: 14, color: "var(--ink3)" }}>
            {stories ? `${stories.length} bookmarked stories` : "0 bookmarked stories"}
          </p>
        </div>

        {/* Search Input */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r6)",
            padding: "0 14px",
            height: 38,
            marginBottom: 20,
            maxWidth: 320,
          }}
        >
          <Search size={14} style={{ color: "var(--ink3)", flexShrink: 0 }} />
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
              fontSize: 14,
              fontFamily: "var(--fb)",
              color: "var(--ink)",
              width: "100%",
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
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
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
          <div style={{ display: "flex", flexDirection: "column", gap: 10, paddingBottom: 96 }}>
            {filteredStories.map((story) => (
              <Link
                href={`/story/${story.id}`}
                key={story.id}
                className="bkcard"
                style={{ textDecoration: "none" }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ marginBottom: 6 }}>
                    {story.category && <CategoryBadge category={story.category.name} />}
                  </div>
                  <div className="bk-hl">{story.headline}</div>
                  <div className="bk-mt">
                    <span>{story.source_count || 1} sources</span>
                    <span>Saved recently</span>
                  </div>
                </div>
                
                <div className="bk-acts">
                  <button
                    type="button"
                    className="bk-ab"
                    onClick={(e) => handleShare(story, e)}
                  >
                    Share
                  </button>
                  <button
                    type="button"
                    className="bk-ab rm"
                    onClick={(e) => handleRemove(story.id, e)}
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
