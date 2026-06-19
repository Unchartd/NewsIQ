"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { useTheme } from "next-themes";
import { AppShell } from "@/components/layout/app-shell";
import { SidebarWidgets } from "@/components/sidebar/sidebar-widgets";
import type { Story } from "@/types";
import {
  User,
  Crown,
  Bell,
  Grid,
  MapPin,
  BookOpen,
  Sun,
  History,
  Lock,
  Shield,
  Download,
  RotateCcw,
  AlertTriangle,
} from "lucide-react";
import { useConsent } from "@/components/legal/consent-provider";

// Toast Notification type
interface Toast {
  id: string;
  msg: string;
  type: "s" | "w" | "e"; // Success, Warning, Error
}

// Mock Notifications type
interface MockNotification {
  id: string;
  title: string;
  meta: string;
  type: "break" | "trend" | "digest" | "sys";
  unread: boolean;
}

// Mock History Item type
interface MockHistoryItem {
  id: string;
  num: number;
  title: string;
  category: string;
  catClass: string;
  sources: string;
  time: string;
  isToday: boolean;
}

const DEFAULT_NOTIFICATIONS: MockNotification[] = [
  {
    id: "n1",
    title: "India Supreme Court delivers landmark verdict on electoral bonds — 9 sources now covering",
    meta: "Breaking news · 4 minutes ago",
    type: "break",
    unread: true,
  },
  {
    id: "n2",
    title: 'Story you bookmarked is trending: "OpenAI GPT-5 release" now has 12 sources',
    meta: "Trending alert · 38 minutes ago",
    type: "trend",
    unread: true,
  },
  {
    id: "n3",
    title: "Your Morning Digest is ready — 10 top stories for today",
    meta: "Morning digest · Today, 7:00 AM",
    type: "digest",
    unread: false,
  },
  {
    id: "n4",
    title: "RBI holds repo rate at 6.5% for seventh consecutive meeting",
    meta: "Breaking news · Yesterday, 2:14 PM",
    type: "break",
    unread: false,
  },
  {
    id: "n5",
    title: "New feature: Story timelines now show source-level attribution on each event",
    meta: "Product update · 2 days ago",
    type: "sys",
    unread: false,
  },
  {
    id: "n6",
    title: "Your Weekly Summary is ready — biggest stories of the week",
    meta: "Weekly digest · Sun, Jun 8",
    type: "digest",
    unread: false,
  },
];

const DEFAULT_HISTORY: MockHistoryItem[] = [
  {
    id: "h1",
    num: 1,
    title: "OpenAI releases GPT-5 with 40% reasoning improvement and native multimodal capabilities",
    category: "Technology",
    catClass: "bt",
    sources: "12 sources",
    time: "43 min ago",
    isToday: true,
  },
  {
    id: "h2",
    num: 2,
    title: "Parliament session extended two weeks as opposition demands debate on data protection bill",
    category: "Politics",
    catClass: "bp",
    sources: "7 sources",
    time: "1h ago",
    isToday: true,
  },
  {
    id: "h3",
    num: 3,
    title: "RBI holds repo rate at 6.5% for seventh consecutive meeting, signals cautious stance",
    category: "Business",
    catClass: "bb",
    sources: "9 sources",
    time: "2h ago",
    isToday: true,
  },
  {
    id: "h4",
    num: 4,
    title: "WHO declares end to mpox public health emergency after global cases drop 82%",
    category: "Health",
    catClass: "bh",
    sources: "11 sources",
    time: "5h ago",
    isToday: true,
  },
  {
    id: "h5",
    num: 5,
    title: "Ukraine–Russia ceasefire talks resume in Istanbul with US and EU mediators present",
    category: "World",
    catClass: "bwl",
    sources: "18 sources",
    time: "Jun 13",
    isToday: false,
  },
  {
    id: "h6",
    num: 6,
    title: "Bengaluru monsoon rains flood Outer Ring Road; all schools ordered closed Friday",
    category: "Weather",
    catClass: "bw",
    sources: "6 sources",
    time: "Jun 13",
    isToday: false,
  },
  {
    id: "h7",
    num: 7,
    title: "India advances to semi-final in ICC Men's Champions Trophy after win over Australia",
    category: "Sports",
    catClass: "bs",
    sources: "9 sources",
    time: "Jun 13",
    isToday: false,
  },
];

const TAB_ICONS: Record<string, React.ComponentType<{ size?: number }>> = {
  edit: User,
  sub: Crown,
  notif: Bell,
  topics: Grid,
  locs: MapPin,
  summary: BookOpen,
  theme: Sun,
  history: History,
  security: Lock,
  privacy: Shield,
};

let hasHydratedSettings = false;

function SettingsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();
  const { user, isAuthenticated, setUser, logout: storeLogout } = useAuthStore();

  const {
    essentialEnabled,
    functionalEnabled,
    analyticsEnabled,
    marketingEnabled,
    region,
    consentVersion,
    updateConsent,
    withdrawConsent,
  } = useConsent();

  const [activeTab, setActiveTab] = useState<string>("edit");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [openModal, setOpenModal] = useState<string | null>(null);
  const [mounted, setMounted] = useState(hasHydratedSettings);

  useEffect(() => {
    hasHydratedSettings = true;
    setMounted(true);
  }, []);

  // Sync tab state with URL parameter
  useEffect(() => {
    if (tabParam && ["edit", "sub", "notif", "topics", "locs", "summary", "theme", "history", "security", "privacy"].includes(tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  // Toast notifier function
  const triggerToast = (msg: string, type: "s" | "w" | "e" = "s") => {
    const id = Math.random().toString();
    setToasts((prev) => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  };

  // Queries & Mutations
  const { data: preferences, isLoading: isLoadingPrefs } = useQuery({
    queryKey: ["user-preferences"],
    queryFn: async () => {
      const response = await apiClient.get("/users/preferences");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Query trending stories for the sidebar
  const { data: trendingStories = [], isLoading: isTrendingLoading } = useQuery<Story[]>({
    queryKey: ["stories", "trending-sidebar"],
    queryFn: async () => {
      const response = await apiClient.get("/stories", {
        params: {
          trending: "true",
          limit: 4,
        },
      });
      return response.data;
    },
  });

  const { data: digestSubscriptions = [], isLoading: isLoadingDigests } = useQuery({
    queryKey: ["digest-subscriptions"],
    queryFn: async () => {
      const response = await apiClient.get("/users/digests");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  const { data: sessions = [], refetch: refetchSessions } = useQuery({
    queryKey: ["active-sessions"],
    queryFn: async () => {
      const response = await apiClient.get("/auth/sessions");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Fetch recent notifications
  const { data: notifications = [], refetch: refetchNotifs } = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const response = await apiClient.get("/users/notifications");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Fetch reading history
  const { data: historyItems = [], refetch: refetchHistory } = useQuery({
    queryKey: ["reading-history"],
    queryFn: async () => {
      const response = await apiClient.get("/users/history");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Profile update mutation
  const updateProfileMutation = useMutation({
    mutationFn: async (updatedName: string) => {
      const response = await apiClient.patch("/users/profile", { name: updatedName });
      return response.data;
    },
    onSuccess: (data) => {
      setUser(data);
      triggerToast("Profile saved", "s");
    },
    onError: () => {
      triggerToast("Failed to save profile", "e");
    },
  });

  // Preferences update mutation
  const updatePrefsMutation = useMutation({
    mutationFn: async (payload: {
      preferred_summary_type?: string;
      theme?: string;
      language?: string;
      categories?: string[];
      countries?: string[];
      cities?: string[];
      ui_settings?: any;
    }) => {
      const response = await apiClient.patch("/users/preferences", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
    },
    onError: () => {
      triggerToast("Failed to update preferences", "e");
    },
  });

  // Digest subscription update mutation
  const updateDigestMutation = useMutation({
    mutationFn: async (payload: { frequency: string; delivery_channel?: string; enabled: boolean }) => {
      const response = await apiClient.patch("/users/digests", payload);
      return response.data;
    },
    onSuccess: () => {
      // Invalidate both so the notifications tab toggles AND the digest setup page stay in sync
      queryClient.invalidateQueries({ queryKey: ["digest-subscriptions"] });
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      triggerToast("Digest subscription updated", "s");
    },
    onError: () => {
      triggerToast("Failed to update digest subscription", "e");
    },
  });

  // Revoke session mutation
  const revokeSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      await apiClient.delete(`/auth/sessions/${sessionId}`);
    },
    onSuccess: () => {
      triggerToast("Session revoked", "w");
      refetchSessions();
    },
    onError: () => {
      triggerToast("Failed to revoke session", "e");
    },
  });

  // Logout all sessions mutation
  const logoutAllMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/auth/logout-all");
    },
    onSuccess: () => {
      triggerToast("All other sessions signed out", "w");
      storeLogout();
      router.push("/login");
    },
    onError: () => {
      triggerToast("Failed to logout other sessions", "e");
    },
  });

  // Delete account mutation
  const deleteAccountMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete("/users/account");
    },
    onSuccess: () => {
      triggerToast("Account deleted", "e");
      storeLogout();
      router.push("/");
    },
    onError: () => {
      triggerToast("Failed to delete account", "e");
    },
  });

  // Mark notification as read mutation
  const markReadMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.patch(`/users/notifications/${id}/read`);
    },
    onSuccess: () => {
      refetchNotifs();
    },
  });

  // Mark all notifications as read mutation
  const markAllReadMutation = useMutation({
    mutationFn: async () => {
      await apiClient.patch("/users/notifications/read-all");
    },
    onSuccess: () => {
      refetchNotifs();
      triggerToast("All notifications marked as read", "s");
    },
  });

  // Remove history item mutation
  const removeHistoryMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/users/history/${id}`);
    },
    onSuccess: () => {
      refetchHistory();
      triggerToast("Removed from history", "w");
    },
  });

  // Clear all history mutation
  const clearHistoryMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete("/users/history");
    },
    onSuccess: () => {
      refetchHistory();
      triggerToast("History cleared", "w");
    },
  });

  // Change password mutation
  const changePasswordMutation = useMutation({
    mutationFn: async (payload: any) => {
      const response = await apiClient.post("/auth/change-password", payload);
      return response.data;
    },
    onSuccess: () => {
      triggerToast("Password updated successfully", "s");
      setNewPassword("");
      setCurrentPassword("");
      setConfirmPassword("");
      setPwdStrengthScore(0);
    },
    onError: (error: any) => {
      const msg = error.response?.data?.detail || "Failed to update password";
      triggerToast(msg, "e");
    },
  });

  // Upgrade/Cancel plan mutations
  const upgradeSubMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post("/users/subscription/upgrade");
      return response.data;
    },
    onSuccess: (data) => {
      setUser(data);
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      triggerToast("Upgraded to NewsIQ Pro!", "s");
    },
  });

  const cancelSubMutation = useMutation({
    mutationFn: async () => {
      const response = await apiClient.post("/users/subscription/cancel");
      return response.data;
    },
    onSuccess: (data) => {
      setUser(data);
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      triggerToast("Subscription cancelled", "w");
    },
  });

  // Clear personalization
  const clearPersonalisationMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/users/clear-personalisation");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-preferences"] });
      queryClient.invalidateQueries({ queryKey: ["reading-history"] });
      triggerToast("Personalisation data cleared", "w");
    },
  });

  // Screen Nav switcher
  const go = (tabName: string) => {
    setActiveTab(tabName);
    router.push(`/settings?tab=${tabName}`);
  };

  // Switch between Dark/Light/System theme
  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    updatePrefsMutation.mutate({ theme: nextTheme });
    triggerToast(`${nextTheme.charAt(0).toUpperCase() + nextTheme.slice(1)} theme applied`, "s");
  };

  const handleThemeModeSelection = (mode: string) => {
    setTheme(mode);
    updatePrefsMutation.mutate({ theme: mode });
    triggerToast(`${mode.charAt(0).toUpperCase() + mode.slice(1)} theme applied`, "s");
  };

  // Helper to resolve digest status
  const isDigestEnabled = (frequency: string, deliveryChannel: string) => {
    const sub = digestSubscriptions.find(
      (s: { frequency: string; delivery_channel: string; enabled: boolean }) =>
        s.frequency === frequency && s.delivery_channel === deliveryChannel
    );
    return sub ? sub.enabled : false;
  };

  // --- LOCAL STATES ---
  // Tab 1: Edit Profile
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [phone, setPhone] = useState("");
  const [lang, setLang] = useState("English");
  const [dateTimeFormat, setDateTimeFormat] = useState("DD/MM/YYYY · 24-hour");

  // Tab 3: Notifications Preferences
  const [breakingNewsAlerts, setBreakingNewsAlerts] = useState(true);
  const [trendingStoryAlerts, setTrendingStoryAlerts] = useState(true);
  const [productUpdates, setProductUpdates] = useState(false);
  const [pushNotifications, setPushNotifications] = useState(true);

  // Tab 4: Topics
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [boostSelected, setBoostSelected] = useState(true);
  const [showAllTrending, setShowAllTrending] = useState(true);

  // Tab 5: Locations
  const [countries, setCountries] = useState<string[]>([]);
  const [cities, setCities] = useState<string[]>([]);
  const [prioritiseLocal, setPrioritiseLocal] = useState(true);
  const [includeStateNews, setIncludeStateNews] = useState(true);
  const [locSearchQuery, setLocSearchQuery] = useState("");

  // Tab 6: Default Summary
  const [summaryLevel, setSummaryLevel] = useState<"one_line" | "short" | "detailed">("short");
  const [showSummaryOnCards, setShowSummaryOnCards] = useState(true);
  const [showAiLabel, setShowAiLabel] = useState(true);

  // Tab 7: Theme & Appearance
  const [fontSize, setFontSize] = useState("default");
  const [compactLayout, setCompactLayout] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  // Tab 8: Reading History
  const [historySearch, setHistorySearch] = useState("");

  // Tab 9: Security
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwdStrengthScore, setPwdStrengthScore] = useState(0);
  const [totp2Fa, setTotp2Fa] = useState(true);
  const [email2Fa, setEmail2Fa] = useState(false);

  // Tab 10: Privacy
  const [personaliseHistory, setPersonaliseHistory] = useState(true);
  const [personaliseDigest, setPersonaliseDigest] = useState(true);
  const [trackClick, setTrackClick] = useState(true);
  const [shareUsage, setShareUsage] = useState(true);
  const [uxResearch, setUxResearch] = useState(false);

  // Hydration Effect from Backend Preferences
  useEffect(() => {
    if (user?.name) {
      const parts = user.name.split(" ");
      setFirstName(parts[0] || "");
      setLastName(parts.slice(1).join(" ") || "");
      setDisplayName(user.name);
    }
    if (preferences) {
      const ui = preferences.ui_settings || {};
      setBio(ui.bio ?? "Founder, tech enthusiast, based in Bengaluru.");
      setPhone(ui.phone ?? "");
      setLang(ui.lang ?? "English");
      setDateTimeFormat(ui.dateTimeFormat ?? "DD/MM/YYYY · 24-hour");

      setBreakingNewsAlerts(ui.breakingNewsAlerts ?? true);
      setTrendingStoryAlerts(ui.trendingStoryAlerts ?? true);
      setProductUpdates(ui.productUpdates ?? false);
      setPushNotifications(ui.pushNotifications ?? true);

      setBoostSelected(ui.boostSelected ?? true);
      setShowAllTrending(ui.showAllTrending ?? true);

      setPrioritiseLocal(ui.prioritiseLocal ?? true);
      setIncludeStateNews(ui.includeStateNews ?? true);

      setShowSummaryOnCards(ui.showSummaryOnCards ?? true);
      setShowAiLabel(ui.showAiLabel ?? true);

      setFontSize(ui.fontSize ?? "default");
      setCompactLayout(ui.compactLayout ?? false);
      setReduceMotion(ui.reduceMotion ?? false);

      setTotp2Fa(ui.totp2Fa ?? true);
      setEmail2Fa(ui.email2Fa ?? false);

      setPersonaliseHistory(ui.personaliseHistory ?? true);
      setPersonaliseDigest(ui.personaliseDigest ?? true);
      setTrackClick(ui.trackClick ?? true);
      setShareUsage(ui.shareUsage ?? true);
      setUxResearch(ui.uxResearch ?? false);
    }
    if (preferences?.categories) {
      setSelectedTopics(preferences.categories);
    }
    if (preferences?.countries) setCountries(preferences.countries);
    if (preferences?.cities) setCities(preferences.cities);
    if (preferences?.preferred_summary_type) {
      setSummaryLevel(preferences.preferred_summary_type as any);
    }
  }, [preferences, user]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("text-sz-small", "text-sz-large");
    if (fontSize === "small") root.classList.add("text-sz-small");
    if (fontSize === "large") root.classList.add("text-sz-large");

    if (reduceMotion) {
      root.classList.add("reduce-motion");
    } else {
      root.classList.remove("reduce-motion");
    }
  }, [fontSize, reduceMotion]);

  const saveProfile = () => {
    if (!firstName.trim() || !lastName.trim()) {
      triggerToast("First and last name are required", "e");
      return;
    }
    const combinedName = `${firstName.trim()} ${lastName.trim()}`;
    updateProfileMutation.mutate(combinedName);
    
    updatePrefsMutation.mutate({
      ui_settings: {
        bio,
        phone,
        lang,
        dateTimeFormat,
      }
    });
  };

  const discardProfileChanges = () => {
    if (user?.name) {
      const parts = user.name.split(" ");
      setFirstName(parts[0] || "");
      setLastName(parts.slice(1).join(" ") || "");
      setDisplayName(user.name);
    }
    if (preferences?.ui_settings) {
      const ui = preferences.ui_settings;
      setBio(ui.bio ?? "Founder, tech enthusiast, based in Bengaluru.");
      setPhone(ui.phone ?? "");
      setLang(ui.lang ?? "English");
      setDateTimeFormat(ui.dateTimeFormat ?? "DD/MM/YYYY · 24-hour");
    }
    triggerToast("Changes discarded", "w");
  };

  // Helper to save a single UI toggle state directly
  const handleUiToggleChange = (key: string, val: boolean, setter: (v: boolean) => void) => {
    setter(val);
    updatePrefsMutation.mutate({
      ui_settings: {
        [key]: val
      }
    });
  };

  const toggleTopic = (slug: string) => {
    setSelectedTopics((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  };

  const saveTopics = () => {
    updatePrefsMutation.mutate({
      categories: selectedTopics,
      ui_settings: {
        boostSelected,
        showAllTrending,
      }
    });
    triggerToast("Topics saved", "s");
  };

  const resetTopicsDefault = () => {
    setSelectedTopics(["politics", "technology"]);
    triggerToast("Reset to defaults", "w");
  };

  const removeCountry = (code: string) => {
    const updated = countries.filter((c) => c !== code);
    setCountries(updated);
    updatePrefsMutation.mutate({ countries: updated });
    triggerToast(`${code === "IN" ? "India" : code} removed`, "w");
  };

  const removeCity = (cityName: string) => {
    const updated = cities.filter((c) => c !== cityName);
    setCities(updated);
    updatePrefsMutation.mutate({ cities: updated });
    triggerToast(`${cityName} removed`, "w");
  };

  const addLocation = (type: "country" | "city", val: string) => {
    if (type === "country") {
      if (!countries.includes(val)) {
        const updated = [...countries, val];
        setCountries(updated);
        updatePrefsMutation.mutate({ countries: updated });
        triggerToast("Location added", "s");
      }
    } else {
      if (!cities.includes(val)) {
        const updated = [...cities, val];
        setCities(updated);
        updatePrefsMutation.mutate({ cities: updated });
        triggerToast("Location added", "s");
      }
    }
    setOpenModal(null);
  };

  const saveLocationSettings = () => {
    updatePrefsMutation.mutate({
      ui_settings: {
        prioritiseLocal,
        includeStateNews,
      }
    });
    triggerToast("Locations saved", "s");
  };

  const saveSummaryPreference = () => {
    updatePrefsMutation.mutate({
      preferred_summary_type: summaryLevel,
      ui_settings: {
        showSummaryOnCards,
        showAiLabel,
      }
    });
    triggerToast("Summary preference saved", "s");
  };

  const getSummaryPreviewText = () => {
    if (summaryLevel === "one_line") {
      return "GPT-5 scores 40% higher on reasoning benchmarks than GPT-4 Turbo.";
    } else if (summaryLevel === "short") {
      return "OpenAI launched GPT-5, its most capable model to date, scoring 40% higher on MMLU reasoning benchmarks than GPT-4 Turbo. Enterprise access is available at $60 per million tokens; consumer rollout begins in two weeks.";
    } else {
      return "OpenAI officially launched GPT-5 at 9:00 AM PT today, marking the company's most significant model release since GPT-4 Turbo in 2023. GPT-5 scored 40% higher on MMLU benchmarks and introduces native multimodal capabilities — accepting voice, image, document, and text inputs simultaneously — supporting 12 languages at launch. Enterprise pricing is set at $60 per million tokens, with a consumer rollout planned two weeks post-launch. Google DeepMind has not confirmed a competing release date.";
    }
  };

  const saveAppearance = () => {
    updatePrefsMutation.mutate({
      ui_settings: {
        fontSize,
        compactLayout,
        reduceMotion,
      }
    });
    triggerToast("Appearance saved", "s");
  };

  const filteredHistory = historyItems.filter((item: any) =>
    item.title.toLowerCase().includes(historySearch.toLowerCase())
  );

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setNewPassword(val);
    if (!val) {
      setPwdStrengthScore(0);
      return;
    }
    const score = Math.min(
      4,
      [val.length >= 8, /[A-Z]/.test(val), /[0-9]/.test(val), /[^a-zA-Z0-9]/.test(val)].filter(Boolean).length
    );
    setPwdStrengthScore(score);
  };

  const getPwdMeterColor = (idx: number) => {
    const colors = ["var(--border)", "var(--err)", "var(--amber)", "var(--amber)", "var(--green)"];
    return idx <= pwdStrengthScore ? colors[pwdStrengthScore] : "var(--border)";
  };

  const handleUpdatePassword = () => {
    if (!currentPassword) {
      triggerToast("Please enter your current password", "e");
      return;
    }
    if (newPassword.length < 8) {
      triggerToast("New password must be at least 8 characters", "e");
      return;
    }
    if (newPassword !== confirmPassword) {
      triggerToast("New passwords do not match", "e");
      return;
    }
    changePasswordMutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
    });
  };

  const savePrivacySettings = () => {
    updatePrefsMutation.mutate({
      ui_settings: {
        personaliseHistory,
        personaliseDigest,
        trackClick,
        shareUsage,
        uxResearch,
      }
    });
    triggerToast("Privacy settings saved", "s");
  };

  const handleExportData = async () => {
    try {
      triggerToast("Preparing export...", "s");
      const response = await apiClient.get("/users/export-data");
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(response.data, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `newsiq-user-data.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      triggerToast("Data exported successfully", "s");
    } catch (err) {
      triggerToast("Failed to export data", "e");
    }
  };

  // Wait for client-side hydration to restore auth store state
  if (!mounted) {
    return (
      <div className="min-h-screen bg-[var(--surface)] text-[var(--ink)] flex items-center justify-center font-sans">
        <div style={{ fontSize: 14, color: "var(--ink3)" }}>Loading...</div>
      </div>
    );
  }

  // Handle redirect to login if unauthenticated
  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto py-32 text-center px-4 font-sans text-[var(--ink)]">
        <h2 className="text-xl font-bold mb-2">Sign In Required</h2>
        <p className="text-sm text-[var(--ink3)] mb-6">
          Please sign in to access settings.
        </p>
        <button
          onClick={() => router.push("/login")}
          className="btnp"
          style={{ width: "100%", justifyContent: "center" }}
        >
          Sign In
        </button>
      </div>
    );
  }

  // Helper to determine Title label
  const tabLabelMap: Record<string, string> = {
    edit: "Edit Profile",
    sub: "Subscription",
    notif: "Notifications",
    topics: "Topics & Categories",
    locs: "Locations",
    summary: "Default Summary",
    theme: "Theme",
    history: "Reading History",
    security: "Security",
    privacy: "Privacy",
  };
  const tabLabel = tabLabelMap[activeTab] || "Edit Profile";

  const renderActiveScreen = () => {
    switch (activeTab) {
      case "edit":
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Edit Profile</div>
              <div className="page-hdr-sub">Update your name, photo, and personal details</div>
            </div>

            {/* Avatar card */}
            <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
              <div className="av-editor">
                <div className="av-lg" onClick={() => triggerToast("Photo upload coming soon", "w")}>
                  {firstName ? firstName[0].toUpperCase() : user?.email ? user.email[0].toUpperCase() : "A"}
                  <div className="av-overlay">
                    <svg width="20" height="20" style={{ color: "#fff" }}><use href="#i-cam" /></svg>
                  </div>
                </div>
                <div className="av-info">
                  <div className="av-name">{displayName || user?.name || "Aarav Mehta"}</div>
                  <div className="av-email">{user?.email || "aarav.mehta@gmail.com"}</div>
                  <div className="av-actions">
                    <button className="btno btnsm" onClick={() => triggerToast("Photo upload coming soon", "w")}>
                      <svg width="13" height="13"><use href="#i-cam" /></svg>Change photo
                    </button>
                    <button
                      className="btno btnsm"
                      onClick={() => triggerToast("Photo removed", "w")}
                      style={{ color: "var(--err)", borderColor: "rgba(220,38,38,.25)" }}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Personal info */}
            <div className="slbl">Personal Information</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div className="field">
                  <label className="field-label">First name</label>
                  <input
                    className="field-input"
                    type="text"
                    value={firstName}
                    onChange={(e) => {
                      setFirstName(e.target.value);
                      setDisplayName(`${e.target.value} ${lastName}`);
                    }}
                  />
                </div>
                <div className="field">
                  <label className="field-label">Last name</label>
                  <input
                    className="field-input"
                    type="text"
                    value={lastName}
                    onChange={(e) => {
                      setLastName(e.target.value);
                      setDisplayName(`${firstName} ${e.target.value}`);
                    }}
                  />
                </div>
              </div>
              <div className="field">
                <label className="field-label">Display name</label>
                <input
                  className="field-input"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                />
                <div className="field-hint">This is how your name appears on bookmarks and digests.</div>
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label className="field-label">Bio <span style={{ fontWeight: 400, color: "var(--ink3)" }}>(optional)</span></label>
                <textarea
                  className="field-input"
                  value={bio}
                  maxLength={160}
                  onChange={(e) => setBio(e.target.value)}
                />
                <div className="field-char"><span>{bio.length}</span>/160</div>
              </div>
            </div>

            {/* Contact */}
            <div className="slbl">Contact & Login</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
              <div className="field">
                <label className="field-label">Email address</label>
                <input
                  className="field-input"
                  type="email"
                  value={user?.email || ""}
                  disabled
                  style={{ cursor: "not-allowed", opacity: 0.7 }}
                />
                <div className="field-hint">Used for login, digest delivery, and account alerts.</div>
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label className="field-label">Phone number <span style={{ fontWeight: 400, color: "var(--ink3)" }}>(optional)</span></label>
                <input
                  className="field-input"
                  type="tel"
                  placeholder="+91 98765 43210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                />
                <div className="field-hint">Only used for WhatsApp digest delivery (Phase 2).</div>
              </div>
            </div>

            {/* Language */}
            <div className="slbl">Language & Region</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div className="field">
                <label className="field-label">Content language</label>
                <select className="field-input" style={{ cursor: "pointer" }} value={lang} onChange={(e) => setLang(e.target.value)}>
                  <option>English</option>
                  <option>Hindi</option>
                  <option>Kannada</option>
                  <option>Tamil</option>
                </select>
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label className="field-label">Date & time format</label>
                <select
                  className="field-input"
                  style={{ cursor: "pointer" }}
                  value={dateTimeFormat}
                  onChange={(e) => setDateTimeFormat(e.target.value)}
                >
                  <option>DD/MM/YYYY · 24-hour</option>
                  <option>MM/DD/YYYY · 12-hour</option>
                  <option>YYYY-MM-DD · 24-hour</option>
                </select>
              </div>
            </div>

            <div className="btn-row">
              <button className="btnp" onClick={saveProfile}>Save changes</button>
              <button className="btno" onClick={discardProfileChanges}>Discard</button>
            </div>
          </div>
        );

      case "sub": {
        const isPro = user?.subscription_plan === "pro";
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Subscription</div>
              <div className="page-hdr-sub">Manage your plan, billing, and payment details</div>
            </div>

            {/* Current plan card */}
            <div className="slbl">Current Plan</div>
            <div className="pcrd" style={{ marginBottom: 20 }}>
              <div className="plan-hdr">
                <div className="plan-name-row">
                  <div className="plan-crown"><svg width="18" height="18"><use href="#i-crown" /></svg></div>
                  <div>
                    <div className="plan-lbl">Active Plan</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div className="plan-val">{isPro ? "NewsIQ Pro" : "NewsIQ Free"}</div>
                      {isPro && (
                        <div className="plan-badge-pro">
                          <svg width="10" height="10"><use href="#i-crown" /></svg>Pro
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 22, fontWeight: 700, fontFamily: "var(--fd)", color: "var(--ink)" }}>
                    {isPro ? "₹399" : "₹0"}
                    <span style={{ fontSize: 14, fontWeight: 400, color: "var(--ink3)" }}>/mo</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>
                    {isPro ? "Renews July 14, 2026" : "Free Forever"}
                  </div>
                </div>
              </div>
              <div className="plan-stat-row">
                <div className="plan-stat">
                  <div className="plan-stat-lbl">Member since</div>
                  <div className="plan-stat-val">Jun 14, 2025</div>
                </div>
                <div className="plan-stat">
                  <div className="plan-stat-lbl">Next billing</div>
                  <div className="plan-stat-val">{isPro ? "Jul 14, 2026" : "N/A"}</div>
                </div>
                <div className="plan-stat">
                  <div className="plan-stat-lbl">Payment</div>
                  <div className="plan-stat-val">{isPro ? "•••• 4242" : "N/A"}</div>
                </div>
              </div>
            </div>

            {/* What's included */}
            <div className="slbl">What's Included</div>
            <div className="pcrd" style={{ marginBottom: 20 }}>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">Unlimited stories per day</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">All 3 summary depths (1-line, Short, Detailed)</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">Source Coverage table</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">Difference Engine — contradictions & gaps</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">Personalised feed based on reading habits</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">Daily digest — email delivery</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-check"><use href="#i-check" /></svg>
                <span className="feat-text">Ad-free reading experience</span>
              </div>
              <div className="feat-row">
                <svg width="14" height="14" className="feat-dash"><use href="#i-dash" /></svg>
                <span className="feat-text" style={{ color: "var(--ink3)" }}>AI Chat (Story Q&A)</span>
                <span className="feat-pro-tag">Coming in Phase 2</span>
              </div>
            </div>

            {!isPro && (
              <div className="pcrd pcrd-p" style={{ marginTop: 20, border: "1.5px solid var(--primary)", background: "rgba(196,30,58,.03)" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)" }}>Upgrade to NewsIQ Pro</div>
                    <div style={{ fontSize: 13, color: "var(--ink3)", marginTop: 4 }}>Get access to Difference Engine, Contradictions, daily digests, and more for ₹399/mo.</div>
                  </div>
                  <button
                    className="btnp"
                    disabled={upgradeSubMutation.isPending}
                    onClick={() => upgradeSubMutation.mutate()}
                    style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
                  >
                    <svg width="14" height="14"><use href="#i-crown" /></svg>
                    {upgradeSubMutation.isPending ? "Upgrading..." : "Upgrade to Pro"}
                  </button>
                </div>
              </div>
            )}

            {isPro && (
              <>
                {/* Payment method */}
                <div className="slbl">Payment Method</div>
                <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div
                      style={{
                        width: 48,
                        height: 32,
                        border: "1px solid var(--border)",
                        borderRadius: "var(--r4)",
                        background: "var(--surface)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 11,
                        fontWeight: 700,
                        color: "var(--ink3)",
                      }}
                    >
                      VISA
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>Visa ending in 4242</div>
                      <div style={{ fontSize: 12, color: "var(--ink3)" }}>Expires 09/2027</div>
                    </div>
                    <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                      <button className="btno btnsm" onClick={() => triggerToast("Payment update coming soon", "w")}>Update</button>
                    </div>
                  </div>
                </div>

                {/* Billing history */}
                <div className="slbl">Billing History</div>
                <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
                  <div className="bill-row">
                    <span className="bill-date">Jun 14, 2026</span>
                    <span className="bill-desc">NewsIQ Pro — Monthly</span>
                    <span className="bill-badge">Paid</span>
                    <span className="bill-amt">₹399</span>
                    <button
                      className="btno btnsm"
                      style={{ marginLeft: 8, fontSize: 11, padding: "3px 8px" }}
                      onClick={() => triggerToast("Invoice downloading…", "s")}
                    >
                      <svg width="12" height="12"><use href="#i-download" /></svg>
                    </button>
                  </div>
                  <div className="bill-row">
                    <span className="bill-date">May 14, 2026</span>
                    <span className="bill-desc">NewsIQ Pro — Monthly</span>
                    <span className="bill-badge">Paid</span>
                    <span className="bill-amt">₹399</span>
                    <button
                      className="btno btnsm"
                      style={{ marginLeft: 8, fontSize: 11, padding: "3px 8px" }}
                      onClick={() => triggerToast("Invoice downloading…", "s")}
                    >
                      <svg width="12" height="12"><use href="#i-download" /></svg>
                    </button>
                  </div>
                  <div className="bill-row">
                    <span className="bill-date">Apr 14, 2026</span>
                    <span className="bill-desc">NewsIQ Pro — Monthly</span>
                    <span className="bill-badge">Paid</span>
                    <span className="bill-amt">₹399</span>
                    <button
                      className="btno btnsm"
                      style={{ marginLeft: 8, fontSize: 11, padding: "3px 8px" }}
                      onClick={() => triggerToast("Invoice downloading…", "s")}
                    >
                      <svg width="12" height="12"><use href="#i-download" /></svg>
                    </button>
                  </div>
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
                    <a
                      href="#"
                      onClick={(e) => { e.preventDefault(); triggerToast("Redirecting to billing system", "s"); }}
                      style={{ fontSize: 13, color: "var(--blue)", fontWeight: 500, display: "flex", alignItems: "center", gap: 4 }}
                    >
                      View full billing history <svg width="12" height="12"><use href="#i-ext" /></svg>
                    </a>
                  </div>
                </div>

                {/* Cancel billing */}
                <div className="danger-zone">
                  <div className="dz-hdr">
                    <svg width="14" height="14" style={{ color: "var(--err)" }}><use href="#i-alert" /></svg>
                    <span className="dz-hdr-title">Subscription Actions</span>
                  </div>
                  <div className="dz-item">
                    <div className="dz-item-info">
                      <div className="dz-item-title">Cancel subscription</div>
                      <div className="dz-item-sub">Access continues until July 14, 2026. No refund for unused days.</div>
                    </div>
                    <button className="btn-danger btnsm" onClick={() => setOpenModal("cancelSub")}>Cancel plan</button>
                  </div>
                </div>
              </>
            )}
          </div>
        );
      }

      case "notif":
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Notifications</div>
              <div className="page-hdr-sub">Manage digest editions, alerts, and delivery preferences</div>
            </div>

            {/* ── DIGEST EDITIONS ── */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
              <div className="slbl" style={{ marginBottom: 0 }}>Digest Editions</div>
              <button
                className="btno btnsm"
                onClick={() => router.push("/digest/setup")}
                style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12 }}
              >
                <svg width="12" height="12"><use href="#i-news" /></svg>
                Full setup
              </button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 28 }}>
              {([
                { key: "morning", label: "Morning Digest", desc: "Top 10 stories. 3-minute read.", time: "Every day at 7 AM", icon: "🌅", accent: "var(--amber)", accentBg: "rgba(217,119,6,.06)" },
                { key: "midday",  label: "Midday Brief",   desc: "Quick catch-up on what's moving.", time: "Every day at 1 PM", icon: "☀️", accent: "var(--blue)", accentBg: "rgba(59,130,246,.06)" },
                { key: "evening", label: "Evening Wrap",   desc: "What you missed today.",          time: "Every day at 6 PM", icon: "🌆", accent: "var(--primary)", accentBg: "rgba(196,30,58,.05)" },
                { key: "weekly",  label: "Weekly Summary", desc: "Biggest stories of the week.",    time: "Every Sunday",     icon: "📋", accent: "var(--green)", accentBg: "rgba(22,163,74,.06)" },
              ] as const).map((ed) => {
                const isSubscribed = digestSubscriptions.some(
                  (s: { frequency: string }) => s.frequency === ed.key
                );
                const isEnabled = digestSubscriptions.some(
                  (s: { frequency: string; enabled: boolean }) =>
                    s.frequency === ed.key && s.enabled
                );
                const isBusy = isLoadingDigests || updateDigestMutation.isPending;
                const channels = digestSubscriptions
                  .filter((s: { frequency: string }) => s.frequency === ed.key)
                  .map((s: { delivery_channel: string }) => {
                    if (s.delivery_channel === "in_app") return "in-app";
                    return s.delivery_channel;
                  });
                const channelsText = channels.length > 0 ? `· via ${channels.join(" & ")}` : "· via email";

                return (
                  <div
                    key={ed.key}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 10,
                      padding: "16px 16px 14px",
                      borderRadius: "var(--r8)",
                      border: isSubscribed && isEnabled ? `1.5px solid color-mix(in srgb, ${ed.accent} 35%, transparent)` : "1.5px solid var(--border)",
                      background: isSubscribed && isEnabled ? ed.accentBg : "var(--card)",
                      transition: "border-color .2s, background .2s",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                        <span style={{ fontSize: 20, lineHeight: 1, flexShrink: 0 }}>{ed.icon}</span>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", lineHeight: 1.25 }}>{ed.label}</div>
                          <div style={{ fontSize: 11, color: "var(--ink3)", marginTop: 2 }}>{ed.time}</div>
                        </div>
                      </div>
                      {isSubscribed && (
                        <label className="toggle" style={{ flexShrink: 0, marginTop: 1 }}>
                          <input
                            type="checkbox"
                            checked={isEnabled}
                            disabled={isBusy}
                            onChange={(e) => updateDigestMutation.mutate({ frequency: ed.key, enabled: e.target.checked })}
                          />
                          <div className="tog-track"></div>
                          <div className="tog-thumb"></div>
                        </label>
                      )}
                    </div>

                    <div style={{ fontSize: 12, color: "var(--ink3)", lineHeight: 1.5 }}>{ed.desc}</div>

                    {isSubscribed ? (
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          fontSize: 11, fontWeight: 700, padding: "3px 8px", borderRadius: 99,
                          background: isEnabled ? "rgba(22,163,74,.12)" : "rgba(107,107,107,.1)",
                          color: isEnabled ? "var(--green)" : "var(--ink3)",
                        }}>
                          <svg width="6" height="6" viewBox="0 0 8 8" fill="currentColor"><circle cx="4" cy="4" r="4" /></svg>
                          {isEnabled ? "Active" : "Paused"}
                        </span>
                        <span style={{ fontSize: 11, color: "var(--ink3)" }}>{channelsText}</span>
                      </div>
                    ) : (
                      <button
                        className="btnp btnsm"
                        disabled={isBusy}
                        onClick={() => updateDigestMutation.mutate({ frequency: ed.key, enabled: true })}
                        style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, padding: "7px 13px", width: "fit-content", opacity: isBusy ? 0.6 : 1 }}
                      >
                        <svg width="12" height="12"><use href="#i-bell" /></svg>
                        Subscribe free
                      </button>
                    )}
                  </div>
                );
              })}
            </div>

            {/* ── ALERT PREFERENCES ── */}
            <div className="slbl" style={{ marginBottom: 12 }}>Alert Preferences</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 24 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 13 }}>⚡</span>Breaking news
                  </div>
                  <div className="tog-sub">Instant alert for top-tier stories (max 3/day)</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={breakingNewsAlerts} onChange={(e) => handleUiToggleChange("breakingNewsAlerts", e.target.checked, setBreakingNewsAlerts)} />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 13 }}>📈</span>Trending story alerts
                  </div>
                  <div className="tog-sub">When a story you follow spikes in coverage</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={trendingStoryAlerts} onChange={(e) => handleUiToggleChange("trendingStoryAlerts", e.target.checked, setTrendingStoryAlerts)} />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span style={{ fontSize: 13 }}>🔔</span>Product updates
                  </div>
                  <div className="tog-sub">New features, improvements, and announcements</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={productUpdates} onChange={(e) => handleUiToggleChange("productUpdates", e.target.checked, setProductUpdates)} />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            {/* ── DELIVERY CHANNELS ── */}
            <div className="slbl" style={{ marginBottom: 12 }}>Delivery Channels</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 24 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-bell" /></svg>
                    Push notifications
                  </div>
                  <div className="tog-sub">In-browser alerts — requires permission</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={pushNotifications} onChange={(e) => handleUiToggleChange("pushNotifications", e.target.checked, setPushNotifications)} />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-mail" /></svg>
                    Email
                  </div>
                  <div className="tog-sub">{user?.email || "—"}</div>
                </div>
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 99,
                  background: digestSubscriptions.some((s: { enabled: boolean }) => s.enabled) ? "rgba(22,163,74,.12)" : "rgba(107,107,107,.1)",
                  color: digestSubscriptions.some((s: { enabled: boolean }) => s.enabled) ? "var(--green)" : "var(--ink3)",
                }}>
                  {digestSubscriptions.some((s: { enabled: boolean }) => s.enabled) ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontSize: 14 }}>📱</span>
                    Telegram
                    <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 99, background: "rgba(107,107,107,.1)", color: "var(--ink3)" }}>
                      Not connected
                    </span>
                  </div>
                  <div className="tog-sub">Connect Telegram to receive your digest there</div>
                </div>
                <button className="btno btnsm" onClick={() => triggerToast("Telegram connection coming soon", "w")}>Connect</button>
              </div>
            </div>

            {/* ── RECENT NOTIFICATIONS ── */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div className="slbl" style={{ marginBottom: 0 }}>Recent Notifications</div>
              <button className="btno btnsm" onClick={() => markAllReadMutation.mutate()} style={{ fontSize: 11, padding: "3px 8px" }}>
                Mark all read
              </button>
            </div>
            <div className="pcrd" style={{ marginBottom: 28 }}>
              {notifications.map((notif: any) => {
                const type = notif.notification_type || "sys";
                const iconClass = type === "break" ? "ni-break" : type === "trend" ? "ni-trend" : type === "digest" ? "ni-digest" : "ni-sys";
                const iconHref = type === "break" ? "#i-zap" : type === "trend" ? "#i-trend" : type === "digest" ? "#i-news" : "#i-bell";
                const formattedTime = new Date(notif.created_at).toLocaleString();
                return (
                  <div
                    key={notif.id}
                    className={`notif-item ${!notif.is_read ? "unread" : ""}`}
                    onClick={() => {
                      if (!notif.is_read) {
                        markReadMutation.mutate(notif.id);
                      }
                    }}
                  >
                    <div className={`notif-icon ${iconClass}`}>
                      <svg width="14" height="14"><use href={iconHref} /></svg>
                    </div>
                    <div className="notif-body">
                      <div className="notif-title">{notif.title}</div>
                      <div className="notif-meta">{notif.body} · {formattedTime}</div>
                    </div>
                    {!notif.is_read && <div className="notif-unread-dot"></div>}
                  </div>
                );
              })}
            </div>
            <div style={{ textAlign: "center", fontSize: 13, color: "var(--ink3)" }}>
              You're all caught up ·{" "}
              <a href="#" onClick={(e) => { e.preventDefault(); triggerToast("Older notifications loaded", "s"); }} style={{ color: "var(--blue)" }}>
                Load older
              </a>
            </div>
          </div>
        );

      case "topics": {
        const availableCategories = [
          { slug: "politics", name: "Politics", icon: "🏛️" },
          { slug: "technology", name: "Technology", icon: "💻" },
          { slug: "business", name: "Business", icon: "📈" },
          { slug: "sports", name: "Sports", icon: "⚽" },
          { slug: "health", name: "Health", icon: "❤️" },
          { slug: "science", name: "Science", icon: "🔬" },
          { slug: "world", name: "World", icon: "🌍" },
          { slug: "weather", name: "Weather", icon: "🌦️" },
          { slug: "entertainment", name: "Entertainment", icon: "🎬" },
        ];

        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Topics & Categories</div>
              <div className="page-hdr-sub">Stories in selected topics appear first in your feed. Pick at least one.</div>
            </div>

            <div className="slbl">News Categories</div>
            <div className="chk-grid" style={{ marginBottom: 28 }} id="topicGrid">
              {availableCategories.map((cat) => {
                const isSelected = selectedTopics.includes(cat.slug);
                return (
                  <div
                    key={cat.slug}
                    className={`chk-opt ${isSelected ? "sel" : ""}`}
                    onClick={() => toggleTopic(cat.slug)}
                  >
                    <div className="chk-mark">
                      <svg width="9" height="9" style={{ color: "#fff" }}><use href="#i-check" /></svg>
                    </div>
                    <div className="chk-icon">{cat.icon}</div>
                    <div className="chk-name">{cat.name}</div>
                  </div>
                );
              })}
            </div>

            <div className="slbl">Feed Behaviour</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label">Boost selected topics</div>
                  <div className="tog-sub">Stories from your chosen categories appear at the top of the feed, even if they're not the most recent</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={boostSelected}
                    onChange={(e) => setBoostSelected(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label">Show all-category trending</div>
                  <div className="tog-sub">Include trending stories from topics outside your selection in the Trending tab</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={showAllTrending}
                    onChange={(e) => setShowAllTrending(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            <div className="btn-row">
              <button className="btnp" onClick={saveTopics}>Save preferences</button>
              <button className="btno" onClick={resetTopicsDefault}>Reset defaults</button>
            </div>
          </div>
        );
      }

      case "locs":
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Locations</div>
              <div className="page-hdr-sub">Stories from your added locations are prioritised in your feed</div>
            </div>

            <div className="slbl">Your Locations</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
              {countries.map((code) => (
                <div className="loc-item" key={code}>
                  <div className="loc-icon">{code === "IN" ? "🇮🇳" : "🌍"}</div>
                  <div style={{ flex: 1 }}>
                    <div className="loc-name">{code === "IN" ? "India" : code}</div>
                    <div className="loc-type">Country</div>
                  </div>
                  <button className="loc-remove" onClick={() => removeCountry(code)}>
                    <svg width="14" height="14"><use href="#i-x" /></svg>
                  </button>
                </div>
              ))}
              {cities.map((city) => (
                <div className="loc-item" key={city}>
                  <div className="loc-icon">🏙️</div>
                  <div style={{ flex: 1 }}>
                    <div className="loc-name">{city}</div>
                    <div className="loc-type">City · {city === "Bengaluru" ? "Karnataka, India" : "India"}</div>
                  </div>
                  <button className="loc-remove" onClick={() => removeCity(city)}>
                    <svg width="14" height="14"><use href="#i-x" /></svg>
                  </button>
                </div>
              ))}
              <div className="loc-add-btn" onClick={() => setOpenModal("addLoc")}>
                <svg width="16" height="16" style={{ color: "var(--blue)" }}><use href="#i-plus" /></svg>
                Add location
              </div>
            </div>

            <div className="slbl">Location Feed Settings</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label">Prioritise local stories</div>
                  <div className="tog-sub">Stories from your locations appear above national and world news</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={prioritiseLocal}
                    onChange={(e) => setPrioritiseLocal(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label">Include state/regional news</div>
                  <div className="tog-sub">Show stories from Karnataka, not just Bengaluru specifically</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={includeStateNews}
                    onChange={(e) => setIncludeStateNews(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            <div className="slbl">Location Hierarchy</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div style={{ fontSize: 13, color: "var(--ink3)", marginBottom: 14, lineHeight: 1.6 }}>
                Stories are matched to you at these levels, from most specific to broadest:
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", fontSize: 13, color: "var(--ink2)" }}>
                <span style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 99, fontWeight: 500 }}>Bengaluru</span>
                <span style={{ color: "var(--ink3)" }}>→</span>
                <span style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 99 }}>Karnataka</span>
                <span style={{ color: "var(--ink3)" }}>→</span>
                <span style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 99 }}>India</span>
                <span style={{ color: "var(--ink3)" }}>→</span>
                <span style={{ background: "var(--surface)", border: "1px solid var(--border)", padding: "4px 10px", borderRadius: 99 }}>World</span>
              </div>
            </div>

            <div className="btn-row">
              <button className="btnp" onClick={saveLocationSettings}>Save</button>
            </div>
          </div>
        );

      case "summary":
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Default Summary</div>
              <div className="page-hdr-sub">Choose how much you want to read by default. You can always switch per story.</div>
            </div>

            <div className="slbl">Summary Level</div>
            <div className="radio-group" style={{ marginBottom: 28 }}>
              <div className={`radio-opt ${summaryLevel === "one_line" ? "sel" : ""}`} onClick={() => setSummaryLevel("one_line")}>
                <div className="radio-circle"><div className="radio-dot"></div></div>
                <div className="radio-text">
                  <div className="radio-main">1-line</div>
                  <div className="radio-desc">~20 words · Just the core fact. Who, what, where.</div>
                </div>
              </div>
              <div className={`radio-opt ${summaryLevel === "short" ? "sel" : ""}`} onClick={() => setSummaryLevel("short")}>
                <div className="radio-circle"><div className="radio-dot"></div></div>
                <div className="radio-text">
                  <div className="radio-main">Short</div>
                  <div className="radio-desc">~50 words · Key facts with a bit of context. Good for most stories.</div>
                </div>
                <span className="radio-badge">Recommended</span>
              </div>
              <div className={`radio-opt ${summaryLevel === "detailed" ? "sel" : ""}`} onClick={() => setSummaryLevel("detailed")}>
                <div className="radio-circle"><div className="radio-dot"></div></div>
                <div className="radio-text">
                  <div className="radio-main">Detailed</div>
                  <div className="radio-desc">~150 words · Full context, background, and what to watch for next.</div>
                </div>
              </div>
            </div>

            {/* Live preview */}
            <div className="slbl">Preview</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".07em", color: "var(--ink3)", textTransform: "uppercase", marginBottom: 10, display: "flex", alignItems: "center", gap: 4 }}>
                <span style={{ fontSize: 12 }}>✦</span>AI Summary · {summaryLevel.replace("_", " ")}
              </div>
              <div style={{ fontSize: 15, color: "var(--ink2)", lineHeight: 1.7 }} id="prevSum">
                {getSummaryPreviewText()}
              </div>
            </div>

            <div className="slbl">Card Display</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label">Show summary on feed cards</div>
                  <div className="tog-sub">Display summary text on story cards in the feed, not just on the story page</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={showSummaryOnCards}
                    onChange={(e) => setShowSummaryOnCards(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label">Show AI label on summaries</div>
                  <div className="tog-sub">Display the ✦ AI Summary indicator on all AI-generated content</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={showAiLabel}
                    onChange={(e) => setShowAiLabel(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            <div className="btn-row">
              <button className="btnp" onClick={saveSummaryPreference}>Save preference</button>
            </div>
          </div>
        );

      case "theme":
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Appearance</div>
              <div className="page-hdr-sub">Choose how NewsIQ looks. Your preference is saved across devices.</div>
            </div>

            <div className="slbl">Colour Mode</div>
            <div className="theme-grid" style={{ marginBottom: 28 }}>
              {/* Light */}
              <div className={`theme-opt ${theme === "light" ? "sel" : ""}`} onClick={() => handleThemeModeSelection("light")}>
                <div className="theme-preview tp-light">
                  <div className="tp-bar" style={{ marginTop: 10, width: "60%" }}></div>
                  <div className="tp-card" style={{ marginTop: 6 }}></div>
                  <div className="tp-bar" style={{ width: "80%", marginTop: 5 }}></div>
                  <div className="tp-bar" style={{ width: "50%", marginTop: 4 }}></div>
                </div>
                <div className="theme-label">
                  Light
                  <div className="theme-check"><svg width="9" height="9" style={{ color: "#fff" }}><use href="#i-check" /></svg></div>
                </div>
              </div>
              {/* Dark */}
              <div className={`theme-opt ${theme === "dark" ? "sel" : ""}`} onClick={() => handleThemeModeSelection("dark")}>
                <div className="theme-preview tp-dark">
                  <div className="tp-bar tp-bar-dark" style={{ marginTop: 10, width: "60%" }}></div>
                  <div className="tp-card tp-card-dark" style={{ marginTop: 6 }}></div>
                  <div className="tp-bar tp-bar-dark" style={{ width: "80%", marginTop: 5 }}></div>
                  <div className="tp-bar tp-bar-dark" style={{ width: "50%", marginTop: 4 }}></div>
                </div>
                <div className="theme-label" style={{ background: "var(--card)" }}>
                  Dark
                  <div className="theme-check"><svg width="9" height="9" style={{ color: "#fff" }}><use href="#i-check" /></svg></div>
                </div>
              </div>
              {/* System */}
              <div className={`theme-opt ${theme === "system" ? "sel" : ""}`} onClick={() => handleThemeModeSelection("system")}>
                <div className="theme-preview tp-sys">
                  <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: "50%", padding: "10px 6px" }}>
                    <div className="tp-bar" style={{ width: "80%" }}></div>
                    <div className="tp-card" style={{ marginTop: 5, height: 22 }}></div>
                  </div>
                  <div style={{ position: "absolute", right: 0, top: 0, bottom: 0, width: "50%", padding: "10px 6px" }}>
                    <div className="tp-bar tp-bar-dark" style={{ width: "80%" }}></div>
                    <div className="tp-card tp-card-dark" style={{ marginTop: 5, height: 22 }}></div>
                  </div>
                </div>
                <div className="theme-label">
                  System
                  <div className="theme-check"><svg width="9" height="9" style={{ color: "#fff" }}><use href="#i-check" /></svg></div>
                </div>
              </div>
            </div>

            <div className="slbl">Font Size</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 24 }}>
              <div className="radio-group">
                <div className={`radio-opt ${fontSize === "small" ? "sel" : ""}`} onClick={() => setFontSize("small")}>
                  <div className="radio-circle"><div className="radio-dot"></div></div>
                  <div className="radio-text"><div className="radio-main" style={{ fontSize: 13 }}>Small</div></div>
                </div>
                <div className={`radio-opt ${fontSize === "default" ? "sel" : ""}`} onClick={() => setFontSize("default")}>
                  <div className="radio-circle"><div className="radio-dot"></div></div>
                  <div className="radio-text"><div className="radio-main">Default</div></div>
                  <span className="radio-badge">Recommended</span>
                </div>
                <div className={`radio-opt ${fontSize === "large" ? "sel" : ""}`} onClick={() => setFontSize("large")}>
                  <div className="radio-circle"><div className="radio-dot"></div></div>
                  <div className="radio-text"><div className="radio-main" style={{ fontSize: 17 }}>Large</div></div>
                </div>
              </div>
            </div>

            <div className="slbl">Reading Preferences</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label">Compact card layout</div>
                  <div className="tog-sub">Show more stories per screen by reducing card padding</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={compactLayout}
                    onChange={(e) => setCompactLayout(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label">Reduce motion</div>
                  <div className="tog-sub">Disable all transition animations and the Signal Bar pulse</div>
                </div>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={reduceMotion}
                    onChange={(e) => setReduceMotion(e.target.checked)}
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            <div className="btn-row">
              <button className="btnp" onClick={saveAppearance}>Save</button>
            </div>
          </div>
        );

      case "history":
        return (
          <div className="page-wide">
            <div className="page-hdr">
              <div className="page-hdr-title">Reading History</div>
              <div className="page-hdr-sub">Stories you've opened. Not shared with anyone.</div>
            </div>

            <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 20 }}>
              <div className="sch-box" style={{ flex: 1, maxWidth: 360 }}>
                <svg width="14" height="14" style={{ color: "var(--ink3)", flexShrink: 0 }}><use href="#i-search" /></svg>
                <input
                  type="text"
                  placeholder="Search your history…"
                  value={historySearch}
                  onChange={(e) => setHistorySearch(e.target.value)}
                />
              </div>
              <button
                className="btno btnsm"
                onClick={() => clearHistoryMutation.mutate()}
                style={{ color: "var(--err)", borderColor: "rgba(220,38,38,.25)" }}
              >
                Clear all
              </button>
            </div>

            {/* Today */}
            {filteredHistory.some((h: any) => h.isToday) && (
              <>
                <div className="slbl">Today</div>
                <div className="pcrd" style={{ marginBottom: 16 }}>
                  {filteredHistory
                    .filter((h: any) => h.isToday)
                    .map((item: any) => (
                      <div className="hist-item" key={item.id}>
                        <div className="hist-num">{item.num}</div>
                        <div className="hist-body">
                          <div className="hist-title">{item.title}</div>
                          <div className="hist-meta">
                            <span className={`cbadge ${item.catClass}`}>{item.category}</span>
                            <span>{item.sources}</span>
                            <span>{new Date(item.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          </div>
                        </div>
                        <button className="hist-remove" onClick={() => removeHistoryMutation.mutate(item.id)}>
                          <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-x" /></svg>
                        </button>
                      </div>
                    ))}
                </div>
              </>
            )}

            {/* Yesterday */}
            {filteredHistory.some((h: any) => !h.isToday) && (
              <>
                <div className="slbl">Older</div>
                <div className="pcrd" style={{ marginBottom: 16 }}>
                  {filteredHistory
                    .filter((h: any) => !h.isToday)
                    .map((item: any) => (
                      <div className="hist-item" key={item.id}>
                        <div className="hist-num">{item.num}</div>
                        <div className="hist-body">
                          <div className="hist-title">{item.title}</div>
                          <div className="hist-meta">
                            <span className={`cbadge ${item.catClass}`}>{item.category}</span>
                            <span>{item.sources}</span>
                            <span>{new Date(item.time).toLocaleDateString()}</span>
                          </div>
                        </div>
                        <button className="hist-remove" onClick={() => removeHistoryMutation.mutate(item.id)}>
                          <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-x" /></svg>
                        </button>
                      </div>
                    ))}
                </div>
              </>
            )}

            {/* Privacy note */}
            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r6)", padding: "14px 16px", display: "flex", gap: 10, marginBottom: 28 }}>
              <svg width="16" height="16" style={{ color: "var(--ink3)", flexShrink: 0, marginTop: 2 }}><use href="#i-lock" /></svg>
              <div style={{ fontSize: 13, color: "var(--ink3)", lineHeight: 1.6 }}>
                Your reading history is stored privately in the database. It's used only to personalise your feed — it is never sold, shared, or used for advertising.
              </div>
            </div>
          </div>
        );

      case "security":
        return (
          <div className="page">
            <div className="page-hdr">
              <div className="page-hdr-title">Security</div>
              <div className="page-hdr-sub">Manage your password, login sessions, and two-factor authentication</div>
            </div>

            <div className="slbl">Password</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
              <div className="field">
                <label className="field-label">Current password</label>
                <input
                  className="field-input"
                  type="password"
                  placeholder="Enter current password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
              </div>
              <div className="field">
                <label className="field-label">New password</label>
                <input
                  className="field-input"
                  type="password"
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={handlePasswordChange}
                />
                <div style={{ display: "flex", gap: 4, marginTop: 6 }} id="pwdMeter">
                  <div style={{ height: 3, flex: 1, borderRadius: 99, background: getPwdMeterColor(1) }}></div>
                  <div style={{ height: 3, flex: 1, borderRadius: 99, background: getPwdMeterColor(2) }}></div>
                  <div style={{ height: 3, flex: 1, borderRadius: 99, background: getPwdMeterColor(3) }}></div>
                  <div style={{ height: 3, flex: 1, borderRadius: 99, background: getPwdMeterColor(4) }}></div>
                </div>
              </div>
              <div className="field" style={{ marginBottom: 16 }}>
                <label className="field-label">Confirm new password</label>
                <input
                  className="field-input"
                  type="password"
                  placeholder="Repeat new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
              <button className="btnp btnsm" onClick={handleUpdatePassword} disabled={changePasswordMutation.isPending}>
                <svg width="13" height="13"><use href="#i-lock" /></svg>
                {changePasswordMutation.isPending ? "Updating..." : "Update password"}
              </button>
            </div>

            <div className="slbl">Two-Factor Authentication</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 20 }}>
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <svg width="14" height="14" style={{ color: "var(--green)" }}><use href="#i-shield" /></svg>Authenticator app (TOTP)
                  </div>
                  <div className="tog-sub">Use Google Authenticator, Authy, or any TOTP app</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={totp2Fa} onChange={(e) => handleUiToggleChange("totp2Fa", e.target.checked, setTotp2Fa)} />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <svg width="14" height="14" style={{ color: "var(--ink3)" }}><use href="#i-mail" /></svg>Email verification
                  </div>
                  <div className="tog-sub">Send a code to {user?.email || "aarav.mehta@gmail.com"} on new logins</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked={email2Fa} onChange={(e) => handleUiToggleChange("email2Fa", e.target.checked, setEmail2Fa)} />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            <div className="slbl">Active Sessions</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 28 }}>
              {sessions.map((session: any) => (
                <div
                  key={session.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    paddingBottom: 14,
                    borderBottom: "1px solid var(--border)",
                    marginBottom: 14,
                  }}
                  className="last:border-none last:pb-0 last:mb-0"
                >
                  <div
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: "var(--r6)",
                      background: "var(--surface)",
                      border: "1px solid var(--border)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 18,
                      flexShrink: 0,
                    }}
                  >
                    {session.device_name?.toLowerCase().includes("phone") ? "📱" : "💻"}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{session.device_name || "Device"}</div>
                    <div style={{ fontSize: 12, color: "var(--ink3)" }}>
                      {session.ip_address || "Unknown IP"} · {session.is_current ? "Active now" : new Date(session.last_used_at).toLocaleDateString()}
                    </div>
                  </div>
                  {session.is_current ? (
                    <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 7px", borderRadius: 99, background: "rgba(22,163,74,.1)", color: "var(--green)" }}>
                      Current
                    </span>
                  ) : (
                    <button
                      className="btno btnsm"
                      style={{ fontSize: 11, color: "var(--err)", borderColor: "rgba(220,38,38,.2)" }}
                      onClick={() => revokeSessionMutation.mutate(session.id)}
                    >
                      Revoke
                    </button>
                  )}
                </div>
              ))}
            </div>

            {/* Danger zone */}
            <div className="danger-zone">
              <div className="dz-hdr">
                <svg width="14" height="14" style={{ color: "var(--err)" }}><use href="#i-alert" /></svg>
                <span className="dz-hdr-title">Danger Zone</span>
              </div>
              <div className="dz-item">
                <div className="dz-item-info">
                  <div className="dz-item-title">Sign out all other sessions</div>
                  <div className="dz-item-sub">Revoke access from every device except this one</div>
                </div>
                <button className="btn-danger btnsm" onClick={() => logoutAllMutation.mutate()}>Sign out all</button>
              </div>
              <div className="dz-item">
                <div className="dz-item-info">
                  <div className="dz-item-title">Delete account</div>
                  <div className="dz-item-sub">Permanently remove your account and all data</div>
                </div>
                <button className="btn-danger btnsm" onClick={() => setOpenModal("deleteAcc")}>Delete account</button>
              </div>
            </div>
          </div>
        );

      case "privacy":
        return (
          <div className="page" style={{ fontFamily: "var(--font-sans, sans-serif)" }}>
            <div className="page-hdr">
              <div className="page-hdr-title">Privacy & Consent</div>
              <div className="page-hdr-sub">Manage cookie preferences, withdraw consent, and export your compliance history</div>
            </div>

            {/* Jurisdiction & Metadata */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
              <div style={{ padding: 14, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r8)" }}>
                <div style={{ fontSize: 11, color: "var(--ink3)" }}>Legal Jurisdiction</div>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, color: "var(--ink)" }}>{region === "CA" ? "US / California (CCPA)" : region}</div>
              </div>
              <div style={{ padding: 14, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r8)" }}>
                <div style={{ fontSize: 11, color: "var(--ink3)" }}>Active Consent Version</div>
                <div style={{ fontSize: 16, fontWeight: 700, marginTop: 4, color: "var(--ink)" }}>{consentVersion}</div>
              </div>
            </div>

            {/* Cookie Categories Toggles */}
            <div className="slbl">Cookie Categories</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 24 }}>
              
              {/* Essential */}
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    🛡️ Essential Cookies
                  </div>
                  <div className="tog-sub">Required for login sessions, JWT rotating tokens, and anti-CSRF protection.</div>
                </div>
                <label className="toggle">
                  <input type="checkbox" checked disabled />
                  <div className="tog-track" style={{ opacity: 0.5 }}></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>

              {/* Functional */}
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    ⚙️ Functional Preferences
                  </div>
                  <div className="tog-sub">Persists dark/light themes, sidebar layouts, and AI summary preferences.</div>
                </div>
                <label className="toggle">
                  <input 
                    type="checkbox" 
                    checked={functionalEnabled} 
                    onChange={async (e) => {
                      await updateConsent({ functional: e.target.checked });
                      triggerToast(`Functional preferences ${e.target.checked ? "enabled" : "disabled"}.`, "s");
                    }} 
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>

              {/* Analytics */}
              <div className="tog-row">
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    📈 Analytics & Performance
                  </div>
                  <div className="tog-sub">Allows privacy-focused analytics (Google Analytics, PostHog) to optimize summaries.</div>
                </div>
                <label className="toggle">
                  <input 
                    type="checkbox" 
                    checked={analyticsEnabled} 
                    onChange={async (e) => {
                      await updateConsent({ analytics: e.target.checked });
                      triggerToast(`Analytics tracking ${e.target.checked ? "enabled" : "disabled"}.`, "s");
                    }} 
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>

              {/* Marketing */}
              <div className="tog-row" style={{ borderBottom: "none" }}>
                <div className="tog-info">
                  <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600 }}>
                    📢 Target Marketing Pixels
                  </div>
                  <div className="tog-sub">Allows Meta Pixel and LinkedIn tags to measure newsletter and billing conversions.</div>
                </div>
                <label className="toggle">
                  <input 
                    type="checkbox" 
                    checked={marketingEnabled} 
                    onChange={async (e) => {
                      await updateConsent({ marketing: e.target.checked });
                      triggerToast(`Marketing pixels ${e.target.checked ? "enabled" : "disabled"}.`, "s");
                    }} 
                  />
                  <div className="tog-track"></div>
                  <div className="tog-thumb"></div>
                </label>
              </div>
            </div>

            {/* GDPR Evidence Logs & Clear Actions */}
            <div className="slbl">GDPR Compliance Controls</div>
            <div className="pcrd pcrd-p" style={{ marginBottom: 24 }}>
              
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 14, borderBottom: "1px solid var(--border)", marginBottom: 14 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>Export consent history logs</div>
                  <div style={{ fontSize: 11, color: "var(--ink3)", marginTop: 2 }}>Download your signed cookie consent transactions under GDPR Art 7.</div>
                </div>
                <button 
                  onClick={async () => {
                    try {
                      triggerToast("Fetching consent logs...", "s");
                      const response = await apiClient.get("/consent/logs");
                      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(response.data, null, 2));
                      const downloadAnchor = document.createElement("a");
                      downloadAnchor.setAttribute("href", dataStr);
                      downloadAnchor.setAttribute("download", `newsiq-consent-audit-log.json`);
                      document.body.appendChild(downloadAnchor);
                      downloadAnchor.click();
                      downloadAnchor.remove();
                      triggerToast("Consent history logs downloaded.", "s");
                    } catch (e) {
                      triggerToast("Failed to retrieve consent history.", "e");
                    }
                  }} 
                  className="btno btnsm" 
                  style={{ display: "flex", alignItems: "center", gap: 6 }}
                >
                  <Download size={13} /> Export Logs
                </button>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingBottom: 14, borderBottom: "1px solid var(--border)", marginBottom: 14 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>Reset consent defaults</div>
                  <div style={{ fontSize: 11, color: "var(--ink3)", marginTop: 2 }}>Revert all cookie consents to your region's default settings.</div>
                </div>
                <button 
                  onClick={async () => {
                    // Fetch region defaults
                    try {
                      const res = await apiClient.get("/consent/region");
                      const { defaults } = res.data;
                      await updateConsent(defaults);
                      triggerToast("Preferences reset to regional defaults.", "w");
                    } catch (e) {
                      triggerToast("Failed to reset preferences.", "e");
                    }
                  }} 
                  className="btno btnsm" 
                  style={{ display: "flex", alignItems: "center", gap: 6 }}
                >
                  <RotateCcw size={13} /> Reset Defaults
                </button>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>Withdraw all consents</div>
                  <div style={{ fontSize: 11, color: "var(--ink3)", marginTop: 2 }}>Withdraw all non-essential cookies. Will refresh page to clear variables.</div>
                </div>
                <button 
                  onClick={async () => {
                    triggerToast("Withdrawing consents...", "w");
                    await withdrawConsent();
                  }} 
                  className="btno btnsm" 
                  style={{ color: "var(--err)", borderColor: "rgba(220,38,38,.25)", display: "flex", alignItems: "center", gap: 6 }}
                >
                  <AlertTriangle size={13} /> Withdraw All
                </button>
              </div>
            </div>

            {/* General Data & Portability */}
            <div className="slbl">Data Portability & Erasure</div>
            <div className="pcrd" style={{ marginBottom: 28 }}>
              <div className="dz-item" style={{ borderBottom: "1px solid var(--border)" }}>
                <div className="dz-item-info">
                  <div className="dz-item-title">Download your data</div>
                  <div className="dz-item-sub">Export your bookmarks, preferences, and reading history as JSON</div>
                </div>
                <button className="btno btnsm" onClick={handleExportData}>
                  <Download size={13} style={{ marginRight: 6 }} /> Export
                </button>
              </div>
              <div className="dz-item">
                <div className="dz-item-info">
                  <div className="dz-item-title">Clear personalisation data</div>
                  <div className="dz-item-sub">Reset your feed ranking model — your bookmarks are kept</div>
                </div>
                <button
                  className="btno btnsm"
                  style={{ color: "var(--err)", borderColor: "rgba(220,38,38,.25)" }}
                  onClick={() => clearPersonalisationMutation.mutate()}
                  disabled={clearPersonalisationMutation.isPending}
                >
                  {clearPersonalisationMutation.isPending ? "Clearing..." : "Clear"}
                </button>
              </div>
            </div>

            <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r6)", padding: "14px 16px", display: "flex", gap: 10, marginBottom: 28 }}>
              <Shield size={16} style={{ color: "var(--ink3)", flexShrink: 0, marginTop: 2 }} />
              <div style={{ fontSize: 13, color: "var(--ink3)", lineHeight: 1.6 }}>
                NewsIQ does not sell your data to third parties. We never use your reading history for advertising. <a href="/legal?policy=privacy" style={{ color: "var(--blue)", textDecoration: "underline" }}>Read our Privacy Policy →</a>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const sidebar = <SidebarWidgets trendingStories={trendingStories} isLoading={isTrendingLoading} />;

  return (
    <AppShell sidebar={sidebar}>
      {/* SVG SPRITE */}
      <svg style={{ display: "none" }} xmlns="http://www.w3.org/2000/svg">
        <symbol id="i-back" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 5L7 10l5 5" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="3.5" /><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42" strokeLinecap="round" /></symbol>
        <symbol id="i-moon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M17 11.5A7 7 0 0 1 8.5 3a7 7 0 1 0 8.5 8.5z" strokeLinejoin="round" /></symbol>
        <symbol id="i-check" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 10l5 5 7-7" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-dash" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 10h8" strokeLinecap="round" /></symbol>
        <symbol id="i-x" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M5 5l10 10M15 5 5 15" strokeLinecap="round" /></symbol>
        <symbol id="i-crown" viewBox="0 0 20 20" fill="currentColor"><path d="M3 15h14l2-9-5 4-4-7-4 7-5-4 2 9z" /></symbol>
        <symbol id="i-bell" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2a6 6 0 0 0-6 6v2l-1.5 3h15L16 10V8a6 6 0 0 0-6-6zM8.5 16a1.5 1.5 0 0 0 3 0" strokeLinejoin="round" /></symbol>
        <symbol id="i-zap" viewBox="0 0 20 20" fill="currentColor"><path d="M11 2L3 12h7l-1 6 9-10h-7l1-6z" /></symbol>
        <symbol id="i-trend" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 14l5-5 4 3 5-6" strokeLinecap="round" strokeLinejoin="round" /><path d="M14 6h3v3" strokeLinecap="round" /></symbol>
        <symbol id="i-mail" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="5" width="16" height="12" rx="1.5" /><path d="M2 7l8 5 8-5" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-map" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="7.5" r="2.5" /><path d="M10 18s-6-5.686-6-9.5a6 6 0 0 1 12 0c0 3.814-6 9.5-6 9.5z" /></symbol>
        <symbol id="i-plus" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 4v12M4 10h12" strokeLinecap="round" /></symbol>
        <symbol id="i-trash" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 6h12M8 6V4h4v2M7 9v6M13 9v6M5 6l1 10h8l1-10" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-cam" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="6" width="16" height="11" rx="1.5" /><circle cx="10" cy="11.5" r="2.5" /><path d="M7 6l1-2h4l1 2" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-card" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="5" width="16" height="12" rx="1.5" /><path d="M2 9h16" strokeLinecap="round" /></symbol>
        <symbol id="i-lock" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="4" y="9" width="12" height="9" rx="1.5" /><path d="M7 9V7a3 3 0 0 1 6 0v2" strokeLinecap="round" /></symbol>
        <symbol id="i-alert" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 3 2 17h16L10 3z" strokeLinejoin="round" /><path d="M10 8v4M10 14.5v.5" strokeLinecap="round" /></symbol>
        <symbol id="i-download" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 3v9M6 8l4 4 4-4M4 14v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-ext" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 5H5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-4" strokeLinejoin="round" /><path d="M12 3h5v5M16 4l-7 7" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-search" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="9" cy="9" r="5.5" /><path d="m14.5 14.5 3 3" strokeLinecap="round" /></symbol>
        <symbol id="i-clock" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="7.5" /><path d="M10 6v4.5l3 1.5" strokeLinecap="round" strokeLinejoin="round" /></symbol>
        <symbol id="i-user" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="6.5" r="3" /><path d="M3 17c0-3.3 3.1-6 7-6s7 2.7 7 6" strokeLinecap="round" /></symbol>
        <symbol id="i-news" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="2" y="4" width="16" height="13" rx="1.5" /><path d="M6 8h8M6 11h5M6 14h3" strokeLinecap="round" /></symbol>
        <symbol id="i-shield" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M10 2l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V5l7-3z" strokeLinejoin="round" /></symbol>
      </svg>

      <div className="settings-container">
        {/* Left Settings Navigation */}
        <div className="settings-nav">
          {Object.entries(tabLabelMap).map(([key, label]) => {
            const IconComponent = TAB_ICONS[key];
            return (
              <button
                key={key}
                onClick={() => go(key)}
                className={`settings-nav-btn ${activeTab === key ? "active" : ""}`}
              >
                {IconComponent && <IconComponent size={15} />}
                {label}
              </button>
            );
          })}
        </div>

        {/* Settings Body */}
        <div className="settings-body">
          {renderActiveScreen()}
        </div>
      </div>

      {/* TOAST STACK */}
      <div className="tstack" id="ts">
        {toasts.map((t) => (
          <div key={t.id} className={`toast-item ${t.type === "w" ? "w" : t.type === "e" ? "e" : ""}`}>
            <span className="toast-msg">{t.msg}</span>
          </div>
        ))}
      </div>

      {/* MODAL: Confirm Delete */}
      <div className={`modal-overlay ${openModal === "deleteAcc" ? "open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) setOpenModal(null); }}>
        <div className="modal">
          <div style={{ width: 44, height: 44, borderRadius: "50%", background: "rgba(220,38,38,.1)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, color: "var(--err)" }}>
            <svg width="20" height="20"><use href="#i-alert" /></svg>
          </div>
          <div className="modal-title">Delete account?</div>
          <div className="modal-body">This will permanently remove your account, reading history, bookmarks, and preferences. This action <strong>cannot be undone</strong>.</div>
          <div className="modal-btns">
            <button className="btno btnsm" onClick={() => setOpenModal(null)}>Cancel</button>
            <button className="btn-danger btnsm" onClick={() => { deleteAccountMutation.mutate(); setOpenModal(null); }}>Yes, delete account</button>
          </div>
        </div>
      </div>

      {/* MODAL: Cancel Subscription */}
      <div className={`modal-overlay ${openModal === "cancelSub" ? "open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) setOpenModal(null); }}>
        <div className="modal">
          <div style={{ width: 44, height: 44, borderRadius: "50%", background: "rgba(220,38,38,.1)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 16, color: "var(--err)" }}>
            <svg width="20" height="20"><use href="#i-crown" /></svg>
          </div>
          <div className="modal-title">Cancel Pro subscription?</div>
          <div className="modal-body">You'll keep Pro access until <strong>July 14, 2026</strong>. After that, your account reverts to Free — summaries, source comparison, and AI chat will be unavailable.</div>
          <div className="modal-btns">
            <button className="btno btnsm" onClick={() => setOpenModal(null)}>Keep Pro</button>
            <button className="btn-danger btnsm" onClick={() => { cancelSubMutation.mutate(); setOpenModal(null); }}>Cancel subscription</button>
          </div>
        </div>
      </div>

      {/* MODAL: Add Location */}
      <div className={`modal-overlay ${openModal === "addLoc" ? "open" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) setOpenModal(null); }}>
        <div className="modal">
          <div className="modal-title">Add location</div>
          <div className="modal-body" style={{ marginBottom: 16 }}>Search for a country, state, or city to add to your feed.</div>
          <div className="sch-box" style={{ marginBottom: 20 }}>
            <svg width="16" height="16" style={{ color: "var(--ink3)", flexShrink: 0 }}><use href="#i-search" /></svg>
            <input type="text" placeholder="e.g. Chennai, Maharashtra, Japan…" value={locSearchQuery} onChange={(e) => setLocSearchQuery(e.target.value)} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 20 }}>
            {/* Bengaluru */}
            {("bengaluru").includes(locSearchQuery.toLowerCase()) && (
              <div
                style={{ padding: "10px 12px", border: "1.5px solid var(--primary)", borderRadius: "var(--r6)", backgroundColor: "rgba(196,30,58,.04)", fontSize: 14, cursor: "pointer", fontWeight: 500, display: "flex", alignItems: "center", gap: 8 }}
                onClick={() => addLocation("city", "Bengaluru")}
              >
                <span>🇮🇳</span>Bengaluru, Karnataka · City
              </div>
            )}
            {/* Chennai */}
            {("chennai").includes(locSearchQuery.toLowerCase()) && (
              <div
                style={{ padding: "10px 12px", border: "1px solid var(--border)", borderRadius: "var(--r6)", fontSize: 14, cursor: "pointer", fontWeight: 400, color: "var(--ink2)", display: "flex", alignItems: "center", gap: 8 }}
                onClick={() => addLocation("city", "Chennai")}
              >
                <span>🇮🇳</span>Chennai, Tamil Nadu · City
              </div>
            )}
            {/* Karnataka */}
            {("karnataka").includes(locSearchQuery.toLowerCase()) && (
              <div
                style={{ padding: "10px 12px", border: "1px solid var(--border)", borderRadius: "var(--r6)", fontSize: 14, cursor: "pointer", fontWeight: 400, color: "var(--ink2)", display: "flex", alignItems: "center", gap: 8 }}
                onClick={() => addLocation("country", "IN")}
              >
                <span>🇮🇳</span>Karnataka · State
              </div>
            )}
            {/* Fallback if query not matching preset mockups */}
            {locSearchQuery && !("bengaluru chennai karnataka").includes(locSearchQuery.toLowerCase()) && (
              <div style={{ padding: "10px 12px", fontSize: 13, color: "var(--ink3)", textAlign: "center" }}>No mock locations found matching "{locSearchQuery}"</div>
            )}
          </div>
          <div className="modal-btns">
            <button className="btno btnsm" onClick={() => setOpenModal(null)}>Cancel</button>
            <button className="btnp btnsm" onClick={() => { triggerToast("Location added", "s"); setOpenModal(null); }}>Add selected</button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[var(--surface)] text-[var(--ink)] flex items-center justify-center font-sans">Loading...</div>}>
      <SettingsContent />
    </Suspense>
  );
}
