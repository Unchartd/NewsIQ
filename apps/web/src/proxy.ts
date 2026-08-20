import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { isAuthOnlyPath, isProtectedPath } from "@/lib/route-access";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Determine if the path requires a session
  const isProtected = isProtectedPath(pathname);

  // 2. Check for authentication tokens in cookies
  const hasRefreshToken = request.cookies.has("refresh_token");
  const hasAccessToken = request.cookies.has("access_token");
  const isAuthenticated = hasRefreshToken || hasAccessToken;

  // 3. Server-side redirect rules
  if (isProtected) {
    // Protected page: redirect to login if not authenticated
    if (!isAuthenticated) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  } else {
    // Public (or non-existent) page. Unknown paths fall through to the router
    // and 404 rather than being redirected.
    const isAuthOnly = isAuthOnlyPath(pathname);
    if (isAuthOnly && isAuthenticated) {
      return NextResponse.redirect(new URL("/home", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - sitemap.xml, robots.txt (search engine files)
     * - file names with extensions (e.g. logo.png, styles.css)
     */
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|.*\\.[\\w]+$).*)",
  ],
};
