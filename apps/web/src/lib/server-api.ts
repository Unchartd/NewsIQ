/**
 * Server-side data helpers for stories.
 *
 * Used by Server Components (e.g. generateMetadata, JSON-LD) to fetch a story
 * directly from the backend without going through the browser axios client.
 */

import type { StoryDetail } from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * Fetch a story by ID on the server. Returns null on any error (404, network).
 * Uses Next.js fetch caching with a short revalidate window so SSR stays fast
 * while still reflecting fresh AI-generated content.
 */
export async function fetchStoryServer(storyId: string): Promise<StoryDetail | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/stories/${storyId}`, {
      next: { revalidate: 300 }, // 5 minutes
    });
    if (!res.ok) return null;
    return (await res.json()) as StoryDetail;
  } catch {
    return null;
  }
}
