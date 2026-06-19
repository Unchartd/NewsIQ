import type { Metadata } from "next";

import { fetchStoryServer } from "@/lib/server-api";
import { StoryDetailClient } from "./story-detail-client";
import { buildStoryMetadata } from "@/lib/metadata";
import {
  buildNewsArticleSchema,
  buildBreadcrumbSchema,
  serializeJsonLd,
} from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";

interface PageProps {
  params: Promise<{ storyId: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { storyId } = await params;
  const story = await fetchStoryServer(storyId);

  if (!story) {
    return {
      title: "Story Not Found",
      description: "This story could not be found on NewsIQ.",
      robots: { index: false, follow: false },
    };
  }

  return buildStoryMetadata(story);
}

export default async function StoryDetailPage({ params }: PageProps) {
  const { storyId } = await params;
  const story = await fetchStoryServer(storyId);

  const newsArticleSchema = story
    ? buildNewsArticleSchema(story)
    : null;

  const breadcrumbSchema = story
    ? buildBreadcrumbSchema([
        { name: "Home", url: SITE_URL },
        {
          name: story.category?.name ? `${story.category.name} News` : "News",
          url: story.category?.name
            ? `${SITE_URL}/category/${story.category.name.toLowerCase()}`
            : `${SITE_URL}/trending`,
        },
        { name: story.headline, url: `${SITE_URL}/story/${storyId}` },
      ])
    : null;

  return (
    <>
      {newsArticleSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(newsArticleSchema) }}
        />
      )}
      {breadcrumbSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbSchema) }}
        />
      )}
      <StoryDetailClient storyId={storyId} initialStory={story} />
    </>
  );
}
