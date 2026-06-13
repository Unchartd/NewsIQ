"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Settings, User, Shield, AlertTriangle, Moon, Sun, Laptop, Mail, BellRing, Smartphone, Globe, Trash2, LogOut } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const { user, isAuthenticated, setUser } = useAuthStore();
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();

  // Load preferences
  const { data: preferences, isLoading } = useQuery({
    queryKey: ["user-preferences"],
    queryFn: async () => {
      const response = await apiClient.get("/users/preferences");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const [name, setName] = useState("");
  const [summaryType, setSummaryType] = useState<"one_line" | "short" | "detailed">("short");

  const [prevUser, setPrevUser] = useState(user);
  if (user !== prevUser) {
    setPrevUser(user);
    if (user?.name) setName(user.name);
  }

  const [prevPreferences, setPrevPreferences] = useState(preferences);
  if (preferences !== prevPreferences) {
    setPrevPreferences(preferences);
    if (preferences?.preferred_summary_type) {
      setSummaryType(preferences.preferred_summary_type);
    }
  }

  // Update Profile Mutation
  const updateProfileMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.patch("/users/profile", { name });
      return response.data;
    },
    onSuccess: (data) => {
      setUser(data);
      toast.success("Profile updated successfully!");
    },
    onError: () => {
      toast.error("Failed to update profile.");
    },
  });

  // Update Preferences Mutation
  const updatePrefsMutation = useMutation({
    mutationFn: async (updatedType: "one_line" | "short" | "detailed") => {
      await apiClient.patch("/users/preferences", {
        preferred_summary_type: updatedType,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      toast.success("Summary preference updated.");
    },
    onError: () => {
      toast.error("Failed to save preference.");
    },
  });

  // Delete Account Mutation
  const deleteAccountMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete("/users/account");
    },
    onSuccess: () => {
      toast.success("Account successfully deleted.");
      localStorage.removeItem("access_token");
      window.location.href = "/";
    },
    onError: () => {
      toast.error("Failed to delete account.");
    },
  });

  // Load Digest Subscriptions
  const { data: digestSubscriptions = [] } = useQuery({
    queryKey: ["digest-subscriptions"],
    queryFn: async () => {
      const response = await apiClient.get("/users/digests");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Load Active Sessions
  const { data: sessions = [], isLoading: isLoadingSessions, refetch: refetchSessions } = useQuery({
    queryKey: ["active-sessions"],
    queryFn: async () => {
      const response = await apiClient.get("/auth/sessions");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Revoke Session Mutation
  const revokeSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      await apiClient.delete(`/auth/sessions/${sessionId}`);
    },
    onSuccess: () => {
      toast.success("Session revoked successfully.");
      refetchSessions();
    },
    onError: () => {
      toast.error("Failed to revoke session.");
    },
  });

  // Logout All Devices Mutation
  const logoutAllMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/auth/logout-all");
    },
    onSuccess: () => {
      toast.success("Logged out from all devices.");
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    },
    onError: () => {
      toast.error("Failed to logout from all devices.");
    },
  });

  // Update Digest Mutation
  const updateDigestMutation = useMutation({
    mutationFn: async ({
      frequency,
      delivery_channel,
      enabled,
    }: {
      frequency: string;
      delivery_channel: string;
      enabled: boolean;
    }) => {
      await apiClient.patch("/users/digests", {
        frequency,
        delivery_channel,
        enabled,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["digest-subscriptions"] });
      toast.success("Digest subscription updated.");
    },
    onError: () => {
      toast.error("Failed to update digest subscription.");
    },
  });

  const isDigestEnabled = (frequency: string, delivery_channel: string) => {
    const sub = digestSubscriptions.find(
      (s: { frequency: string; delivery_channel: string; enabled: boolean }) =>
        s.frequency === frequency && s.delivery_channel === delivery_channel
    );
    return sub ? sub.enabled : false;
  };


  if (!isAuthenticated) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto py-16 text-center">
          <h2 className="text-xl font-bold text-foreground">Sign In Required</h2>
          <p className="text-muted-foreground text-sm mt-1 mb-6">
            Please sign in to access settings.
          </p>
          <Button render={<a href="/login" />} className="rounded-xl">
            Sign In
          </Button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6 pb-24">
        {/* Title */}
        <div className="flex items-center gap-2">
          <Settings className="w-6 h-6 text-primary" />
          <h1 className="text-2xl font-bold">Settings</h1>
        </div>

        {/* Profile Card */}
        <Card className="border-border/50 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <User className="w-4 h-4 text-muted-foreground" />
              Profile Settings
            </CardTitle>
            <CardDescription>Update your personal information.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground">Email</label>
              <Input value={user?.email || ""} disabled className="bg-muted/40 cursor-not-allowed rounded-xl" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className="rounded-xl" />
            </div>
          </CardContent>
          <CardFooter className="bg-secondary/20 py-3 flex justify-end">
            <Button
              onClick={() => updateProfileMutation.mutate()}
              disabled={updateProfileMutation.isPending}
              className="rounded-xl px-4"
            >
              {updateProfileMutation.isPending ? "Saving..." : "Save Profile"}
            </Button>
          </CardFooter>
        </Card>

        {/* Readability & Preferences Card */}
        <Card className="border-border/50 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4 text-muted-foreground" />
              Reading Preferences
            </CardTitle>
            <CardDescription>Configure your default AI summary depth and appearance.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Summary length */}
            <div className="space-y-3">
              <label className="text-xs font-semibold text-muted-foreground">Default Summary Type</label>
              <div className="grid grid-cols-3 gap-2">
                {(["one_line", "short", "detailed"] as const).map((type) => (
                  <Button
                    key={type}
                    variant={summaryType === type ? "default" : "outline"}
                    onClick={() => {
                      setSummaryType(type);
                      updatePrefsMutation.mutate(type);
                    }}
                    className="rounded-xl text-xs capitalize"
                  >
                    {type.replace("_", " ")}
                  </Button>
                ))}
              </div>
            </div>

            {/* Appearance Theme */}
            <div className="space-y-3">
              <label className="text-xs font-semibold text-muted-foreground">Appearance Mode</label>
              <div className="grid grid-cols-3 gap-2">
                <Button
                  variant={theme === "light" ? "default" : "outline"}
                  onClick={() => setTheme("light")}
                  className="rounded-xl text-xs flex items-center gap-1.5"
                >
                  <Sun className="w-3.5 h-3.5" /> Light
                </Button>
                <Button
                  variant={theme === "dark" ? "default" : "outline"}
                  onClick={() => setTheme("dark")}
                  className="rounded-xl text-xs flex items-center gap-1.5"
                >
                  <Moon className="w-3.5 h-3.5" /> Dark
                </Button>
                <Button
                  variant={theme === "system" ? "default" : "outline"}
                  onClick={() => setTheme("system")}
                  className="rounded-xl text-xs flex items-center gap-1.5"
                >
                  <Laptop className="w-3.5 h-3.5" /> System
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Digest & Notifications Preferences */}
        <Card className="border-border/50 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <BellRing className="w-4 h-4 text-muted-foreground" />
              Digest & Notification Preferences
            </CardTitle>
            <CardDescription>
              Choose when and where you want to receive aggregated AI digests.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              {/* Morning Digest */}
              <div className="flex items-center justify-between pb-3 border-b border-border/40">
                <div className="space-y-0.5">
                  <p className="text-xs font-semibold text-foreground">Morning Briefing</p>
                  <p className="text-[10px] text-muted-foreground">Receive a summary of yesterday&apos;s stories at 8:00 AM.</p>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="morning-in-app" className="text-[10px] text-muted-foreground">In-App</Label>
                    <Switch
                      id="morning-in-app"
                      checked={isDigestEnabled("morning", "in_app")}
                      onCheckedChange={(checked) =>
                        updateDigestMutation.mutate({
                          frequency: "morning",
                          delivery_channel: "in_app",
                          enabled: checked,
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="morning-email" className="text-[10px] text-muted-foreground">Email</Label>
                    <Switch
                      id="morning-email"
                      checked={isDigestEnabled("morning", "email")}
                      onCheckedChange={(checked) =>
                        updateDigestMutation.mutate({
                          frequency: "morning",
                          delivery_channel: "email",
                          enabled: checked,
                        })
                      }
                    />
                  </div>
                </div>
              </div>

              {/* Evening Digest */}
              <div className="flex items-center justify-between pb-3 border-b border-border/40">
                <div className="space-y-0.5">
                  <p className="text-xs font-semibold text-foreground">Evening Briefing</p>
                  <p className="text-[10px] text-muted-foreground">Receive a summary of today&apos;s events at 6:00 PM.</p>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="evening-in-app" className="text-[10px] text-muted-foreground">In-App</Label>
                    <Switch
                      id="evening-in-app"
                      checked={isDigestEnabled("evening", "in_app")}
                      onCheckedChange={(checked) =>
                        updateDigestMutation.mutate({
                          frequency: "evening",
                          delivery_channel: "in_app",
                          enabled: checked,
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="evening-email" className="text-[10px] text-muted-foreground">Email</Label>
                    <Switch
                      id="evening-email"
                      checked={isDigestEnabled("evening", "email")}
                      onCheckedChange={(checked) =>
                        updateDigestMutation.mutate({
                          frequency: "evening",
                          delivery_channel: "email",
                          enabled: checked,
                        })
                      }
                    />
                  </div>
                </div>
              </div>

              {/* Weekly Digest */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <p className="text-xs font-semibold text-foreground">Weekly Digest</p>
                  <p className="text-[10px] text-muted-foreground">A curated digest of the week&apos;s major stories every Sunday.</p>
                </div>
                <div className="flex gap-4">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="weekly-in-app" className="text-[10px] text-muted-foreground">In-App</Label>
                    <Switch
                      id="weekly-in-app"
                      checked={isDigestEnabled("weekly", "in_app")}
                      onCheckedChange={(checked) =>
                        updateDigestMutation.mutate({
                          frequency: "weekly",
                          delivery_channel: "in_app",
                          enabled: checked,
                        })
                      }
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="weekly-email" className="text-[10px] text-muted-foreground">Email</Label>
                    <Switch
                      id="weekly-email"
                      checked={isDigestEnabled("weekly", "email")}
                      onCheckedChange={(checked) =>
                        updateDigestMutation.mutate({
                          frequency: "weekly",
                          delivery_channel: "email",
                          enabled: checked,
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Active Sessions Card */}
        <Card className="border-border/50 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4 text-muted-foreground" />
              Active Sessions & Security
            </CardTitle>
            <CardDescription>
              Manage the devices currently logged into your NewsIQ account.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoadingSessions ? (
              <div className="flex items-center justify-center py-6">
                <div className="w-6 h-6 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
              </div>
            ) : sessions.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-4">No active sessions found.</p>
            ) : (
              <div className="divide-y divide-border/40">
                {sessions.map((session: any) => {
                  const isCurrent = session.is_current;
                  return (
                    <div key={session.id} className="py-3.5 flex items-center justify-between first:pt-0 last:pb-0">
                      <div className="flex items-start gap-3">
                        <div className="mt-0.5 p-2 rounded-lg bg-secondary/30 text-muted-foreground">
                          {session.device_name?.toLowerCase().includes("phone") || session.device_name?.toLowerCase().includes("mobile") ? (
                            <Smartphone className="w-4 h-4" />
                          ) : (
                            <Laptop className="w-4 h-4" />
                          )}
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-foreground">
                              {session.device_name || "Unknown Device"}
                            </span>
                            {isCurrent && (
                              <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/15 border-0 rounded-full px-2 py-0 text-[10px] font-medium">
                                Current Session
                              </Badge>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Globe className="w-3 h-3" />
                              {session.ip_address || "Unknown IP"}
                            </span>
                            <span>•</span>
                            <span>Last active: {new Date(session.last_used_at).toLocaleString()}</span>
                          </div>
                        </div>
                      </div>
                      
                      {!isCurrent && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (confirm("Are you sure you want to revoke this session? You will be logged out on that device.")) {
                              revokeSessionMutation.mutate(session.id);
                            }
                          }}
                          disabled={revokeSessionMutation.isPending}
                          className="rounded-xl text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/5 px-2.5 h-8 flex items-center gap-1.5"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          Revoke
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
          <CardFooter className="bg-secondary/20 py-3 flex justify-between items-center">
            <span className="text-[10px] text-muted-foreground">
              Revoking a session immediately invalidates its tokens.
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (confirm("Are you sure you want to logout from all devices? All active sessions (including this one) will be revoked.")) {
                  logoutAllMutation.mutate();
                }
              }}
              disabled={logoutAllMutation.isPending}
              className="rounded-xl text-xs border-destructive/20 text-destructive hover:bg-destructive/5 hover:text-destructive flex items-center gap-1.5 h-8"
            >
              <LogOut className="w-3.5 h-3.5" />
              Logout All Devices
            </Button>
          </CardFooter>
        </Card>

        {/* Danger Zone */}
        <Card className="border-destructive/20 bg-destructive/5 rounded-2xl">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-destructive flex items-center gap-2">
              <AlertTriangle className="w-4 h-4" />
              Danger Zone
            </CardTitle>
            <CardDescription className="text-destructive/80">
              Operations here are permanent and cannot be undone.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground leading-normal mb-4">
              Deactivating your account will immediately revoke all access, delete your reading history, and clear your preferences.
            </p>
          </CardContent>
          <CardFooter className="border-t border-destructive/10 bg-destructive/10 py-3.5 flex justify-end">
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm("Are you absolutely sure you want to deactivate your NewsIQ account? This cannot be undone.")) {
                  deleteAccountMutation.mutate();
                }
              }}
              disabled={deleteAccountMutation.isPending}
              className="rounded-xl"
            >
              {deleteAccountMutation.isPending ? "Deleting..." : "Deactivate Account"}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </AppShell>
  );
}
