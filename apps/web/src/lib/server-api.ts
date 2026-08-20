/**
 * Server-side data helpers for stories.
 *
 * Used by Server Components (e.g. generateMetadata, JSON-LD) to fetch a story
 * directly from the backend without going through the browser axios client.
 */

import type { Story, StoryDetail } from "@/types";

const API_BASE_URL =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000/api/v1";

/**
 * Fetch a story by ID on the server. Returns null on any error (404, network).
 * Uses Next.js fetch caching with a short revalidate window so SSR stays fast
 * while still reflecting fresh AI-generated content.
 */
export async function fetchStoryServer(storyId: string): Promise<StoryDetail | null> {
  try {
    // Extract the UUID (which is the last 36 characters of the slugified storyId or the storyId itself)
    const uuidMatch = storyId.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
    const uuid = uuidMatch ? uuidMatch[0] : storyId;

    const res = await fetch(`${API_BASE_URL}/stories/${uuid}`, {
      next: { revalidate: 300 }, // 5 minutes
    });
    if (!res.ok) return null;
    return (await res.json()) as StoryDetail;
  } catch {
    return null;
  }
}

/**
 * Fetch a list of stories on the server.
 *
 * `/home` and `/trending` were thin server wrappers around client components, so
 * the prerendered HTML contained the page shell and no stories: a crawler that
 * does not execute JavaScript indexed an empty page, and the LCP element could
 * not paint until JS loaded and a request completed. These are the product's
 * primary landing pages.
 *
 * Returns [] rather than throwing, so a backend blip degrades the page to the
 * client-side fetch it already performs instead of failing the render.
 */
export async function fetchStoriesServer(
  params: Record<string, string | number | boolean> = {},
  revalidateSeconds = 120,
): Promise<Story[]> {
  try {
    const query = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]),
    ).toString();

    const res = await fetch(`${API_BASE_URL}/stories${query ? `?${query}` : ""}`, {
      // Shorter than a story's 5 minutes: a feed's ordering changes more often
      // than any single story's contents.
      next: { revalidate: revalidateSeconds },
    });
    if (!res.ok) return [];
    return (await res.json()) as Story[];
  } catch {
    return [];
  }
}
