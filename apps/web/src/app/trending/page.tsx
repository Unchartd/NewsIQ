import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";
import { buildCollectionPageSchema, buildBreadcrumbSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";
import TrendingPage from "./trending-client";

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

export default function TrendingServerPage() {
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
      <TrendingPage />
    </>
  );
}
