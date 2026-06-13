import type { Metadata } from "next";

import { fetchStoryServer } from "@/lib/server-api";
import { StoryDetailClient } from "./story-detail-client";

interface PageProps {
  params: Promise<{ storyId: string }>;
}

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://newsiq.app";

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { storyId } = await params;
  const story = await fetchStoryServer(storyId);

  if (!story) {
    return {
      title: "Story not found",
      robots: { index: false, follow: false },
    };
  }

  const description =
    story.one_line_summary || story.short_summary || "AI-summarized news story on NewsIQ.";
  const url = `${SITE_URL}/story/${storyId}`;
  const ogImage = story.articles?.find((a) => a.image_url)?.image_url || undefined;

  return {
    title: story.headline || "News story",
    description,
    alternates: { canonical: url },
    openGraph: {
      type: "article",
      url,
      title: story.headline || "News story",
      description,
      siteName: "NewsIQ",
      images: ogImage ? [{ url: ogImage }] : undefined,
      publishedTime: story.first_seen_at || undefined,
      modifiedTime: story.updated_at || undefined,
    },
    twitter: {
      card: "summary_large_image",
      title: story.headline || "News story",
      description,
      images: ogImage ? [ogImage] : undefined,
    },
  };
}

export default async function StoryDetailPage({ params }: PageProps) {
  const { storyId } = await params;
  const story = await fetchStoryServer(storyId);

  // NewsArticle structured data for SEO / rich results
  const jsonLd = story
    ? {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        headline: story.headline,
        description: story.one_line_summary || story.short_summary,
        datePublished: story.first_seen_at || undefined,
        dateModified: story.updated_at || undefined,
        articleSection: story.category?.name,
        url: `${SITE_URL}/story/${storyId}`,
        publisher: {
          "@type": "Organization",
          name: "NewsIQ",
        },
        isBasedOn: (story.articles || [])
          .filter((a) => a.url)
          .map((a) => a.url),
      }
    : null;

  return (
    <>
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      )}
      <StoryDetailClient storyId={storyId} initialStory={story} />
    </>
  );
}
