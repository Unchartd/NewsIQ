"use client";

import { motion } from "framer-motion";
import { TrendingUp, Newspaper, CloudSun, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

// Mock data for right sidebar components
const trendingTopics = [
  { topic: "Generative AI", count: "12 stories", category: "technology" },
  { topic: "Federal Reserve", count: "8 stories", category: "business" },
  { topic: "Global Warming", count: "6 stories", category: "science" },
  { topic: "Championship Finals", count: "5 stories", category: "sports" },
];

const popularSources = [
  { name: "Reuters", rating: "94% neutrality", slug: "reuters" },
  { name: "BBC News", rating: "91% neutrality", slug: "bbc-news" },
  { name: "Bloomberg", rating: "89% neutrality", slug: "bloomberg" },
];

const latestUpdates = [
  { title: "Tech giants sign new AI safety accord", time: "10m ago" },
  { title: "Market futures drop ahead of inflation report", time: "24m ago" },
  { title: "Historic space mission successfully launches", time: "1h ago" },
];

export function RightPanel() {
  return (
    <aside className="hidden xl:flex flex-col w-[320px] h-[calc(100vh-4rem)] sticky top-16 border-l border-border/60 bg-background py-4 px-4 overflow-y-auto space-y-6 flex-shrink-0">
      {/* Weather Widget */}
      <Card className="border-border/50 bg-secondary/30 overflow-hidden rounded-2xl">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground font-medium">San Francisco, CA</p>
            <h3 className="text-2xl font-bold tracking-tight">68°F</h3>
            <p className="text-xs text-muted-foreground capitalize">Partly Cloudy</p>
          </div>
          <CloudSun className="w-12 h-12 text-amber-500 animate-pulse" />
        </CardContent>
      </Card>

      {/* Trending Topics */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-primary" />
            Trending Topics
          </h4>
        </div>
        <div className="space-y-2">
          {trendingTopics.map((topic, i) => (
            <motion.div
              key={topic.topic}
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-center justify-between p-2 rounded-xl hover:bg-muted/50 transition-colors cursor-pointer group"
            >
              <div>
                <p className="text-sm font-medium group-hover:text-primary transition-colors">#{topic.topic}</p>
                <p className="text-[11px] text-muted-foreground">{topic.count}</p>
              </div>
              <Badge variant="secondary" className="text-[10px] capitalize px-2 py-0.5 rounded-full">
                {topic.category}
              </Badge>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Popular Sources */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/75 flex items-center gap-1.5">
          <Newspaper className="w-3.5 h-3.5 text-primary" />
          Trusted Sources
        </h4>
        <div className="space-y-2">
          {popularSources.map((source, i) => (
            <div
              key={source.name}
              className="flex items-center justify-between p-2 rounded-xl hover:bg-muted/50 transition-colors cursor-pointer"
            >
              <div>
                <p className="text-sm font-medium">{source.name}</p>
                <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                  {source.rating}
                </p>
              </div>
              <ArrowRight className="w-3.5 h-3.5 text-muted-foreground/50" />
            </div>
          ))}
        </div>
      </div>

      {/* Latest Updates */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/75">
          Latest Updates
        </h4>
        <div className="space-y-3 pl-1.5 border-l-2 border-border/80">
          {latestUpdates.map((update, i) => (
            <div key={update.title} className="space-y-1 relative">
              <div className="absolute -left-[11px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-background bg-primary" />
              <p className="text-xs font-medium leading-relaxed hover:text-primary transition-colors cursor-pointer">
                {update.title}
              </p>
              <p className="text-[10px] text-muted-foreground">{update.time}</p>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
