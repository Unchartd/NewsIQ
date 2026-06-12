"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import {
  User,
  Crown,
  Bell,
  Grid,
  Map,
  BookOpen,
  Sun,
  Moon,
  Bookmark,
  ChevronRight,
  LogOut,
} from "lucide-react";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import type { Story, UserPreferences } from "@/types";
import { AppShell } from "@/components/layout/app-shell";

export default function ProfilePage() {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { user, isAuthenticated, logout: storeLogout } = useAuthStore();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, router]);

  // Query User Preferences
  const { data: preferences } = useQuery<UserPreferences>({
    queryKey: ["user-preferences"],
    queryFn: async () => {
      const response = await apiClient.get("/users/preferences");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Query bookmarks to display current count
  const { data: bookmarks } = useQuery<Story[]>({
    queryKey: ["bookmarked-stories"],
    queryFn: async () => {
      const response = await apiClient.get("/stories/bookmarks");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Still logout locally if API fails
    }
    storeLogout();
    toast.success("Logged out successfully");
    router.push("/");
  };

  const toggleAppTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    toast.success(`Theme switched to ${nextTheme === "dark" ? "Dark" : "Light"}`);
  };

  if (!user) return null;

  const initials = user.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : user.email[0].toUpperCase();

  const isPro = user.subscription_plan === "pro";
  const bookmarkCount = bookmarks?.length || 0;

  // Format preference labels
  const categoriesCount = preferences?.categories?.length || 0;
  const categoriesLabel = categoriesCount > 0 ? `${categoriesCount} selected` : "None";
  
  const locationsList = [];
  if (preferences?.countries?.length) locationsList.push(...preferences.countries);
  if (preferences?.cities?.length) locationsList.push(...preferences.cities);
  const locationsLabel = locationsList.length > 0 ? locationsList.join(", ") : "Global";

  const summaryLabel = preferences?.preferred_summary_type
    ? preferences.preferred_summary_type.charAt(0).toUpperCase() + preferences.preferred_summary_type.slice(1)
    : "Short";

  return (
    <AppShell>
      <div style={{ maxWidth: 680, margin: "0 auto", paddingBottom: 60 }}>
        {/* Profile Header */}
        <div className="niq-profile-header">
          <div className="niq-profile-avatar-lg">{initials}</div>
          <div>
            <div className="niq-profile-name">{user.name || "User"}</div>
            <div className="niq-profile-email">{user.email}</div>
            {isPro ? (
              <div className="niq-pro-badge">
                <Crown className="w-3 h-3 mr-1" />
                Pro member
              </div>
            ) : (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--ink-3)",
                  padding: "2px 8px",
                  border: "1px solid var(--border)",
                  borderRadius: 99,
                  marginTop: 6,
                }}
              >
                Free account
              </div>
            )}
          </div>
        </div>

        <div style={{ padding: "0 24px" }}>
          {/* Account Section */}
          <div style={{ marginTop: 24, marginBottom: 8 }} className="section-label">
            Account
          </div>
          <ul className="niq-settings-list">
            <li className="niq-settings-item" onClick={() => toast.info("Profile editing coming soon!")}>
              <div className="niq-settings-icon">
                <User className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Edit profile</div>
              <ChevronRight className="w-4 h-4 text-gray-400" />
            </li>
            
            <li className="niq-settings-item" onClick={() => router.push("/premium")}>
              <div className="niq-settings-icon">
                <Crown className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Subscription</div>
              <div className="niq-settings-value">
                {isPro ? "Pro • Renews Jul 2026" : "Free • Upgrade available"}
              </div>
            </li>

            <li className="niq-settings-item" onClick={() => router.push("/settings")}>
              <div className="niq-settings-icon">
                <Bell className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Notifications</div>
              <ChevronRight className="w-4 h-4 text-gray-400" />
            </li>
          </ul>

          {/* Preferences Section */}
          <div style={{ marginTop: 20, marginBottom: 8 }} className="section-label">
            Preferences
          </div>
          <ul className="niq-settings-list">
            <li className="niq-settings-item" onClick={() => router.push("/onboarding")}>
              <div className="niq-settings-icon">
                <Grid className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Topics & categories</div>
              <div className="niq-settings-value">{categoriesLabel}</div>
            </li>

            <li className="niq-settings-item" onClick={() => router.push("/onboarding")}>
              <div className="niq-settings-icon">
                <Map className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Locations</div>
              <div className="niq-settings-value" style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {locationsLabel}
              </div>
            </li>

            <li className="niq-settings-item" onClick={() => router.push("/onboarding")}>
              <div className="niq-settings-icon">
                <BookOpen className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Default summary</div>
              <div className="niq-settings-value">{summaryLabel}</div>
            </li>

            <li className="niq-settings-item" onClick={toggleAppTheme}>
              <div className="niq-settings-icon">
                {theme === "dark" ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
              </div>
              <div className="niq-settings-label">Theme</div>
              <div className="niq-settings-value" style={{ textTransform: "capitalize" }}>
                {theme || "light"}
              </div>
            </li>
          </ul>

          {/* Reading Section */}
          <div style={{ marginTop: 20, marginBottom: 8 }} className="section-label">
            Reading
          </div>
          <ul className="niq-settings-list">
            <li className="niq-settings-item" onClick={() => router.push("/bookmarks")}>
              <div className="niq-settings-icon">
                <Bookmark className="w-4 h-4" />
              </div>
              <div className="niq-settings-label">Saved stories</div>
              <div className="niq-settings-value">
                {bookmarkCount} {bookmarkCount === 1 ? "story" : "stories"}
              </div>
            </li>
          </ul>

          {/* Sign Out Button */}
          <div style={{ marginTop: 28, paddingBottom: 40 }}>
            <button
              onClick={handleLogout}
              disabled={isLoggingOut}
              style={{
                color: "var(--error)",
                fontSize: "14px",
                fontWeight: 500,
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "10px 0",
                width: "100%",
                textAlign: "left",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <LogOut className="w-4 h-4" />
              {isLoggingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
