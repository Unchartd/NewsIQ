"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  User,
  Mail,
  Shield,
  Crown,
  Settings,
  Bookmark,
  LogOut,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";

import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, logout: storeLogout } = useAuthStore();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, router]);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Still logout on client even if API fails
    }
    storeLogout();
    toast.success("Logged out successfully.");
    router.push("/");
  };

  const handleLogoutAll = async () => {
    try {
      await apiClient.post("/auth/logout-all");
      storeLogout();
      toast.success("Logged out from all devices.");
      router.push("/");
    } catch {
      toast.error("Unable to logout from all devices.");
    }
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

  return (
    <div className="min-h-screen bg-background">
      {/* Simple top bar */}
      <div className="border-b border-border">
        <div className="max-w-2xl mx-auto px-4 h-16 flex items-center justify-between">
          <button
            onClick={() => router.push("/home")}
            className="flex items-center gap-2"
          >
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Zap className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-bold">NewsIQ</span>
          </button>
          <Button variant="ghost" size="sm" onClick={() => router.push("/home")}>
            Back to Feed
          </Button>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="space-y-6"
        >
          {/* Profile Header */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-start gap-4">
                <Avatar className="w-16 h-16">
                  <AvatarImage src={user.image_url || undefined} />
                  <AvatarFallback className="text-lg font-semibold bg-primary/10 text-primary">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <h1 className="text-xl font-bold truncate">
                    {user.name || "User"}
                  </h1>
                  <p className="text-muted-foreground text-sm truncate">
                    {user.email}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge
                      variant={
                        user.subscription_plan === "pro"
                          ? "default"
                          : "secondary"
                      }
                      className="capitalize"
                    >
                      {user.subscription_plan === "pro" && (
                        <Crown className="w-3 h-3 mr-1" />
                      )}
                      {user.subscription_plan}
                    </Badge>
                    <Badge variant="outline" className="capitalize">
                      <Shield className="w-3 h-3 mr-1" />
                      {user.role}
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {[
                {
                  icon: Settings,
                  label: "Preferences",
                  href: "/preferences",
                  desc: "Categories, locations, summary style",
                },
                {
                  icon: Bookmark,
                  label: "Bookmarks",
                  href: "/bookmarks",
                  desc: "Your saved stories",
                },
                {
                  icon: Shield,
                  label: "Settings",
                  href: "/settings",
                  desc: "Theme, notifications, security",
                },
                {
                  icon: Crown,
                  label: "Upgrade to Pro",
                  href: "/premium",
                  desc: "Unlimited summaries, AI chat",
                },
              ].map((item) => (
                <button
                  key={item.label}
                  onClick={() => router.push(item.href)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-muted transition-colors text-left"
                >
                  <item.icon className="w-5 h-5 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Session Management */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Session</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                onClick={handleLogout}
                disabled={isLoggingOut}
              >
                <LogOut className="w-4 h-4" />
                {isLoggingOut ? "Logging out..." : "Sign out"}
              </Button>
              <Button
                variant="ghost"
                className="w-full justify-start gap-2 text-destructive hover:text-destructive"
                onClick={handleLogoutAll}
              >
                <LogOut className="w-4 h-4" />
                Sign out from all devices
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
