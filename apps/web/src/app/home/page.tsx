import type { Metadata } from "next";
import { HomeContent } from "./home-content";
import { fetchStoriesServer } from "@/lib/server-api";
import { buildPageMetadata } from "@/lib/metadata";

// Rendered per request. HomeContentInner calls useSearchParams(), which in a
// statically rendered page makes Next bail out to the nearest Suspense
// fallback on the server — and that fallback is null, so the prerendered HTML
// contained no stories and no /story/ links at all. The feed is per-visitor
// anyway; fetchStoriesServer still caches the upstream call for 120s, so the
// backend sees the same load either way.
export const dynamic = "force-dynamic";


export const metadata: Metadata = buildPageMetadata(
  "Your News Feed",
  "Your personalised AI-powered news feed. Multi-source stories clustered and summarised by topic. Updated every 5 minutes across technology, politics, business, sports, and more.",
  "/home",
  {
    keywords: [
      "AI news feed",
      "personalised news",
      "news dashboard",
      "latest news",
      "multi-source news",
    ],
  }
);

export default async function HomePage() {
  // Rendered on the server so the HTML a crawler sees contains stories and
  // their links. Matches the client's default query: category 'all', 20 items.
  const initialStories = await fetchStoriesServer({ limit: 20 });

  return <HomeContent initialStories={initialStories} />;
}
