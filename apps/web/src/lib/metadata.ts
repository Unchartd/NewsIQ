/**
 * metadata.ts — Centralized metadata factory for NewsIQ
 *
 * All page-level metadata should be built through these factories.
 * This ensures consistency across title templates, OG images,
 * canonical URLs, and structured data across all 20+ routes.
 *
 * Usage:
 *   export const metadata = buildPageMetadata("Trending", "Top stories right now", "/trending");
 */

import type { Metadata } from "next";

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://newsiq.online";
export const SITE_NAME = "NewsIQ";
export const SITE_DESCRIPTION =
  "Understand any major story in under 30 seconds. AI-powered news clustering, multi-source comparison, neutral headlines, and transparent summaries.";

// Default OG image — served from /public/og-image.png (1200×630)
export const DEFAULT_OG_IMAGE = `${SITE_URL}/og-image.png`;

// Default Twitter handle
export const TWITTER_HANDLE = "@newsiq_online";

/**
 * Slugifies a given text to make it URL-friendly.
 */
export function slugify(text: string): string {
  return text
    .toString()
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-") // Replace spaces with -
    .replace(/[^\w\-]+/g, "") // Remove all non-word chars
    .replace(/\-\-+/g, "-") // Replace multiple - with single -
    .replace(/^-+/, "") // Trim - from start of text
    .replace(/-+$/, ""); // Trim - from end of text
}

/**
 * Generates the SEO-friendly URL route for a story.
 */
export function getStoryRoute(story: { id: string; headline: string }): string {
  if (!story.headline) return `/story/${story.id}`;
  const slug = slugify(story.headline);
  return `/story/${slug}-${story.id}`;
}

/**
 * Build metadata for a standard informational page.
 */
export function buildPageMetadata(
  title: string,
  description: string,
  path: string,
  options?: {
    noIndex?: boolean;
    ogImage?: string;
    keywords?: string[];
  }
): Metadata {
  const url = `${SITE_URL}${path}`;
  const ogImage = options?.ogImage || DEFAULT_OG_IMAGE;

  return {
    title,
    description,
    keywords: options?.keywords,
    alternates: {
      canonical: url,
    },
    openGraph: {
      type: "website",
      url,
      title,
      description,
      siteName: SITE_NAME,
      locale: "en_US",
      images: [
        {
          url: ogImage,
          width: 1200,
          height: 630,
          alt: `${title} — ${SITE_NAME}`,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      site: TWITTER_HANDLE,
      title,
      description,
      images: [ogImage],
    },
    robots: options?.noIndex
      ? { index: false, follow: false }
      : { index: true, follow: true },
  };
}

/**
 * Build metadata for a news story/article page.
 * Includes article-specific OG properties and full canonical.
 */
export function buildStoryMetadata(
  story: {
    id: string;
    headline: string;
    one_line_summary?: string;
    short_summary?: string;
    first_seen_at?: string;
    updated_at?: string;
    category?: { name: string } | null;
    tags?: string[];
    articles?: Array<{ image_url?: string | null }>;
  }
): Metadata {
  const url = `${SITE_URL}${getStoryRoute(story)}`;
  const title = story.headline;
  const description =
    story.one_line_summary ||
    story.short_summary ||
    "AI-summarized multi-source news story on NewsIQ.";

  const ogImage =
    story.articles?.find((a) => a.image_url)?.image_url || DEFAULT_OG_IMAGE;

  const keywords = [
    ...(story.tags || []),
    story.category?.name || "",
    "AI news summary",
    "multi-source news",
    "NewsIQ",
  ].filter(Boolean);

  return {
    title,
    description,
    keywords,
    alternates: {
      canonical: url,
    },
    openGraph: {
      type: "article",
      url,
      title,
      description,
      siteName: SITE_NAME,
      locale: "en_US",
      publishedTime: story.first_seen_at || undefined,
      modifiedTime: story.updated_at || undefined,
      section: story.category?.name || undefined,
      tags: story.tags || undefined,
      images: [
        {
          url: ogImage,
          width: 1200,
          height: 630,
          alt: title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      site: TWITTER_HANDLE,
      title,
      description,
      images: [ogImage],
    },
    robots: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  };
}

/**
 * Build metadata for a category/topic page.
 */
export function buildCategoryMetadata(slug: string, name: string): Metadata {
  const title = `${name} News`;
  const description = `Latest ${name} news, AI-summarized and fact-checked across multiple sources. Updated every 5 minutes on NewsIQ.`;

  return buildPageMetadata(title, description, `/category/${slug}`, {
    keywords: [`${name} news`, `${name} latest`, "AI news", "NewsIQ", slug],
    ogImage: DEFAULT_OG_IMAGE,
  });
}

/**
 * Metadata for pages that must NOT be indexed (auth, settings, etc.)
 */
export function buildNoIndexMetadata(title: string): Metadata {
  return {
    title,
    robots: {
      index: false,
      follow: false,
      noarchive: true,
      nosnippet: true,
    },
  };
}
