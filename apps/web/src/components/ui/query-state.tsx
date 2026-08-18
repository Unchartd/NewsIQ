"use client";

import type { ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

/**
 * Renders the loading, error and empty states of a React Query result.
 *
 * The audit found 47 `useQuery` calls in this app and only 8 references to
 * `isError`. Loading was handled almost everywhere; failure was not. A failed
 * request rendered an empty region with no message and no way to retry — which
 * a reader cannot distinguish from "there is genuinely nothing here".
 *
 * This deliberately does **not** throw to the route-level `error.tsx`. A failed
 * sidebar widget should not blank the article a reader is in the middle of; the
 * boundary in `app/error.tsx` is for render failures, this is for data failures.
 */
export function QueryState({
  isLoading,
  isError,
  error,
  isEmpty,
  onRetry,
  loading,
  emptyMessage = "Nothing to show yet.",
  label = "content",
  children,
}: {
  isLoading: boolean;
  isError?: boolean;
  error?: unknown;
  /** Pass the emptiness test explicitly; only the caller knows what empty means. */
  isEmpty?: boolean;
  onRetry?: () => void;
  /** Skeleton to show while loading. Falls back to a labelled status region. */
  loading?: ReactNode;
  emptyMessage?: string;
  /** Used in the status announcement, e.g. "trending stories". */
  label?: string;
  children: ReactNode;
}) {
  if (isLoading) {
    return (
      <>
        {loading ?? (
          // role="status" so a screen reader announces the wait rather than
          // leaving the user on a silent, empty region.
          <div role="status" aria-live="polite" className="py-8 text-center text-sm text-muted-foreground">
            Loading {label}…
          </div>
        )}
      </>
    );
  }

  if (isError) {
    const message =
      error instanceof Error && error.message ? error.message : `Could not load ${label}.`;
    return (
      <div
        role="alert"
        className="flex flex-col items-center gap-3 rounded-lg border border-border px-6 py-8 text-center"
      >
        <AlertTriangle className="h-6 w-6 text-amber-500" aria-hidden="true" />
        <p className="text-sm font-medium">Could not load {label}</p>
        <p className="max-w-prose text-xs text-muted-foreground">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-1 inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-xs font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            Try again
          </button>
        )}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">{emptyMessage}</p>
    );
  }

  return <>{children}</>;
}
