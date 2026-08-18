"use client"; // Error boundaries must be Client Components.

import { AlertTriangle, RotateCcw } from "lucide-react";

/**
 * Route-level error boundary.
 *
 * The app had no `error.tsx`, `global-error.tsx` or `not-found.tsx` anywhere, so
 * an uncaught render error anywhere in the tree fell through to the framework
 * default — a blank or generic page with no way back.
 *
 * Uses `unstable_retry` rather than `reset`: on this version of Next.js, retry
 * re-fetches and re-renders the boundary's children inside a Transition, while
 * `reset` only clears the error state without re-fetching, which for a
 * data-driven page usually just re-renders straight back into the same error.
 */
export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <main
      id="main-content"
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center"
    >
      <AlertTriangle className="h-10 w-10 text-amber-500" aria-hidden="true" />
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-prose text-sm text-muted-foreground">
        This page could not be loaded. The problem has been logged; trying again often
        resolves it.
      </p>
      {/* The digest is the only handle support has on a production stack trace,
          since the message itself is redacted in production builds. */}
      {error.digest && (
        <p className="font-mono text-xs text-muted-foreground">Reference: {error.digest}</p>
      )}
      <button
        onClick={() => unstable_retry()}
        className="mt-2 inline-flex items-center gap-2 rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <RotateCcw className="h-4 w-4" aria-hidden="true" />
        Try again
      </button>
    </main>
  );
}
