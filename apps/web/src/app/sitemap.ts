import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://newsiq.app";
const API_BASE_URL =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v1";

/**
 * Known category slugs — kept in sync with backend categories.
 * These get their own sitemap entries with topic authority.
 */
const CATEGORIES = [
  "technology",
  "politics",
  "business",
  "sports",
  "entertainment",
  "science",
  "health",
  "world",
  "india",
  "finance",
  "environment",
  "education",
];

/**
 * Static routes that are always indexable.
 */
const STATIC_ROUTES: MetadataRoute.Sitemap = [
  {
    url: SITE_URL,
    lastModified: new Date(),
    changeFrequency: "hourly",
    priority: 1.0,
  },
  {
    url: `${SITE_URL}/trending`,
    lastModified: new Date(),
    changeFrequency: "hourly",
    priority: 0.9,
  },
  {
    url: `${SITE_URL}/search`,
    lastModified: new Date(),
    changeFrequency: "daily",
    priority: 0.7,
  },
  {
    url: `${SITE_URL}/premium`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    url: `${SITE_URL}/topics`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.8,
  },
  // E-E-A-T pages
  {
    url: `${SITE_URL}/about`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.7,
  },
  {
    url: `${SITE_URL}/editorial-principles`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    url: `${SITE_URL}/methodology`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    url: `${SITE_URL}/ai-transparency`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.6,
  },
  {
    url: `${SITE_URL}/source-transparency`,
    lastModified: new Date(),
    changeFrequency: "monthly",
    priority: 0.6,
  },
];

/**
 * Category routes — one per known category.
 */
const CATEGORY_ROUTES: MetadataRoute.Sitemap = CATEGORIES.map((slug) => ({
  url: `${SITE_URL}/category/${slug}`,
  lastModified: new Date(),
  changeFrequency: "hourly" as const,
  priority: 0.85,
}));

/**
 * Fetch recent stories from the API for dynamic story entries.
 * Falls back to an empty array on error so the sitemap always renders.
 */
async function fetchRecentStoryIds(): Promise<Array<{ id: string; updatedAt: string }>> {
  try {
    const res = await fetch(`${API_BASE_URL}/stories?limit=200&sort=updated_at`, {
      next: { revalidate: 900 }, // Re-fetch every 15 minutes
    });
    if (!res.ok) return [];
    const stories = await res.json();
    const list = Array.isArray(stories) ? stories : (stories?.items ?? []);
    return list.map((s: { id: string; updated_at?: string }) => ({
      id: s.id,
      updatedAt: s.updated_at || new Date().toISOString(),
    }));
  } catch {
    return [];
  }
}

/**
 * Dynamic sitemap — includes static pages, categories, and recent stories.
 *
 * NewsIQ story pages are high-value: each represents a multi-source
 * AI-clustered news event. Submitting them ensures fast indexing.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const stories = await fetchRecentStoryIds();

  const storyRoutes: MetadataRoute.Sitemap = stories.map(({ id, updatedAt }) => ({
    url: `${SITE_URL}/story/${id}`,
    lastModified: new Date(updatedAt),
    changeFrequency: "hourly" as const,
    priority: 0.9,
  }));

  return [
    ...STATIC_ROUTES,
    ...CATEGORY_ROUTES,
    ...storyRoutes,
  ];
}
