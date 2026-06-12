"use client";

import { AppShell } from "@/components/layout/app-shell";
import { StoryFeedSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { Newspaper } from "lucide-react";

export function HomeContent() {
  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        {/* Heading */}
        <div>
          <h1 className="text-2xl font-bold">Your Feed</h1>
          <p className="text-muted-foreground text-sm mt-1">
            AI-curated stories from trusted sources.
          </p>
        </div>

        {/* Placeholder — will be replaced with real data in Phase 6 */}
        <EmptyState
          icon={Newspaper}
          title="Stories are on the way"
          description="The news ingestion pipeline will populate your feed once it runs. Start Docker and run the ingestion worker."
        />
      </div>
    </AppShell>
  );
}
