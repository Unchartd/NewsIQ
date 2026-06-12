"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { StoryCard } from "@/components/story/story-card";
import { StoryCardSkeleton } from "@/components/skeletons";
import { EmptyState } from "@/components/empty-states";
import { Newspaper, Globe, Compass, Landmark, Cpu, Briefcase, Trophy, HeartPulse, FlaskConical, Clapperboard, CloudSun } from "lucide-react";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import type { Story } from "@/types";

const CATEGORIES = [
  { slug: "all", name: "All Feed", icon: Compass },
  { slug: "politics", name: "Politics", icon: Landmark },
  { slug: "technology", name: "Technology", icon: Cpu },
  { slug: "business", name: "Business", icon: Briefcase },
  { slug: "sports", name: "Sports", icon: Trophy },
  { slug: "health", name: "Health", icon: HeartPulse },
  { slug: "science", name: "Science", icon: FlaskConical },
  { slug: "entertainment", name: "Entertainment", icon: Clapperboard },
  { slug: "weather", name: "Weather", icon: CloudSun },
  { slug: "world", name: "World", icon: Globe },
];

export function HomeContent() {
  const [category, setCategory] = useState<string>("all");
  const [country, setCountry] = useState<string>("");

  // Query stories
  const { data: stories, isLoading, error, refetch } = useQuery<Story[]>({
    queryKey: ["stories", category, country],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (category !== "all") {
        params.category = category;
      }
      if (country) {
        params.country = country;
      }
      const response = await apiClient.get("/stories", { params });
      return response.data;
    },
  });

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 py-6 space-y-6 pb-24">
        {/* Header Row */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">Your Feed</h1>
            <p className="text-muted-foreground text-sm mt-1">
              AI-curated stories from trusted global sources.
            </p>
          </div>

          {/* Simple country filter */}
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

        {/* Categories Horizontal Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-2 -mx-4 px-4 no-scrollbar">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isSelected = category === cat.slug;
            return (
              <Button
                key={cat.slug}
                onClick={() => setCategory(cat.slug)}
                variant={isSelected ? "default" : "outline"}
                size="sm"
                className={`rounded-full shrink-0 flex items-center gap-1.5 text-xs px-3 h-8 ${
                  isSelected
                    ? "bg-primary text-primary-foreground border-transparent font-medium"
                    : "border-border/50 hover:bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {cat.name}
              </Button>
            );
          })}
        </div>

        {/* Feed Content */}
        {isLoading ? (
          <div className="space-y-4">
            <StoryCardSkeleton />
            <StoryCardSkeleton />
            <StoryCardSkeleton />
          </div>
        ) : error ? (
          <EmptyState
            title="Failed to load stories"
            description="We encountered an issue connecting to the NewsIQ services. Please try again."
            actionLabel="Retry"
            onAction={refetch}
          />
        ) : !stories || stories.length === 0 ? (
          <EmptyState
            icon={Newspaper}
            title="No stories found"
            description={
              category !== "all" || country
                ? "No stories matched the selected filters. Try changing filters or ingestion."
                : "No news stories have been clustered yet. Populate the database via the manual ingestion trigger."
            }
            actionLabel={category !== "all" || country ? "Clear Filters" : "Trigger News Ingestion"}
            onAction={
              category !== "all" || country
                ? () => {
                    setCategory("all");
                    setCountry("");
                  }
                : async () => {
                    try {
                      await apiClient.post("/sources/trigger-ingestion");
                      alert("News ingestion triggered! Give it 30s to parse and cluster, then refresh.");
                      refetch();
                    } catch (err) {
                      alert("Sign in to trigger ingestion.");
                    }
                  }
            }
          />
        ) : (
          <div className="space-y-4">
            {stories.map((story, index) => (
              <StoryCard key={story.id} story={story} index={index} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
