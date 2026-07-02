"use client";

import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Calendar, BookOpen, Clock, ArrowRight, BookMarked } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { motion } from "framer-motion";
import Link from "next/link";
import { getStoryRoute } from "@/lib/metadata";

interface DigestItem {
  story_id: string;
  headline: string;
  one_line_summary: string;
  short_summary: string;
  category_id: string | null;
  created_at: string;
}

interface LatestDigest {
  digest_type: string;
  generated_at: string;
  title: string;
  items: DigestItem[];
}

export default function DigestPage() {
  const { isAuthenticated } = useAuthStore();

  const { data: digest, isLoading } = useQuery<LatestDigest>({
    queryKey: ["latest-digest"],
    queryFn: async () => {
      const response = await apiClient.get("/users/digests/latest");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto py-16 text-center">
          <BookMarked className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-bold text-foreground">Premium Intelligence Briefing</h2>
          <p className="text-muted-foreground text-sm mt-1 mb-6">
            Sign in to access your morning, evening, and weekly personalized news digests.
          </p>
          <Button render={<Link href="/login" />} nativeButton={false} className="rounded-xl">
            Sign In
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-8 pb-24">
        {/* Header Briefing Header */}
        <div className="text-center md:text-left md:flex md:items-end md:justify-between border-b border-border/40 pb-6">
          <div className="space-y-2">
            <div className="flex items-center justify-center md:justify-start gap-1 text-violet-500 font-semibold text-xs tracking-wider uppercase">
              <Sparkles className="w-3.5 h-3.5" />
              AI Intelligence
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight">Your Daily Briefing</h1>
            <p className="text-xs text-muted-foreground">
              Synthesized from active global publishers based on your categories of interest.
            </p>
          </div>

          <div className="mt-4 md:mt-0 flex items-center justify-center gap-1.5 text-xs text-muted-foreground font-medium bg-secondary/30 px-3 py-1.5 rounded-full border border-border/30 w-fit mx-auto md:mx-0">
            <Calendar className="w-3.5 h-3.5" />
            {digest?.generated_at ? new Date(digest.generated_at).toLocaleDateString(undefined, {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            }) : 'Today'}
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="border-border/40 rounded-2xl animate-pulse">
                <div className="h-40 bg-muted/40 rounded-2xl" />
              </Card>
            ))}
          </div>
        ) : !digest || !digest.items || digest.items.length === 0 ? (
          <div className="text-center py-12 space-y-4">
            <BookOpen className="w-12 h-12 text-muted-foreground/30 mx-auto" />
            <h3 className="text-lg font-semibold text-foreground">No Briefing Available</h3>
            <p className="text-xs text-muted-foreground max-w-sm mx-auto">
              We couldn&apos;t compile a briefing right now. Ensure you have selected preferred categories in settings and check back in a few minutes.
            </p>
            <Button render={<Link href="/settings" />} nativeButton={false} variant="outline" className="rounded-xl">
              Manage Settings
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            {digest.items.map((item, index) => (
              <motion.div
                key={item.story_id}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <Card className="border-border/50 rounded-2xl overflow-hidden hover:shadow-md hover:border-border transition-all bg-card/60 backdrop-blur-sm">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] text-muted-foreground font-bold tracking-wider uppercase flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Story #{index + 1}
                      </span>
                    </div>
                    <CardTitle className="text-lg font-bold leading-tight text-foreground hover:text-primary transition-colors">
                      <Link href={getStoryRoute({ id: item.story_id, headline: item.headline })}>{item.headline}</Link>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4 pb-6">
                    <div className="p-3.5 rounded-xl bg-violet-500/5 border border-violet-500/10 text-xs italic text-foreground/90 font-medium">
                      &ldquo;{item.one_line_summary}&rdquo;
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {item.short_summary}
                    </p>
                    <div className="pt-2 flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        render={<Link href={getStoryRoute({ id: item.story_id, headline: item.headline })} />}
                        nativeButton={false}
                        className="rounded-xl text-xs flex items-center gap-1.5 h-8 text-primary hover:bg-primary/10"
                      >
                        Explore Full Coverage <ArrowRight className="w-3.5 h-3.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
