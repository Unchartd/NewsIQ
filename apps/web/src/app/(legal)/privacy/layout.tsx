import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";

/**
 * Metadata for /privacy.
 *
 * The page itself is a Client Component, and Client Components cannot export
 * `metadata`. These are publicly linked, indexable pages, so without a server
 * layout they inherited only the root layout's defaults — every legal page
 * shared one title and description.
 */
export const metadata: Metadata = buildPageMetadata(
  "Privacy Policy",
  "How NewsIQ collects, uses, and protects your personal data, including cookies, analytics, and your rights over your information.",
  "/privacy",
);

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
