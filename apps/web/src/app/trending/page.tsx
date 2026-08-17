import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";
import { buildCollectionPageSchema, buildBreadcrumbSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";
import TrendingPage from "./trending-client";
import { fetchStoriesServer } from "@/lib/server-api";

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
  // Fetched here so the HTML contains the stories: this is a primary landing
  // page and was previously an empty shell for any crawler without JS.
  const initialStories = await fetchStoriesServer({ trending: true, limit: 15 });

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
