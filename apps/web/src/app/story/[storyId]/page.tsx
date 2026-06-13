"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  Share2,
  ChevronLeft,
  ExternalLink,
  MapPin,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { AppShell } from "@/components/layout/app-shell";
import { CategoryBadge } from "@/components/ui/category-badge";
import { SourceDots } from "@/components/ui/source-dots";
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { StoryDetail } from "@/types";

interface PageProps {
  params: Promise<{ storyId: string }>;
}

export default function StoryDetailPage({ params }: PageProps) {
  const { storyId } = use(params);
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const [summaryType, setSummaryType] = useState<"one_line" | "short" | "detailed">("short");

  const { data: story, isLoading, error } = useQuery<StoryDetail>({
    queryKey: ["story-detail", storyId],
    queryFn: async () => {
      const response = await apiClient.get(`/stories/${storyId}`);
      return response.data;
    },
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: bookmarkedStories } = useQuery<any[]>({
    queryKey: ["bookmarked-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories/bookmarks");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const isBookmarked = bookmarkedStories?.some((s: any) => s.id === storyId) || false;

  const bookmarkMutation = useMutation({
    mutationFn: async () => {
      if (isBookmarked) {
        await apiClient.delete(`/stories/${storyId}/bookmark`);
      } else {
        await apiClient.post(`/stories/${storyId}/bookmark`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bookmarked-stories"] });
      toast.success(isBookmarked ? "Bookmark removed." : "Story saved.");
    },
    onError: () => {
      toast.error("Failed to update bookmark.");
    },
  });

  const handleShare = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      toast.success("Link copied to clipboard!");
    }
  };

  if (isLoading) {
    return (
      <AppShell>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>
          <div style={{ height: 12, width: 100, borderRadius: 6, background: "var(--border)", marginBottom: 20 }} />
          <div style={{ height: 36, width: "70%", borderRadius: 8, background: "var(--border)", marginBottom: 16 }} />
          <div style={{ height: 120, borderRadius: 10, background: "var(--border)", marginBottom: 24 }} />
          <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 24 }}>
            <div style={{ height: 300, borderRadius: 10, background: "var(--border)" }} />
            <div style={{ height: 300, borderRadius: 10, background: "var(--border)" }} />
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !story) {
    return (
      <AppShell>
        <div className="niq-empty-state">
          <div className="niq-empty-title">Story Not Found</div>
          <div className="niq-empty-desc">The story you are looking for does not exist or may have been removed.</div>
          <Link href="/home"><button className="niq-btn-primary">Go Back Home</button></Link>
        </div>
      </AppShell>
    );
  }

  const activeSummary =
    summaryType === "one_line"
      ? story.one_line_summary
      : summaryType === "detailed"
        ? story.detailed_summary
        : story.short_summary;

  const locationLabel = story.location_city || story.location_state || story.location_country;

  return (
    <AppShell>
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 24px 64px" }}>
        {/* Back */}
        <Link href="/home" style={{ fontSize: 13, color: "var(--ink-3)", display: "inline-flex", alignItems: "center", gap: 4, marginBottom: 24, textDecoration: "none" }}>
          <ChevronLeft size={14} /> Back to feed
        </Link>

        {/* Story Header */}
        <div style={{ marginBottom: 28 }}>
          <div className="niq-card-meta" style={{ marginBottom: 12 }}>
            {story.category && <CategoryBadge category={story.category.name} />}
            {locationLabel && (
              <>
                <span className="niq-meta-dot" />
                <span className="niq-meta-loc"><MapPin size={11} />{locationLabel}</span>
              </>
            )}
            <span className="niq-meta-time">
              First seen {new Date(story.first_seen_at).toLocaleDateString()} · Updated {new Date(story.updated_at).toLocaleString()}
            </span>
          </div>

          <h1 style={{
            fontFamily: "var(--font-newsreader), Georgia, serif",
            fontSize: 32, fontWeight: 600, lineHeight: 1.2, marginBottom: 12,
          }}>
            {story.headline}
          </h1>

          <div style={{ display: "flex", alignItems: "center", gap: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)" }}>
            <SourceDots count={story.source_count} />
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--ink-3)", background: "rgba(29,78,216,0.08)", padding: "2px 8px", borderRadius: 99 }}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.27 5.82 21 7 14.14 2 9.27l6.91-1.01z"/></svg>
              AI generated
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button
                className="niq-btn-outline"
                style={{ padding: "5px 12px", fontSize: 12, gap: 4 }}
                onClick={() => {
                  if (!isAuthenticated) { toast.error("Please sign in to bookmark."); return; }
                  bookmarkMutation.mutate();
                }}
              >
                <Bookmark size={14} className={isBookmarked ? "fill-current" : ""} />
                {isBookmarked ? "Saved" : "Save"}
              </button>
              <button className="niq-btn-outline" style={{ padding: "5px 12px", fontSize: 12, gap: 4 }} onClick={handleShare}>
                <Share2 size={14} /> Share
              </button>
            </div>
          </div>
        </div>

        {/* Summary Switcher */}
        <div className="niq-section-label">AI Summary</div>
        <div className="niq-summary-switcher">
          {(["one_line", "short", "detailed"] as const).map((key) => (
            <button
              key={key}
              className={`niq-switch-btn ${summaryType === key ? "active" : ""}`}
              onClick={() => setSummaryType(key)}
            >
              {key === "one_line" ? "1-line" : key === "short" ? "Short" : "Detailed"}
            </button>
          ))}
        </div>
        <div className="niq-summary-block" key={summaryType}>
          {activeSummary}
        </div>

        {/* Key Facts */}
        {story.entities && story.entities.length > 0 && (
          <>
            <div className="niq-section-label">Key Facts</div>
            <div className="niq-facts-grid">
              {story.entities.slice(0, 6).map((fact, i) => (
                <div key={fact.id || i} className="niq-fact-chip">
                  <div className="niq-fact-label">{fact.entity_type}</div>
                  <div className="niq-fact-value">{fact.entity_value}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Timeline */}
        {story.timeline && story.timeline.length > 0 && (
          <>
            <div className="niq-section-label">Timeline</div>
            <div className="niq-timeline">
              {story.timeline.map((ev, i) => (
                <div key={ev.id || i} className="niq-timeline-item">
                  <div className="niq-timeline-rail">
                    <div className={`niq-timeline-dot ${i === 0 ? "latest" : ""}`} />
                    <div className="niq-timeline-line" />
                  </div>
                  <div className="niq-timeline-body">
                    <div className="niq-timeline-event">{ev.description}</div>
                    <div className="niq-timeline-source">
                      {new Date(ev.event_time).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Source Coverage Table */}
        {story.source_coverage && story.source_coverage.length > 0 && (
          <>
            <div className="niq-section-label">Source Coverage</div>
            <table className="niq-coverage-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Focus Area</th>
                  <th>Published</th>
                  <th>Link</th>
                </tr>
              </thead>
              <tbody>
                {story.source_coverage.map((cov) => (
                  <tr key={cov.id}>
                    <td>
                      <span className="niq-src-name">
                        <div className="niq-source-dot" style={{ background: "#1D4ED8", width: 7, height: 7, borderRadius: "50%" }} />
                        {cov.source?.name}
                      </span>
                    </td>
                    <td className="niq-src-focus">{cov.focus_area}</td>
                    <td className="niq-src-time">{new Date(cov.published_at).toLocaleDateString()}</td>
                    <td>
                      <span className="niq-src-link">
                        Read <ExternalLink size={11} />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {/* Difference Engine */}
        {story.differences && story.differences.length > 0 && (
          <>
            <div className="niq-section-label" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              Difference Engine
              <AlertTriangle size={14} style={{ color: "var(--warning)" }} />
            </div>
            <table className="niq-diff-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Unique Info</th>
                  <th>Missing</th>
                  <th>Contradictions</th>
                </tr>
              </thead>
              <tbody>
                {story.differences.map((diff) => (
                  <tr key={diff.id} className={diff.contradictions ? "niq-diff-row-conflict" : ""}>
                    <td style={{ fontWeight: 500 }}>{diff.source?.name}</td>
                    <td>{diff.unique_information || <span className="niq-missing-val">—</span>}</td>
                    <td>{diff.missing_information || <span className="niq-missing-val">—</span>}</td>
                    <td>
                      {diff.contradictions ? (
                        <span className="niq-conflict-icon">
                          <AlertTriangle size={12} />
                          {diff.contradictions}
                        </span>
                      ) : (
                        <span className="niq-missing-val">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {/* Original Articles */}
        {story.articles && story.articles.length > 0 && (
          <>
            <div className="niq-section-label" style={{ marginTop: 32 }}>Original Articles</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {story.articles.map((art) => (
                <a
                  key={art.id}
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="niq-bk-card"
                >
                  <div className="niq-bk-body">
                    <div style={{ fontSize: 11, fontWeight: 600, color: "var(--primary)", marginBottom: 3 }}>
                      {art.source?.name}
                      {art.author && <span style={{ color: "var(--ink-3)", fontWeight: 400, marginLeft: 8 }}>By {art.author}</span>}
                    </div>
                    <div className="niq-bk-headline">{art.title}</div>
                  </div>
                  <ExternalLink size={14} style={{ color: "var(--ink-3)", flexShrink: 0, marginTop: 4 }} />
                </a>
              ))}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
