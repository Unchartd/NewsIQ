"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { AppShell } from "@/components/layout/app-shell";
import { Shield, Activity, GitBranch, Layers, Users, HelpCircle, FileText, DollarSign, UserCheck } from "lucide-react";
import { useSSE } from "@/lib/useSSE";

interface AdminLayoutProps {
  children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const { user, isAuthenticated } = useAuthStore();
  const pathname = usePathname();
  const { status: sseStatus } = useSSE();

  const isAdmin = user?.role === "admin";

  if (!isAuthenticated || !isAdmin) {
    return (
      <AppShell>
        <div className="max-w-md mx-auto py-24 text-center">
          <Shield className="w-16 h-16 text-destructive mx-auto mb-6 animate-pulse" />
          <h2 className="text-2xl font-bold text-foreground">Access Denied</h2>
          <p className="text-muted-foreground text-sm mt-2">
            You do not have the required administrative permissions to access the admin console.
          </p>
        </div>
      </AppShell>
    );
  }

  const tabs = [
    { name: "Sources & Control", href: "/admin", icon: Shield },
    { name: "Pipeline DAG", href: "/admin/pipeline", icon: GitBranch },
    { name: "Story Clusters", href: "/admin/clusters", icon: Layers },
    { name: "Entity Debugger", href: "/admin/entities", icon: Users },
    { name: "Prompt Viewer", href: "/admin/prompts", icon: FileText },
    { name: "Cost Analytics", href: "/admin/costs", icon: DollarSign },
    { name: "Review Queue", href: "/admin/review", icon: UserCheck },
  ];

  return (
    <AppShell>
      <div className="border-b border-border/40 bg-card/30 backdrop-blur-md sticky top-[64px] z-40">
        <div className="max-w-7xl mx-auto px-4 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-foreground flex items-center gap-2">
                NewsIQ Admin Console
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-primary/20 text-primary font-mono">
                  SRE Platform
                </span>
              </h1>
              <p className="text-xs text-muted-foreground mt-0.5">
                AI Observability, Pipeline Tracing, & Replay Engine
              </p>
            </div>
          </div>

          {/* SSE live status badge */}
          <div className="flex items-center gap-2 self-start md:self-auto">
            <span className="text-xs text-muted-foreground flex items-center gap-1.5">
              Live Pipeline Feed:
            </span>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-background border border-border/60">
              <span className={`w-2.5 h-2.5 rounded-full ${
                sseStatus === "connected"
                  ? "bg-emerald-500 animate-pulse"
                  : sseStatus === "connecting"
                  ? "bg-amber-500 animate-spin"
                  : "bg-red-500"
              }`} />
              <span className="text-[11px] font-mono capitalize">
                {sseStatus}
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex overflow-x-auto gap-1 border-t border-border/20 pt-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-all whitespace-nowrap ${
                    isActive
                      ? "border-primary text-primary bg-primary/5"
                      : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/10"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.name}
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {children}
      </div>
    </AppShell>
  );
}
