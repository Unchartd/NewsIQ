"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { usePathname, useRouter } from "next/navigation";
import CookieBanner from "@/components/legal/cookie-banner";


const PUBLIC_PATHS = [
  "/",
  "/home",
  "/category",
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

const AUTH_ONLY_PATHS = [
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
];

function AuthInitializer({ children }: { children: React.ReactNode }) {
  const { setUser, setLoading, isAuthenticated, isLoading } = useAuthStore();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    async function initAuth() {
      // Skip auth check for public pages to avoid redundant /auth/me calls
      const publicPaths = ["/login", "/signup", "/forgot-password", "/reset-password", "/tos", "/privacy", "/legal"];

      if (publicPaths.includes(window.location.pathname)) {
        setLoading(false);
        return;
      }

      try {
        const res = await apiClient.get("/auth/me");
        setUser(res.data);
      } catch (err) {
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

    const isPublic = PUBLIC_PATHS.some(
      (path) => pathname === path || pathname.startsWith(path + "/")
    );
    const isAuthOnly = AUTH_ONLY_PATHS.some(
      (path) => pathname === path || pathname.startsWith(path + "/")
    );

    if (!isPublic && !isAuthenticated) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    } else if (isAuthOnly && isAuthenticated) {
      router.replace("/home");
    }
  }, [isLoading, isAuthenticated, pathname, router]);

  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );
  const isAuthOnly = AUTH_ONLY_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );

  // While initializing, show a loader on protected pages to prevent flash of content
  if (isLoading && !isPublic) {
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
  if (!isPublic && !isAuthenticated) {
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
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
            retry: 2,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <TooltipProvider>
          <AuthInitializer>{children}</AuthInitializer>
          <Toaster position="bottom-right" richColors closeButton />
          <CookieBanner />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>

  );
}
