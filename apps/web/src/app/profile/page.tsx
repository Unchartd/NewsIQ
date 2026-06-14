"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
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
      <div style={{ maxWidth: 660, margin: "0 auto", paddingBottom: 60 }}>
        {/* Profile Header */}
        <div className="prof-hdr">
          <div className="prof-av">{initials}</div>
          <div>
            <div className="prof-name">{user.name || "User"}</div>
            <div className="prof-em">{user.email}</div>
            {isPro ? (
              <div className="probadge">
                <Crown size={11} style={{ marginRight: 4 }} />
                Pro member
              </div>
            ) : (
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  fontSize: 11,
                  fontWeight: 600,
                  color: "var(--ink3)",
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
          <div style={{ marginTop: 24, marginBottom: 8 }} className="slbl">
            Account
          </div>
          <ul className="slist">
            <li className="sitem" onClick={() => router.push("/settings?tab=edit")}>
              <div className="si-icon">
                <User size={15} />
              </div>
              <div className="si-lbl">Edit profile</div>
              <ChevronRight size={14} style={{ color: "var(--ink3)" }} />
            </li>
            
            <li className="sitem" onClick={() => router.push("/settings?tab=sub")}>
              <div className="si-icon">
                <Crown size={15} />
              </div>
              <div className="si-lbl">Subscription</div>
              <div className="si-val">
                {isPro ? "Pro · Renews Jul 2026" : "Free · Upgrade available"}
              </div>
            </li>

            <li className="sitem" onClick={() => router.push("/settings?tab=notif")}>
              <div className="si-icon">
                <Bell size={15} />
              </div>
              <div className="si-lbl">Notifications</div>
              <ChevronRight size={14} style={{ color: "var(--ink3)" }} />
            </li>
          </ul>

          {/* Preferences Section */}
          <div style={{ marginTop: 20, marginBottom: 8 }} className="slbl">
            Preferences
          </div>
          <ul className="slist">
            <li className="sitem" onClick={() => router.push("/settings?tab=topics")}>
              <div className="si-icon">
                <Grid size={15} />
              </div>
              <div className="si-lbl">Topics & categories</div>
              <div className="si-val">{categoriesLabel}</div>
            </li>

            <li className="sitem" onClick={() => router.push("/settings?tab=locs")}>
              <div className="si-icon">
                <Map size={15} />
              </div>
              <div className="si-lbl">Locations</div>
              <div className="si-val" style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {locationsLabel}
              </div>
            </li>

            <li className="sitem" onClick={() => router.push("/settings?tab=summary")}>
              <div className="si-icon">
                <BookOpen size={15} />
              </div>
              <div className="si-lbl">Default summary</div>
              <div className="si-val">{summaryLabel}</div>
            </li>

            <li className="sitem" onClick={() => router.push("/settings?tab=theme")}>
              <div className="si-icon">
                {theme === "dark" ? <Moon size={15} /> : <Sun size={15} />}
              </div>
              <div className="si-lbl">Theme</div>
              <div className="si-val" style={{ textTransform: "capitalize" }}>
                {theme || "light"}
              </div>
            </li>
          </ul>

          {/* Reading Section */}
          <div style={{ marginTop: 20, marginBottom: 8 }} className="slbl">
            Reading
          </div>
          <ul className="slist">
            <li className="sitem" onClick={() => router.push("/bookmarks")}>
              <div className="si-icon">
                <Bookmark size={15} />
              </div>
              <div className="si-lbl">Saved stories</div>
              <div className="si-val">
                {bookmarkCount} {bookmarkCount === 1 ? "story" : "stories"}
              </div>
            </li>
            <li className="sitem" onClick={() => router.push("/settings?tab=history")}>
              <div className="si-icon">
                <BookOpen size={15} />
              </div>
              <div className="si-lbl">Reading history</div>
              <ChevronRight size={14} style={{ color: "var(--ink3)" }} />
            </li>
          </ul>

          {/* Sign Out Button */}
          <div style={{ marginTop: 28, paddingBottom: 48 }}>
            <button
              onClick={handleLogout}
              disabled={isLoggingOut}
              style={{
                color: "var(--err)",
                fontSize: "14px",
                fontWeight: 500,
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: "10px 0",
                width: "100%",
                textAlign: "left",
              }}
            >
              {isLoggingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
