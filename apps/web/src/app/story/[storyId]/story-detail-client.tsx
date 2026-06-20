"use client";

import { useState, useEffect } from "react";
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
import apiClient from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";
import type { StoryDetail, StoryEntity } from "@/types";

interface Props {
  storyId: string;
  initialStory: StoryDetail | null;
}

const SOURCE_COLORS = [
  "#1D4ED8", "#DC2626", "#16A34A", "#D97706", "#7C3AED",
  "#0E7490", "#065F46", "#374151", "#6B21A8", "#0369A1",
];

/** Returns a stable short date (no locale, no relative) — safe for SSR. */
function formatDateStable(dateString: string): string {
  try {
    const d = new Date(dateString);
    // ISO slice gives YYYY-MM-DD — locale-independent
    return d.toISOString().slice(0, 10);
  } catch {
    return "";
  }
}

/** Relative time — only call on the client (after mount). */
function formatTimeAgo(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / (1000 * 60));
    const diffHr = Math.floor(diffMin / 60);
    const diffDays = Math.floor(diffHr / 24);

    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

/** Locale-safe HH:MM — only call on client (after mount). */
function formatTime(dateString: string): string {
  try {
    return new Date(dateString).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

/** Locale-safe short date — only call on client (after mount). */
function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString();
  } catch {
    return "";
  }
}

