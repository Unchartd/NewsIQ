/**
 * Single source of truth for which routes require a session.
 *
 * This list existed in three places — `proxy.ts`, `providers.tsx`, and by hand
 * in `robots.ts` — each as an allowlist of PUBLIC paths, with everything else
 * treated as protected. Default-deny is wrong for a public news site, and the
 * duplication meant a page could be public in one copy and gated in another.
 * It failed three separate times:
 *
 *   1. Nine genuinely public pages (/trending, /search, /topics, /about and
 *      the E-E-A-T pages) 307'd to /login from the proxy while being
 *      advertised in the sitemap.
 *   2. After the proxy was fixed, `providers.tsx` still gated them: during SSR
 *      `isLoading` is true, so any path missing from ITS copy rendered
 *      "Verifying secure session..." — a crawler fetching /trending got a
 *      spinner instead of the page, with zero story links.
 *   3. Any path that does not exist redirected to /login instead of returning
 *      404, showing crawlers a login wall in place of a clean 404.
 *
 * Inverted and shared: a route is public unless it is listed here, so a new
 * public page cannot be walled by omission, and an unknown path falls through
 * to the router and 404s.
 */
export const PROTECTED_PATHS = [
  "/settings",
  "/notifications",
  "/bookmarks",
  "/digest",
  "/profile",
  "/onboarding",
] as const;

/** Routes only meaningful to a signed-out visitor. */
export const AUTH_ONLY_PATHS = [
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
] as const;

function matches(pathname: string, paths: readonly string[]): boolean {
  return paths.some((path) => pathname === path || pathname.startsWith(path + "/"));
}

export function isProtectedPath(pathname: string): boolean {
  return matches(pathname, PROTECTED_PATHS);
}

export function isAuthOnlyPath(pathname: string): boolean {
  return matches(pathname, AUTH_ONLY_PATHS);
}
