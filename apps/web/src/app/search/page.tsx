import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";
import SearchPage from "./search-client";

export const metadata: Metadata = buildPageMetadata(
  "Search News",
  "Search thousands of AI-clustered news stories across all categories. Find breaking news, trending topics, and in-depth coverage from multiple sources on NewsIQ.",
  "/search",
  {
    keywords: [
      "search news",
      "find news",
      "news search engine",
      "AI news search",
      "NewsIQ search",
    ],
    // Search pages generally shouldn't be indexed with query parameters
    // The base /search page is fine to index
  }
);

const webPageSchema = buildWebPageSchema(
  "Search News — NewsIQ",
  "Search thousands of AI-clustered news stories on NewsIQ.",
  "/search"
);

export default function SearchServerPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(webPageSchema) }}
      />
      <SearchPage />
    </>
  );
}
