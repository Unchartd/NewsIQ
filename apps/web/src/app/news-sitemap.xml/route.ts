import { NextResponse } from "next/server";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://newsiq.app";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Google News Sitemap — /news-sitemap.xml
 *
 * Google News requires a specialized sitemap format with <news:news> elements.
 * Only articles published within the last 2 days are eligible.
 * Ref: https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap
 */
export async function GET() {
  let stories: Array<{
    id: string;
    headline: string;
    first_seen_at: string;
    updated_at: string;
    category?: { name: string } | null;
  }> = [];

  try {
    const twoDaysAgo = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    const res = await fetch(
      `${API_BASE_URL}/stories?limit=100&sort=first_seen_at&after=${twoDaysAgo}`,
      { next: { revalidate: 300 } } // Refresh every 5 minutes
    );
    if (res.ok) {
      const data = await res.json();
      stories = Array.isArray(data) ? data : (data?.items ?? []);
    }
  } catch {
    // Return empty sitemap on error — non-fatal
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset
  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
  xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"
  xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
>
${stories
  .map((story) => {
    const pubDate = story.first_seen_at
      ? new Date(story.first_seen_at).toISOString()
      : new Date().toISOString();
    const headline = story.headline
      ? story.headline.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      : "NewsIQ Story";
    const section = story.category?.name
      ? story.category.name.replace(/&/g, "&amp;")
      : "General";

    return `  <url>
    <loc>${SITE_URL}/story/${story.id}</loc>
    <lastmod>${new Date(story.updated_at || story.first_seen_at).toISOString()}</lastmod>
    <news:news>
      <news:publication>
        <news:name>NewsIQ</news:name>
        <news:language>en</news:language>
      </news:publication>
      <news:publication_date>${pubDate}</news:publication_date>
      <news:title>${headline}</news:title>
      <news:keywords>${section}, AI news, ${section.toLowerCase()} news</news:keywords>
    </news:news>
  </url>`;
  })
  .join("\n")}
</urlset>`;

  return new NextResponse(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300, stale-while-revalidate=60",
    },
  });
}
