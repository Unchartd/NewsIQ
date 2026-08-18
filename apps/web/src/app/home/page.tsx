import type { Metadata } from "next";
import { HomeContent } from "./home-content";
import { fetchStoriesServer } from "@/lib/server-api";
import { buildPageMetadata } from "@/lib/metadata";

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
  // The default feed is rendered on the server so the HTML a crawler sees
  // contains stories. Matches the client's default query: category 'all', 20 items.
  const initialStories = await fetchStoriesServer({ limit: 20 });

  return <HomeContent initialStories={initialStories} />;
}
