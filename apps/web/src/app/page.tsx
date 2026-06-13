"use client";

import Link from "next/link";
import { Navbar } from "@/components/layout/navbar";
import { SignalBar } from "@/components/layout/signal-bar";
import { CategoryBadge } from "@/components/ui/category-badge";
import { Home } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

const PREVIEW_CARDS = [
  {
    category: "Technology",
    headline: "OpenAI releases new reasoning model with 40% improvement in benchmark performance",
    sources: 12,
    trending: true,
    time: "43 min ago",
  },
  {
    category: "Business",
    headline: "RBI holds repo rate steady at 6.5% amid global inflation uncertainty",
    sources: 8,
    location: "Mumbai",
    time: "1h ago",
  },
  {
    category: "Weather",
    headline: "Heavy monsoon rains disrupt transport across Bengaluru; schools closed",
    sources: 6,
    location: "Bengaluru",
    time: "2h ago",
  },
];

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <SignalBar />

      {/* Hero */}
      <div className="lhero">
        <div className="lh-l">
          <div className="ley">
            <div className="lpulse" />
            Live intelligence · 1,240 stories indexed today
          </div>
          <h1 className="ltitle">
            Every story,<br />
            <em>understood</em><br />
            in 30 seconds.
          </h1>
          <p className="ldesc">
            NewsIQ clusters thousands of articles into single, clear stories — with AI summaries,
            source comparisons, and timelines. Stop reading. Start understanding.
          </p>
          <div className="lbtns">
            <Link href={isAuthenticated ? "/home" : "/signup"}>
              <button className="btnp" style={{ padding: "11px 24px", fontSize: 15 }}>
                <Home size={16} />
                Start reading free
              </button>
            </Link>
            <Link href="/premium">
              <button className="btno" style={{ padding: "11px 24px", fontSize: 15 }}>
                See plans
              </button>
            </Link>
          </div>
          <div className="lstats">
            <div>
              <div className="lsn">10k+</div>
              <div className="lsl">Sources indexed</div>
            </div>
            <div>
              <div className="lsn">98%</div>
              <div className="lsl">Cluster accuracy</div>
            </div>
            <div>
              <div className="lsn">&lt;5 min</div>
              <div className="lsl">Story freshness</div>
            </div>
          </div>
        </div>

        {/* Preview Cards */}
        <div className="lh-r">
          {PREVIEW_CARDS.map((card, i) => (
            <div key={i} className="hprev">
              <CategoryBadge category={card.category} />
              <div className="hph">{card.headline}</div>
              <div className="hpf">
                <span>{card.sources} sources</span>
                {card.trending && <span>↑ Trending</span>}
                {card.location && <span>{card.location}</span>}
                <span>{card.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Value proposition strip */}
      <div style={{ maxWidth: 1280, margin: "0 auto", padding: "0 24px" }}>
        <div style={{
          borderTop: "1px solid var(--border)",
          padding: "48px 0",
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 40,
        }}>
          {[
            {
              label: "AI Clustering",
              title: "One story from dozens of articles",
              desc: "Articles covering the same event are grouped and synthesized — eliminating redundancy, preserving nuance.",
            },
            {
              label: "Source Transparency",
              title: "See exactly what each outlet emphasised",
              desc: "The Source Coverage table and Difference Engine show you where publishers agree, disagree, and go silent.",
            },
            {
              label: "Neutral Headlines",
              title: "Facts, not clickbait",
              desc: "AI rewrites every headline to be factual and informative. You know what happened before you click.",
            },
          ].map((item) => (
            <div key={item.label}>
              <div style={{
                fontSize: 11, fontWeight: 700, letterSpacing: "0.09em",
                textTransform: "uppercase" as const, color: "var(--primary)", marginBottom: 10,
              }}>
                {item.label}
              </div>
              <div style={{
                fontFamily: "var(--fd)",
                fontSize: 18, fontWeight: 500, marginBottom: 8, color: "var(--ink)",
              }}>
                {item.title}
              </div>
              <div style={{ fontSize: 14, color: "var(--ink3)", lineHeight: 1.7 }}>
                {item.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <footer style={{
        borderTop: "1px solid var(--border)",
        padding: "32px 24px",
        textAlign: "center",
        fontSize: 12,
        color: "var(--ink3)",
      }}>
        © {new Date().getFullYear()} NewsIQ. All rights reserved.
      </footer>
    </div>
  );
}
