"use client";

import Link from "next/link";
import { Bell, Crown } from "lucide-react";
import type { Story } from "@/types";

/* ─── Trending Widget ──────────────────────────── */
interface TrendingWidgetProps {
  stories: Story[];
}

export function TrendingWidget({ stories }: TrendingWidgetProps) {
  return (
    <div className="widget">
      <div className="slbl">Trending Now</div>
      {stories.slice(0, 4).map((story, i) => (
        <Link key={story.id} href={`/story/${story.id}`} style={{ textDecoration: "none", color: "inherit" }}>
          <div className="titem">
            <span className="ti-r">{i + 1}</span>
            <div>
              <div className="ti-h">{story.headline}</div>
              <div className="ti-m">
                {story.source_count} sources · {formatTimeAgo(story.updated_at)}
              </div>
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

/* ─── Top Sources Widget ──────────────────────── */
const SAMPLE_SOURCES = [
  { name: "NDTV", color: "#DC2626" },
  { name: "The Hindu", color: "#1D4ED8" },
  { name: "TOI", color: "#D97706" },
  { name: "Reuters", color: "#16A34A" },
  { name: "Bloomberg", color: "#7C3AED" },
  { name: "BBC", color: "#0E7490" },
];

export function TopSourcesWidget() {
  return (
    <div className="widget">
      <div className="slbl">Top Sources</div>
      <div style={{ display: "flex", flexWrap: "wrap" }}>
        {SAMPLE_SOURCES.map((src) => (
          <div key={src.name} className="spill">
            <div className="sdsm" style={{ background: src.color }} />
            {src.name}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Digest CTA Widget ──────────────────────── */
export function DigestWidget() {
  return (
    <div className="widget">
      <div className="dwidget">
        <div className="dw-t">Morning Digest</div>
        <div className="dw-s">Top 10 stories. 3-minute read. Every day at 7 AM.</div>
        <Link href="/digest">
          <button className="btnp">
            <Bell size={14} />
            Subscribe free
          </button>
        </Link>
      </div>
    </div>
  );
}

/* ─── Premium Upsell Widget ──────────────────── */
export function PremiumUpsellWidget() {
  return (
    <div className="widget">
      <div className="pcrd" style={{ background: "var(--surface)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <Crown size={16} style={{ color: "var(--primary)" }} />
          <span style={{
            fontSize: 12, fontWeight: 700, letterSpacing: "0.06em",
            color: "var(--primary)", textTransform: "uppercase" as const,
          }}>
            NewsIQ Pro
          </span>
        </div>
        <div style={{
          fontSize: 14, color: "var(--ink2)", lineHeight: 1.6, marginBottom: 12,
        }}>
          Unlock source comparison, AI chat, and personalised feed. ₹399/month.
        </div>
        <Link href="/premium">
          <button className="btno" style={{ width: "100%", justifyContent: "center" }}>
            See what&apos;s included
          </button>
        </Link>
      </div>
    </div>
  );
}

/* ─── Trending Skeleton ────────────────────────── */
export function TrendingWidgetSkeleton() {
  return (
    <div className="widget" style={{ pointerEvents: "none" }}>
      <div className="slbl">Trending Now</div>
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="titem" style={{ borderBottom: i === 3 ? "none" : undefined }}>
          <span className="ti-r">{i + 1}</span>
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 6 }}>
            {/* Headline skeleton (2 lines) */}
            <div className="sk-bar" style={{ width: "100%", height: 13, borderRadius: 4 }} />
            <div className="sk-bar" style={{ width: "65%", height: 13, borderRadius: 4 }} />
            {/* Meta skeleton */}
            <div className="sk-bar" style={{ width: "45%", height: 10, borderRadius: 3, marginTop: 4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Combined Sidebar ────────────────────────── */
interface SidebarWidgetsProps {
  trendingStories?: Story[];
  isLoading?: boolean;
}

export function SidebarWidgets({ trendingStories = [], isLoading = false }: SidebarWidgetsProps) {
  return (
    <div className="sticky-p">
      {isLoading ? (
        <TrendingWidgetSkeleton />
      ) : (
        trendingStories.length > 0 && <TrendingWidget stories={trendingStories} />
      )}
      <TopSourcesWidget />
      <DigestWidget />
      <PremiumUpsellWidget />
    </div>
  );
}

/* ─── Helper ──────────────────────────────────── */
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
