"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";
import { Newspaper } from "lucide-react";

interface CategoryPageProps {
  params: Promise<{ slug: string }>;
}

export default function CategoryPage({ params }: CategoryPageProps) {
  const { slug } = use(params);
  const [country, setCountry] = useState<string>("");

  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["category-stories", slug, country],
    queryFn: async () => {
      const response = await apiClient.get("/stories", {
        params: {
          category: slug,
          country: country || undefined,
        },
      });
      return response.data;
    },
  });

  const categoryName = slug.charAt(0).toUpperCase() + slug.slice(1);

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 pb-24">
        {/* Heading */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold capitalize">{categoryName} News</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Top AI-clustered stories categorized under {categoryName}.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground font-medium">Region:</span>
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="text-xs bg-muted/60 border border-border/40 rounded-xl px-2.5 py-1.5 focus:outline-hidden focus:ring-1 focus:ring-primary text-foreground"
            >
              <option value="">Global</option>
              <option value="US">United States</option>
              <option value="GB">United Kingdom</option>
              <option value="IN">India</option>
            </select>
          </div>
        </div>

        {/* Stories List */}
        {isLoading ? (
          <div className="feed-list">
            <StoryCardSkeleton />
            <StoryCardSkeleton />
          </div>
        ) : error ? (
          <EmptyState
            title="Failed to load stories"
            description="We encountered an issue connecting to the NewsIQ services."
            actionLabel="Retry"
            onAction={refetch}
          />
        ) : !stories || stories.length === 0 ? (
          <EmptyState
            icon={Newspaper}
            title={`No ${categoryName} stories`}
            description="There are currently no AI-clustered stories for this category."
          />
        ) : (
          <div className="feed-list">
            {stories.map((story, index) => (
              <StoryCard key={story.id} story={story} index={index} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
