"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Bell, CheckCheck, Trash2, ShieldAlert, Sparkles, Volume2, Calendar } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";

interface NotificationItem {
  id: string;
  title: string;
  body: string;
  notification_type: string;
  is_read: boolean;
  created_at: string;
}

export default function NotificationsPage() {
  const { isAuthenticated } = useAuthStore();
  const queryClient = useQueryClient();

  // Fetch notifications
  const { data: notifications = [], isLoading } = useQuery<NotificationItem[]>({
    queryKey: ["notifications"],
    queryFn: async () => {
      const response = await apiClient.get("/users/notifications");
      return response.data;
    },
    enabled: isAuthenticated,
  });

  // Mark as read mutation
  const markReadMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.patch(`/users/notifications/${id}/read`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("Marked as read");
    },
    onError: () => {
      toast.error("Failed to update notification.");
    },
  });

  // Delete notification mutation
  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/users/notifications/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("Notification deleted");
    },
    onError: () => {
      toast.error("Failed to delete notification.");
    },
  });

  if (!isAuthenticated) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto py-16 text-center">
          <Bell className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-bold text-foreground">Sign In Required</h2>
          <p className="text-muted-foreground text-sm mt-1 mb-6">
            Please sign in to view your notifications feed.
          </p>
          <Button render={<a href="/login" />} className="rounded-xl">
            Sign In
          </Button>
        </div>
      </AppShell>
    );
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "breaking_news":
        return <ShieldAlert className="w-4 h-4 text-rose-500" />;
      case "trending":
        return <Sparkles className="w-4 h-4 text-violet-500" />;
      default:
        return <Volume2 className="w-4 h-4 text-primary" />;
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <AppShell>
      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6 pb-24">
        {/* Title */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="w-6 h-6 text-primary" />
            <h1 className="text-2xl font-bold">Notifications</h1>
            {unreadCount > 0 && (
              <Badge variant="default" className="rounded-full text-[10px] px-2 py-0.5">
                {unreadCount} new
              </Badge>
            )}
          </div>
        </div>

        {/* Notifications List */}
        <Card className="border-border/50 rounded-2xl">
          <CardHeader className="pb-3 border-b border-border/40">
            <CardTitle className="text-base font-semibold">Activity Feed</CardTitle>
            <CardDescription>Stay up to date with the latest intelligence on stories you follow.</CardDescription>
          </CardHeader>
          <CardContent className="p-0 divide-y divide-border/40">
            {isLoading ? (
              <div className="p-6 text-center text-sm text-muted-foreground">Loading...</div>
            ) : notifications.length === 0 ? (
              <div className="p-8 text-center space-y-2">
                <Bell className="w-8 h-8 text-muted-foreground/40 mx-auto" />
                <p className="text-sm font-semibold text-muted-foreground">All caught up!</p>
                <p className="text-xs text-muted-foreground/80">No new notifications at this time.</p>
              </div>
            ) : (
              <div className="overflow-hidden">
                <AnimatePresence initial={false}>
                  {notifications.map((notif) => (
                    <motion.div
                      key={notif.id}
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className={`p-4 flex gap-3.5 transition-colors ${
                        notif.is_read ? "bg-background/40" : "bg-primary/5 dark:bg-primary/5"
                      }`}
                    >
                      <div className="mt-0.5 shrink-0">
                        <div className="w-8 h-8 rounded-full border border-border/50 flex items-center justify-center bg-background">
                          {getIcon(notif.notification_type)}
                        </div>
                      </div>

                      <div className="flex-1 space-y-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className={`text-xs font-semibold ${notif.is_read ? "text-muted-foreground" : "text-foreground"}`}>
                            {notif.title}
                          </p>
                          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {new Date(notif.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {notif.body}
                        </p>
                        
                        <div className="flex justify-end gap-1.5 pt-2">
                          {!notif.is_read && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => markReadMutation.mutate(notif.id)}
                              className="h-7 text-[10px] px-2 rounded-lg flex items-center gap-1 text-primary hover:bg-primary/10"
                            >
                              <CheckCheck className="w-3 h-3" />
                              Mark as read
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteMutation.mutate(notif.id)}
                            className="h-7 text-[10px] px-2 rounded-lg flex items-center gap-1 text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="w-3 h-3" />
                            Delete
                          </Button>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
