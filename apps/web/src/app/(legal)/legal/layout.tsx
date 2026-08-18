import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

/**
 * Metadata for /legal.
 *
 * The page itself is a Client Component, and Client Components cannot export
 * `metadata`. These are publicly linked, indexable pages, so without a server
 * layout they inherited only the root layout's defaults — every legal page
 * shared one title and description.
 */
export const metadata: Metadata = buildPageMetadata(
  "Legal & Policies",
  "NewsIQ's legal policies: privacy, terms of service, DMCA and copyright, content attribution, and data retention.",
  "/legal",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
