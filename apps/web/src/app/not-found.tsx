import Link from "next/link";
import type { Metadata } from "next";

/**
 * 404 page.
 *
 * The app had no `not-found.tsx`, so a missing story or a mistyped URL rendered
 * the framework default. `notFound()` is already called by the story route when
 * a story cannot be fetched, so this is reachable in normal use.
 */
export const metadata: Metadata = {
  title: "Page not found",
  // A 404 must never be indexed, or search engines accumulate soft-404 entries
  // for every mistyped or expired story URL.
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <main
      id="main-content"
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center"
    >
      <p className="font-mono text-sm text-muted-foreground">404</p>
      <h1 className="text-xl font-semibold">This page could not be found</h1>
      <p className="max-w-prose text-sm text-muted-foreground">
        The story may have been removed, or the link may be incorrect.
      </p>
      <Link
        href="/"
        className="mt-2 rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        Back to top stories
      </Link>
    </main>
  );
}
