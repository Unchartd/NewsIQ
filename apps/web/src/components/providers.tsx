"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { isAuthOnlyPath, isProtectedPath } from "@/lib/route-access";
import apiClient from "@/lib/api-client";
import { usePathname, useRouter } from "next/navigation";
import CookieBanner from "@/components/legal/cookie-banner";
import { ConsentProvider } from "@/components/legal/consent-provider";
import { AnalyticsTracker } from "@/components/analytics/analytics-tracker";
import { analytics } from "@/lib/analytics/service";






function AuthInitializer({ children }: { children: React.ReactNode }) {
  const { setUser, setLoading, isAuthenticated, isLoading } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    async function initAuth() {
      // Skip auth check for authentication pages and basic legal docs to avoid redundant /auth/me calls
      const publicNoAuthCheckPaths = [
        "/login",
        "/signup",
        "/forgot-password",
        "/reset-password",
        "/verify-email",
        "/tos",
        "/privacy",
        "/legal",
        "/auth/callback",
      ];

      const shouldSkipAuth = publicNoAuthCheckPaths.some(
        (path) =>
          window.location.pathname === path ||
          window.location.pathname.startsWith(path + "/")
      );

      if (shouldSkipAuth) {
        setLoading(false);
        return;
      }

      try {
        const res = await apiClient.get("/auth/me");
        setUser(res.data);
        if (res.data) {
          analytics.identify(res.data.id, {
            user_tier: res.data.role,
            subscription_status: res.data.subscription_plan,
          });
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    initAuth();
  }, [setUser, setLoading]);

  // Client-side route protection & redirection logic
  useEffect(() => {
    if (isLoading) return;

    const isProtected = isProtectedPath(pathname);
    const isAuthOnly = isAuthOnlyPath(pathname);

    if (isProtected && !isAuthenticated) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    } else if (isAuthOnly && isAuthenticated) {
      router.replace("/home");
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  const isProtected = isProtectedPath(pathname);
  const isAuthOnly = isAuthOnlyPath(pathname);

  // Show the session loader only on genuinely protected pages. This used to
  // fire for anything absent from a local PUBLIC_PATHS copy — including
  // /trending, /search and every E-E-A-T page — so during SSR (isLoading is
  // always true there) a crawler received "Verifying secure session..." and
  // no content at all.
  if (isLoading && isProtected) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="text-center space-y-4">
          <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-muted-foreground font-medium animate-pulse">
            Verifying secure session...
          </p>
        </div>
      </div>
    );
  }

  // Prevent flashing protected content while redirection is in progress
  if (isProtected && !isAuthenticated) {
    return null;
  }

  // Prevent flashing auth pages while redirection to home is in progress
  if (isAuthOnly && isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () => {
      const client = new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
            retry: 2,
          },
        },
      });
      if (typeof window !== "undefined") {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).queryClient = client;
      }
      return client;
    }
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <ConsentProvider>
          <TooltipProvider>
            <AnalyticsTracker />
            <AuthInitializer>{children}</AuthInitializer>
            <Toaster position="bottom-right" richColors closeButton />
            <CookieBanner />
          </TooltipProvider>
        </ConsentProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
