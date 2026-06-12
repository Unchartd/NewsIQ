"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Clock, Bookmark, TrendingUp, MessageSquare } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
    >
      <Link href={`/story/${story.id}`}>
        <Card className="group border-border/50 hover:border-primary/30 hover:shadow-md transition-all duration-300 overflow-hidden">
          <CardContent className="p-5">
            {/* Top row: category + time */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                {story.category && (
                  <Badge
                    variant="secondary"
                    className="text-xs font-medium px-2.5 py-0.5 rounded-full"
                  >
                    {story.category.name}
                  </Badge>
                )}
                {story.trend_score > 80 && (
                  <Badge
                    variant="default"
                    className="text-xs px-2 py-0.5 rounded-full bg-[var(--trending)] text-white"
                  >
                    <TrendingUp className="w-3 h-3 mr-1" />
                    Trending
                  </Badge>
                )}
              </div>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {timeAgo}
              </span>
            </div>

            {/* Headline */}
            <h3 className="text-base font-semibold leading-snug mb-2 group-hover:text-primary transition-colors line-clamp-2">
              {story.headline}
            </h3>

            {/* Summary */}
            <p className="text-sm text-muted-foreground leading-relaxed mb-3 line-clamp-3">
              {summary}
            </p>

            {/* Bottom row: sources + tags */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <MessageSquare className="w-3 h-3" />
                  {story.source_count} source{story.source_count !== 1 ? "s" : ""}
                </span>
                {story.location_country && (
                  <span>{story.location_country}</span>
                )}
              </div>

              {/* Tags */}
              {story.tags.length > 0 && (
                <div className="flex items-center gap-1.5">
                  {story.tags.slice(0, 2).map((tag) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className="text-[10px] px-2 py-0 rounded-full font-normal"
                    >
                      {tag}
                    </Badge>
                  ))}
                  {story.tags.length > 2 && (
                    <span className="text-[10px] text-muted-foreground">
                      +{story.tags.length - 2}
                    </span>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
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
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}
