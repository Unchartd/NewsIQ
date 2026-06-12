"use client";

import { motion } from "framer-motion";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { 
  Sparkles, 
  ArrowRight, 
  Layers, 
  Scale, 
  Database,
  TrendingUp
} from "lucide-react";

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore();

  const features = [
    {
      icon: <Layers className="w-5 h-5 text-blue-500" />,
      title: "Story Clustering",
      description: "HDBSCAN + vector similarity groups articles from multiple publishers into a single, cohesive story.",
    },
    {
      icon: <Sparkles className="w-5 h-5 text-purple-500" />,
      title: "3-Level AI Summaries",
      description: "Read a story in 1-line, a short paragraph, or a detailed breakdown depending on your time.",
    },
    {
      icon: <Scale className="w-5 h-5 text-amber-500" />,
      title: "Angle Comparison",
      description: "Spot coverage differences, missing facts, and subtle contradictions across publishers instantly.",
    },
    {
      icon: <Database className="w-5 h-5 text-emerald-500" />,
      title: "Fact & Entity Extraction",
      description: "Extract verified key entities (Persons, Organizations, Locations) directly from the text using spaCy NER.",
    },
  ];

  const sampleStories = [
    {
      category: "Technology",
      title: "Tech Giants Announce Unified AI Safety Protocol",
      summary: "Leading technology firms have agreed to a standardized framework for open-source AI deployment and security auditing.",
      sources: 12,
      trend: "+148%",
    },
    {
      category: "Finance",
      title: "Federal Reserve Holds Rates Steady Amid Mild Inflation",
      summary: "The central bank opted to maintain current interest rates, citing a stabilizing job market and gradual return to target inflation levels.",
      sources: 8,
      trend: "+92%",
    },
    {
      category: "Science",
      title: "Deep Space Telescope Detects Water Vapor on Nearby Exoplanet",
      summary: "Astronomers have confirmed the presence of atmospheric water vapor on a rocky exoplanet orbiting within its star's habitable zone.",
      sources: 15,
      trend: "+210%",
    },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans selection:bg-primary/20">
      {/* Header */}
      <header className="border-b border-border/40 backdrop-blur-md bg-background/80 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center text-primary-foreground font-bold shadow-md shadow-primary/20">
              IQ
            </div>
            <span className="font-extrabold tracking-tight text-lg">NewsIQ</span>
          </div>

          <div className="flex items-center gap-4">
            {isAuthenticated ? (
              <Button render={<a href="/home" />} nativeButton={false} variant="default" className="rounded-xl px-4 text-xs font-semibold">
                Go to Feed
              </Button>
            ) : (
              <>
                <Button render={<a href="/login" />} nativeButton={false} variant="ghost" className="rounded-xl px-4 text-xs font-semibold">
                  Sign In
                </Button>
                <Button render={<a href="/signup" />} nativeButton={false} variant="default" className="rounded-xl px-4 text-xs font-semibold">
                  Get Started
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-20 pb-16 md:pt-32 md:pb-24 border-b border-border/30">
        {/* Glow Effects */}
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-primary/10 rounded-full blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-500/10 rounded-full blur-[120px] pointer-events-none" />

        <div className="max-w-4xl mx-auto px-6 text-center space-y-6">
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-1.5 bg-primary/10 border border-primary/20 px-3 py-1 rounded-full text-primary text-xs font-semibold"
          >
            <Sparkles className="w-3.5 h-3.5" />
            AI-Powered News Aggregation
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="text-4xl md:text-6xl font-extrabold tracking-tight leading-tight md:leading-none text-balance"
          >
            Understand any major story in{" "}
            <span className="bg-gradient-to-r from-primary via-indigo-500 to-purple-600 bg-clip-text text-transparent">
              30 seconds
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="text-muted-foreground text-base md:text-lg max-w-xl mx-auto leading-relaxed"
          >
            Get neutral, multi-perspective AI summaries compiled from dozens of publishers. Stop reading duplicates, start comparing angles with absolute source transparency.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4"
          >
            <Button
              render={<a href={isAuthenticated ? "/home" : "/signup"} />}
              nativeButton={false}
              size="lg"
              className="rounded-xl w-full sm:w-auto px-6 font-semibold flex items-center gap-2 group shadow-lg shadow-primary/20"
            >
              {isAuthenticated ? "Go to Dashboard" : "Get Started Free"}
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Button>
            <Button
              render={<a href="#features" />}
              nativeButton={false}
              size="lg"
              variant="outline"
              className="rounded-xl w-full sm:w-auto px-6 font-semibold"
            >
              See How It Works
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Interactive Feature Cards */}
      <section id="features" className="py-20 max-w-6xl mx-auto px-6 space-y-12 scroll-mt-16">
        <div className="text-center space-y-2">
          <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight">Core Capabilities</h2>
          <p className="text-muted-foreground text-xs md:text-sm max-w-md mx-auto">
            Engineered to process global information feeds, extract intelligence, and present it without bias.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feat, index) => (
            <motion.div
              key={feat.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: index * 0.1 }}
            >
              <Card className="border-border/50 hover:border-border rounded-2xl h-full transition-all hover:shadow-md bg-card/40 backdrop-blur-sm">
                <CardContent className="p-6 space-y-4">
                  <div className="w-10 h-10 rounded-xl bg-secondary/50 flex items-center justify-center border border-border/40">
                    {feat.icon}
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-bold text-sm">{feat.title}</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed">{feat.description}</p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Demo Section / Live Preview */}
      <section className="py-20 bg-secondary/10 border-t border-b border-border/20 relative">
        <div className="max-w-6xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-5 space-y-6">
            <div className="inline-flex items-center gap-1.5 bg-violet-500/10 border border-violet-500/20 px-3 py-1 rounded-full text-violet-500 text-xs font-semibold">
              <TrendingUp className="w-3.5 h-3.5" />
              Intelligence Dashboard
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight">Compare Publisher Coverages</h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              We extract matching claims and omissions automatically. See what key facts are highlighted by specific publishers, and verify differing timelines side-by-side.
            </p>
            <div className="space-y-3 pt-2">
              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0 mt-0.5">
                  ✓
                </div>
                <p className="text-xs text-muted-foreground">Identify key contradictions instantly.</p>
              </div>
              <div className="flex items-start gap-2.5">
                <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0 mt-0.5">
                  ✓
                </div>
                <p className="text-xs text-muted-foreground">Trace news back to exact origin sources.</p>
              </div>
            </div>
            <Button render={<a href={isAuthenticated ? "/home" : "/signup"} />} nativeButton={false} className="rounded-xl px-5 mt-4">
              Explore Dashboard
            </Button>
          </div>

          <div className="lg:col-span-7">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              className="p-6 border border-border/50 rounded-3xl bg-card shadow-xl space-y-6 relative overflow-hidden"
            >
              {/* Header inside Mockup */}
              <div className="flex items-center justify-between border-b border-border/40 pb-4">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px] text-primary bg-primary/5">
                    Live Story Cluster
                  </Badge>
                  <span className="text-[10px] text-muted-foreground font-medium">Updated 2m ago</span>
                </div>
                <div className="flex gap-1">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-yellow-500/60" />
                  <div className="w-2.5 h-2.5 rounded-full bg-green-500/60" />
                </div>
              </div>

              {/* Summary Selector Mockup */}
              <div className="space-y-4">
                <div className="flex gap-1.5 border-b border-border/30 pb-2">
                  <span className="text-[10px] font-bold text-primary border-b border-primary pb-2 px-1">One-Line</span>
                  <span className="text-[10px] text-muted-foreground font-semibold px-1">Short</span>
                  <span className="text-[10px] text-muted-foreground font-semibold px-1">Detailed</span>
                </div>
                <p className="text-sm font-bold text-foreground leading-snug">
                  "Leading space tech firms launch record-setting payload and confirm recovery parameters."
                </p>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Multiple aerospace sources reported the successful deployment of a next-generation orbital module. The launch marks a milestone in collaborative recovery protocols and safety standards.
                </p>
              </div>

              {/* Source comparison mockup */}
              <div className="space-y-3 pt-2">
                <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Publisher Differences</p>
                <div className="space-y-2">
                  <div className="p-3 rounded-xl border border-border/40 bg-secondary/10 flex justify-between items-center text-xs">
                    <span className="font-semibold text-foreground">Reuters</span>
                    <span className="text-emerald-500 text-[10px] font-medium">Focus on engineering scale</span>
                  </div>
                  <div className="p-3 rounded-xl border border-border/40 bg-secondary/10 flex justify-between items-center text-xs">
                    <span className="font-semibold text-foreground">BBC News</span>
                    <span className="text-emerald-500 text-[10px] font-medium">Emphasis on regulatory approval</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Trending Stories Grid */}
      <section className="py-20 max-w-6xl mx-auto px-6 space-y-12">
        <div className="text-center space-y-2">
          <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight">Trending Story Previews</h2>
          <p className="text-muted-foreground text-xs md:text-sm max-w-md mx-auto">
            These major story pipelines are currently active in our vector analysis database.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {sampleStories.map((story) => (
            <Card key={story.title} className="border-border/50 rounded-2xl flex flex-col justify-between hover:shadow-md hover:border-border transition-all">
              <CardContent className="p-6 space-y-4 flex-1 flex flex-col justify-between">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Badge variant="secondary" className="text-[9px] uppercase tracking-wider font-semibold rounded-lg px-2 py-0.5">
                      {story.category}
                    </Badge>
                    <span className="text-[10px] text-purple-500 font-bold flex items-center gap-0.5">
                      {story.trend} trending
                    </span>
                  </div>
                  <h3 className="font-bold text-sm leading-snug hover:text-primary transition-colors cursor-pointer">
                    {story.title}
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {story.summary}
                  </p>
                </div>
                
                <div className="pt-4 border-t border-border/40 flex items-center justify-between text-[10px] text-muted-foreground">
                  <span>{story.sources} active sources</span>
                  <span className="font-semibold text-primary flex items-center gap-0.5 cursor-pointer">
                    Analyze <ArrowRight className="w-3 h-3" />
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 border-t border-border/30 relative overflow-hidden bg-primary/5">
        <div className="max-w-3xl mx-auto px-6 text-center space-y-6">
          <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight">Stay Ahead of the Information Cycle</h2>
          <p className="text-muted-foreground text-sm max-w-md mx-auto leading-relaxed">
            Create an account, customize your onboard dashboard categories, and receive multi-channel intelligence updates in real time.
          </p>
          <Button
            render={<a href={isAuthenticated ? "/home" : "/signup"} />}
            nativeButton={false}
            size="lg"
            className="rounded-xl px-8 font-semibold shadow-lg shadow-primary/20"
          >
            {isAuthenticated ? "Enter Dashboard" : "Join NewsIQ Now"}
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border/30 bg-card py-12 mt-auto">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-primary flex items-center justify-center text-primary-foreground font-bold">
              IQ
            </div>
            <span className="font-bold text-foreground">NewsIQ</span>
            <span>© {new Date().getFullYear()} NewsIQ Inc. All rights reserved.</span>
          </div>

          <div className="flex gap-6">
            <a href="#" className="hover:text-foreground transition-colors">Privacy Policy</a>
            <a href="#" className="hover:text-foreground transition-colors">Terms of Service</a>
            <a href="#" className="hover:text-foreground transition-colors">Contact Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

