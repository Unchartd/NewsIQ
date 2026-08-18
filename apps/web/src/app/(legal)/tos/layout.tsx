import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

/**
 * Metadata for /tos.
 *
 * The page itself is a Client Component, and Client Components cannot export
 * `metadata`. These are publicly linked, indexable pages, so without a server
 * layout they inherited only the root layout's defaults — every legal page
 * shared one title and description.
 */
export const metadata: Metadata = buildPageMetadata(
  "Terms of Service",
  "The terms governing your use of NewsIQ, including acceptable use, subscriptions, content attribution, and liability.",
  "/tos",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