export function StoryDetailClient({ storyId, initialStory }: Props) {
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();
  const [summaryType, setSummaryType] = useState<"one_line" | "short" | "detailed">("short");
  // Guard: relative / locale-dependent time values must only render after hydration
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);
  // Track which entity-type rows the user has expanded
  const [expandedEntityTypes, setExpandedEntityTypes] = useState<Set<string>>(new Set());

  const { data: story, isLoading, error } = useQuery<StoryDetail>({
    queryKey: ["story-detail", storyId],
    queryFn: async () => {
      const response = await apiClient.get(`/stories/${storyId}`);
      return response.data;
    },
    initialData: initialStory ?? undefined,
  });

  const { data: bookmarkedStories } = useQuery<StoryDetail[]>({
    queryKey: ["bookmarked-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories/bookmarks");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const isBookmarked = bookmarkedStories?.some((s) => s.id === storyId) || false;

  // Fire reading history event once when story data is first available
  useEffect(() => {
    if (!story || !isAuthenticated) return;
    apiClient
      .post("/users/events", null, { params: { event_type: "view_story", story_id: storyId } })
      .catch(() => { /* fire-and-forget */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [story?.id]);

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
      if (isAuthenticated) {
        apiClient
          .post("/users/events", null, { params: { event_type: "share_story", story_id: storyId } })
          .catch(() => { /* fire-and-forget */ });
      }
    }
  };

  if (isLoading && !story) {
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
        <div style={{ textAlign: "center", padding: "80px 24px" }}>
          <h2 style={{ fontFamily: "var(--fd)", fontSize: 24, fontWeight: 600, marginBottom: 8 }}>Story Not Found</h2>
          <p style={{ color: "var(--ink3)", marginBottom: 24 }}>The story you are looking for does not exist or may have been removed.</p>
          <Link href="/home"><button className="btnp">Go Back Home</button></Link>
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

  const sidebar = (
    <div className="sticky-p">
      <div className="pcrd">
        <div className="slbl" style={{ marginBottom: 10 }}>Summary depth</div>
        <div className="swit" style={{ width: "100%" }}>
          {(["one_line", "short", "detailed"] as const).map((key) => (
            <button
              key={key}
              className={`switbtn ${summaryType === key ? "on" : ""}`}
              onClick={() => setSummaryType(key)}
              style={{ flex: 1, textAlign: "center" }}
            >
              {key === "one_line" ? "1-line" : key === "short" ? "Short" : "Detailed"}
            </button>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: "var(--ink3)", display: "flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 11 }}>✦</span>Summarised from {story.source_count} sources
        </div>
      </div>

      <div className="pcrd">
        <div className="slbl" style={{ marginBottom: 10 }}>Coverage</div>
        <div style={{ display: "flex", gap: 16, marginBottom: 14 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "var(--fd)", fontSize: 28, fontWeight: 700, color: "var(--ink)", lineHeight: 1 }}>
              {story.source_count}
            </div>
            <div style={{ fontSize: 11, color: "var(--ink3)" }}>Sources</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "var(--fd)", fontSize: 28, fontWeight: 700, color: "var(--amber)", lineHeight: 1 }}>
              {story.differences?.filter((d) => d.contradictions).length ?? 0}
            </div>
            <div style={{ fontSize: 11, color: "var(--ink3)" }}>Conflicts</div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontFamily: "var(--fd)", fontSize: 28, fontWeight: 700, color: "var(--ink3)", lineHeight: 1 }}>
              {story.differences?.filter((d) => d.missing_information).length ?? 0}
            </div>
            <div style={{ fontSize: 11, color: "var(--ink3)" }}>Missing</div>
          </div>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {story.source_coverage?.slice(0, 4).map((cov, i) => (
            <div key={cov.id || i} className="spill" style={{ fontSize: 11, padding: "4px 8px" }}>
              <div className="sdsm" style={{ background: SOURCE_COLORS[i % SOURCE_COLORS.length] }} />
              {cov.source?.name}
            </div>
          ))}
        </div>
      </div>

      {story.related_stories && story.related_stories.length > 0 && (
        <div className="pcrd">
          <div className="slbl" style={{ marginBottom: 10 }}>Related</div>
          <nav aria-label="Related stories" style={{ display: "flex", flexDirection: "column" }}>
            {story.related_stories.slice(0, 3).map((relStory) => (
              <Link key={relStory.id} href={`/story/${relStory.id}`} style={{ textDecoration: "none" }}>
                <div className="titem" style={{ padding: "8px 0" }}>
                  <div>
                    <div className="ti-h" style={{ fontSize: 13 }}>
                      {relStory.headline}
                    </div>
                    <div className="ti-m">
                      {relStory.source_count} sources · {mounted ? formatTimeAgo(relStory.updated_at) : formatDateStable(relStory.updated_at)}
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </nav>
        </div>
      )}
    </div>
  );

  return (
    <AppShell sidebar={sidebar}>
      <div style={{ padding: "0 0 48px 0" }}>
        {/* Breadcrumb List for E-E-A-T and AEO */}
        <nav aria-label="Breadcrumb" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--ink3)", marginBottom: 24, flexWrap: "wrap" }}>
          <Link href="/home" style={{ color: "var(--ink3)", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 4 }}>
            <ChevronLeft size={14} /> Home
          </Link>
          <span>/</span>
          {story.category && (
            <>
              <Link href={`/category/${story.category.slug}`} style={{ color: "var(--ink3)", textDecoration: "none" }}>
                {story.category.name}
              </Link>
              <span>/</span>
            </>
          )}
          <span style={{ color: "var(--ink2)", maxWidth: "240px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {story.headline}
          </span>
        </nav>

        {/* Story Header */}
        <div style={{ marginBottom: 28 }}>
          <div className="sd-meta">
            {story.category && (
              <Link href={`/category/${story.category.slug}`} style={{ textDecoration: "none" }}>
                <CategoryBadge category={story.category.name} />
              </Link>
            )}
            {locationLabel && (
              <>
                <span className="mdot" />
                <span className="mloc"><MapPin size={11} />{locationLabel}</span>
              </>
            )}
            <span className="mdot" />
            <span
              suppressHydrationWarning
              style={{ fontSize: 12, color: "var(--ink3)", display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              {story.updated_at ? (mounted ? formatTimeAgo(story.updated_at) : formatDateStable(story.updated_at)) : ""}
            </span>
          </div>

          <h1 className="sd-head">
            {story.headline}
          </h1>

          <div style={{ display: "flex", alignItems: "center", gap: 16, paddingBottom: 16, borderBottom: "1px solid var(--border)", flexWrap: "wrap" }}>
            <span>{story.source_count} sources</span>
            <span>·</span>
            <div className="ai-lbl">✦ AI Summary</div>
            <span>·</span>
            {(() => {
              const uniqueSources = Array.from(new Set(story.articles?.map((a) => a.source?.name).filter(Boolean) ?? []));
              return (
                <span style={{ fontSize: 12, color: "var(--ink3)" }}>
                  Summarised from {uniqueSources.slice(0, 3).join(", ")}
                  {uniqueSources.length > 3 ? ` +${uniqueSources.length - 3} more` : ""}
                </span>
              );
            })()}
            <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
              <button
                className="btno"
                style={{ padding: "5px 12px", fontSize: 12, gap: 4 }}
                aria-label={isBookmarked ? "Remove bookmark" : "Save story"}
                onClick={() => {
                  if (!isAuthenticated) { toast.error("Please sign in to bookmark."); return; }
                  bookmarkMutation.mutate();
                }}
              >
                <Bookmark size={14} fill={isBookmarked ? "currentColor" : "none"} aria-hidden="true" />
                {isBookmarked ? "Saved" : "Save"}
              </button>
              <button className="btno" style={{ padding: "5px 12px", fontSize: 12, gap: 4 }} aria-label="Share story" onClick={handleShare}>
                <Share2 size={14} aria-hidden="true" /> Share
              </button>
            </div>
          </div>
        </div>

        {/* Summary Switcher (Visible on mobile/tablet because .sc is hidden) */}
        <div className="swit" style={{ marginBottom: 14 }}>
          {(["one_line", "short", "detailed"] as const).map((key) => (
            <button
              key={key}
              className={`switbtn ${summaryType === key ? "on" : ""}`}
              onClick={() => setSummaryType(key)}
            >
              {key === "one_line" ? "1-line" : key === "short" ? "Short" : "Detailed"}
            </button>
          ))}
        </div>
        <div className="sumblock">
          {activeSummary}
        </div>
        <div style={{
          marginTop: 8,
          fontSize: 11,
          color: "var(--ink3)",
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "var(--r6)",
          padding: "8px 12px",
          marginBottom: 24
        }}>
          <AlertTriangle size={12} style={{ color: "var(--amber)", flexShrink: 0 }} />
          <span>
            <strong>AI Transparency:</strong> Summaries are AI-generated and probabilistic. AI may omit facts or contain inaccuracies. Verify using the original links below.
          </span>
        </div>


        {/* Key Facts */}
        {story.key_facts && story.key_facts.length > 0 && (
          <>
            <div className="slbl">Key Facts</div>
            <ul className="kf-list" style={{ listStyleType: "none", padding: 0, margin: "0 0 28px 0" }}>
              {story.key_facts.map((fact, i) => (
                <li
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    marginBottom: 10,
                    fontSize: 14.5,
                    color: "var(--ink2)",
                    lineHeight: 1.55,
                  }}
                >
                  <span style={{ color: "var(--primary)", fontWeight: "bold", fontSize: 16, lineHeight: 1.2 }}>•</span>
                  <span>{fact}</span>
                </li>
              ))}
            </ul>
          </>
        )}

        {/* Key Entities — grouped by type */}
        {story.entities && story.entities.length > 0 && (() => {
          // 1. Group & deduplicate, preserving first-seen order
          const MAX_VISIBLE = 5;
          const TYPE_ORDER: StoryEntity["entity_type"][] = ["LOCATION", "COUNTRY", "PERSON", "ORG", "EVENT"];
          const grouped = new Map<string, string[]>();
          for (const e of story.entities) {
            const type = e.entity_type ?? "OTHER";
            if (!grouped.has(type)) grouped.set(type, []);
            const existing = grouped.get(type)!;
            if (!existing.some(v => v.toLowerCase() === e.entity_value.toLowerCase())) {
              existing.push(e.entity_value);
            }
          }
          // 2. Sort groups by TYPE_ORDER, then alphabetically for remainder
          const sortedGroups = [...grouped.entries()].sort(([a], [b]) => {
            const ai = TYPE_ORDER.indexOf(a as StoryEntity["entity_type"]);
            const bi = TYPE_ORDER.indexOf(b as StoryEntity["entity_type"]);
            if (ai === -1 && bi === -1) return a.localeCompare(b);
            if (ai === -1) return 1;
            if (bi === -1) return -1;
            return ai - bi;
          });

          return (
            <>
              <div className="slbl">Key Entities</div>
              <div className="eg-section">
                {sortedGroups.map(([type, values]) => {
                  const isExpanded = expandedEntityTypes.has(type);
                  const visible = isExpanded ? values : values.slice(0, MAX_VISIBLE);
                  const hiddenCount = values.length - MAX_VISIBLE;
                  const isStatus = type === "STATUS";
                  return (
                    <div key={type} className="eg-row">
                      <span className="eg-type">{type}</span>
                      <div className="eg-chips">
                        {visible.map((val) => {
                          let chipClass = "eg-chip";
                          if (isStatus) {
                            const v = val.toLowerCase();
                            if (v.includes("develop") || v.includes("escalat")) chipClass += " eg-status-developing";
                            else if (v.includes("ongoing") || v.includes("active") || v.includes("alert")) chipClass += " eg-status-active";
                            else if (v.includes("resolv") || v.includes("confirm") || v.includes("complet")) chipClass += " eg-status-resolved";
                            else if (v.includes("denied") || v.includes("false") || v.includes("dismiss")) chipClass += " eg-status-denied";
                            else chipClass += " eg-status-developing";
                          }
                          return (
                            <Link
                              key={val}
                              href={`/search?q=${encodeURIComponent(val)}`}
                              className={chipClass}
                            >
                              {val}
                            </Link>
                          );
                        })}
                        {!isExpanded && hiddenCount > 0 && (
                          <button
                            className="eg-more"
                            onClick={() => setExpandedEntityTypes(prev => new Set([...prev, type]))}
                            aria-label={`Show ${hiddenCount} more ${type} entities`}
                          >
                            +{hiddenCount} more
                          </button>
                        )}
                        {isExpanded && values.length > MAX_VISIBLE && (
                          <button
                            className="eg-more"
                            onClick={() => setExpandedEntityTypes(prev => { const s = new Set(prev); s.delete(type); return s; })}
                            aria-label={`Show fewer ${type} entities`}
                          >
                            Show less
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          );
        })()}

        {/* Timeline */}
        {story.timeline && story.timeline.length > 0 && (
          <>
            <div className="slbl" style={{ marginTop: 8 }}>How it unfolded</div>
            <div style={{ marginBottom: 28 }}>
              {story.timeline.map((ev, i) => (
                <div key={ev.id || i} className="tl-item">
                  <div className="tl-time" suppressHydrationWarning>
                    {ev.event_time ? (mounted ? formatTime(ev.event_time) : formatDateStable(ev.event_time)) : ""}
                  </div>
                  <div className="tl-rail">
                    <div className={`tl-dot ${i === 0 ? "lat" : ""}`} />
                    <div className="tl-line" />
                  </div>
                  <div>
                    <div className="tl-ev">{ev.description}</div>
                    <div className="tl-src" suppressHydrationWarning>
                      {ev.event_time ? (mounted ? formatDate(ev.event_time) : formatDateStable(ev.event_time)) : ""}
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
            <div className="slbl">Source Coverage</div>
            <div style={{ overflowX: "auto" }}>
              <table className="ctbl">
                <thead>
                  <tr>
                    <th style={{ minWidth: 120 }}>Source</th>
                    <th style={{ minWidth: 180 }}>Primary focus</th>
                    <th>Published</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {story.source_coverage.map((cov, i) => (
                    <tr key={cov.id}>
                      <td>
                        <div className="sname" style={{ display: "flex", alignItems: "center" }}>
                          {cov.source?.logo_url ? (
                            <img
                              src={cov.source.logo_url}
                              alt={cov.source.name}
                              style={{ width: "16px", height: "16px", borderRadius: "50%", marginRight: "8px", objectFit: "cover" }}
                            />
                          ) : (
                            <div
                              className="sdot"
                              style={{
                                background: SOURCE_COLORS[i % SOURCE_COLORS.length],
                              }}
                            />
                          )}
                          {cov.source?.name}
                        </div>
                      </td>

                      <td className="sfoc">{cov.focus_area}</td>
                      <td className="stim" suppressHydrationWarning>{cov.published_at ? (mounted ? formatTime(cov.published_at) : formatDateStable(cov.published_at)) : "—"}</td>
                      <td>
                        {(() => {
                          const srcArticle = story.articles?.find(
                            (a) => a.source?.id === cov.source?.id,
                          );
                          const href = srcArticle?.url || cov.source?.website_url;
                          return href ? (
                            <a
                              href={href}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="slink"
                            >
                              Read <ExternalLink size={11} aria-hidden="true" />
                            </a>
                          ) : (
                            <span className="miss">—</span>
                          );
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Difference Engine */}
        {story.differences && story.differences.length > 0 && (
          <>
            <div className="slbl">Where sources differ</div>
            <div style={{
              fontSize: 11,
              color: "var(--ink3)",
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--r6)",
              padding: "8px 12px",
              marginBottom: 12
            }}>
              <strong>AI Comparative Analysis:</strong> Surfaced conflicts and omissions are compiled using AI models. Verify coverage details using original articles.
            </div>
            <div style={{ overflowX: "auto" }}>

              <table className="dtbl">
                <thead>
                  <tr>
                    <th style={{ minWidth: 120 }}>Source</th>
                    <th>Unique Info</th>
                    <th>Missing</th>
                    <th>Contradictions</th>
                  </tr>
                </thead>
                <tbody>
                  {story.differences.map((diff) => (
                    <tr key={diff.id} className={diff.contradictions ? "dconfl" : ""}>
                      <td style={{ fontWeight: 500 }}>{diff.source?.name}</td>
                      <td>{diff.unique_information || <span className="miss">—</span>}</td>
                      <td>{diff.missing_information || <span className="miss">—</span>}</td>
                      <td>
                        {diff.contradictions ? (
                          <span className="confl-ic">
                            <AlertTriangle size={12} aria-hidden="true" />
                            {diff.contradictions}
                          </span>
                        ) : (
                          <span className="miss">None</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Original Articles */}
        {story.articles && story.articles.length > 0 && (
          <>
            <div className="slbl" style={{ marginTop: 32 }}>Original Articles</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {story.articles.map((art) => (
                <a
                  key={art.id}
                  href={art.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bkcard"
                  style={{ display: "flex", justifyContent: "space-between", textDecoration: "none" }}
                >
                  <div style={{ flex: 1 }}>
                    <div className="bk-hl">{art.title}</div>
                    <div className="bk-mt" style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      {art.source?.logo_url && (
                        <img
                          src={art.source.logo_url}
                          alt={art.source.name}
                          style={{ width: "14px", height: "14px", borderRadius: "50%", objectFit: "cover" }}
                        />
                      )}
                      <span>{art.source?.name}</span>
                      {art.author && <span>By {art.author}</span>}
                      <span suppressHydrationWarning>{mounted ? formatDate(art.published_at) : formatDateStable(art.published_at)}</span>
                    </div>

                  </div>
                  <ExternalLink size={14} style={{ color: "var(--ink3)", flexShrink: 0, marginTop: 4 }} aria-hidden="true" />
                </a>
              ))}
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
