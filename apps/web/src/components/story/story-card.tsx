"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { MapPin, TrendingUp, Bookmark, BookmarkCheck } from "lucide-react";
import { CategoryBadge } from "@/components/ui/category-badge";
import { SourceDots } from "@/components/ui/source-dots";
import type { Story } from "@/types";

interface StoryCardProps {
  story: Story;
  summaryType?: "one_line" | "short" | "detailed";
  index?: number;
}

export function StoryCard({ story, summaryType = "short", index = 0 }: StoryCardProps) {
  const summary =
    summaryType === "one_line"
      ? story.one_line_summary
      : summaryType === "detailed"
        ? story.detailed_summary
        : story.short_summary;

  const timeAgo = formatTimeAgo(story.updated_at);
  const locationLabel = story.location_city || story.location_state || story.location_country;
  const isTrending = story.trend_score > 70;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
    >
      <Link href={`/story/${story.id}`} className="niq-story-card" tabIndex={0}>
        {/* Meta row */}
        <div className="niq-card-meta">
          {story.category && (
            <CategoryBadge category={story.category.name} />
          )}
          {locationLabel && (
            <>
              <span className="niq-meta-dot" />
              <span className="niq-meta-loc">
                <MapPin size={11} />
                {locationLabel}
              </span>
            </>
          )}
          <span className="niq-meta-time">{timeAgo}</span>
        </div>

        {/* Headline */}
        <h2 className="niq-card-headline">{story.headline}</h2>

        {/* Summary */}
        {summary && (
          <p className="niq-card-summary">{summary}</p>
        )}

        {/* Footer */}
        <div className="niq-card-footer">
          <SourceDots count={story.source_count} />
          {isTrending && (
            <span className="niq-trending-badge">
              <TrendingUp size={11} />
              Trending
            </span>
          )}
          <button
            className="niq-bookmark-btn"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              // TODO: toggle bookmark via API
            }}
            title="Bookmark story"
          >
            <Bookmark size={16} />
          </button>
        </div>
      </Link>
    </motion.div>
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
