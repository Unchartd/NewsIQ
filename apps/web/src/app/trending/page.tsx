import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";
import { buildCollectionPageSchema, buildBreadcrumbSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";
import TrendingPage from "./trending-client";
import { fetchStoriesServer } from "@/lib/server-api";

// Rendered per request. HomeContentInner calls useSearchParams(), which in a
// statically rendered page makes Next bail out to the nearest Suspense
// fallback on the server — and that fallback is null, so the prerendered HTML
// contained no stories and no /story/ links at all. The feed is per-visitor
// anyway; fetchStoriesServer still caches the upstream call for 120s, so the
// backend sees the same load either way.
export const dynamic = "force-dynamic";


export const metadata: Metadata = buildPageMetadata(
  "Trending Stories",
  "Top trending news stories ranked by source count, recency, and engagement. AI-clustered from dozens of publishers. Updated every 5 minutes on NewsIQ.",
  "/trending",
  {
    keywords: [
      "trending news",
      "top news today",
      "breaking news",
      "most read news",
      "AI news trending",
      "NewsIQ trending",
    ],
  }
);

const collectionSchema = buildCollectionPageSchema(
  "Trending Stories — NewsIQ",
  "Most-covered news stories right now, ranked by source count, engagement, and recency.",
  `${SITE_URL}/trending`
);

const breadcrumbSchema = buildBreadcrumbSchema([
  { name: "Home", url: SITE_URL },
  { name: "Trending", url: `${SITE_URL}/trending` },
]);

export default async function TrendingServerPage() {
  // Server-rendered so the HTML a crawler sees contains stories and their
  // links. Matches the client's default tab: the 48h window, 15 items.
  const initialStories = await fetchStoriesServer({
    trending: true,
    window_hours: 48,
    limit: 15,
  });

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(collectionSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbSchema) }}
      />
      <TrendingPage initialStories={initialStories} />
    </>
  );
}
