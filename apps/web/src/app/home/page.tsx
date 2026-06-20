import type { Metadata } from "next";
import { HomeContent } from "./home-content";
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

export default function HomePage() {
  return <HomeContent />;
}
