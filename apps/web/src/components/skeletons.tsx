"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";
import { CARD_PADDING, SKELETON_CARD_HEIGHT, CARD_WIDTH } from "@/lib/layout-constants";

export function StoryCardSkeleton() {
  return (
    <div
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: SKELETON_CARD_HEIGHT,
        width: CARD_WIDTH,
        padding: CARD_PADDING,
        cursor: "default",
      }}
    >
      {/* Meta row matching .cmeta */}
      <div className="cmeta">
        <Skeleton className="h-5 w-16 rounded-full" />
        <span className="mdot" />
        <Skeleton className="h-4 w-20" />
        <span className="mtime" style={{ marginLeft: "auto" }}>
          <Skeleton className="h-4 w-12" />
        </span>
      </div>

      {/* Headline matching .chead */}
      <div className="chead">
        <Skeleton className="h-5 w-full mb-2" />
        <Skeleton className="h-5 w-3/4" />
      </div>

      {/* Summary matching .csum */}
      <div className="csum">
        <Skeleton className="h-4 w-full mb-1.5" />
        <Skeleton className="h-4 w-5/6" />
      </div>

      {/* Footer matching .cfoot */}
      <div className="cfoot">
        <div className="srcs">
          <Skeleton className="h-4 w-20" />
        </div>
        <div className="bkbtn" style={{ marginLeft: "auto", cursor: "default", background: "none" }}>
          <Skeleton className="h-8 w-8 rounded-full" />
        </div>
      </div>
    </div>
  );
}

export function StoryFeedSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <StoryCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function TrendingBannerSkeleton() {
  return (
    <Card className="border-border/50 p-6">
      <Skeleton className="h-6 w-32 mb-4" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-16 rounded-full" />
            <Skeleton className="h-5 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ))}
      </div>
    </Card>
  );
}
