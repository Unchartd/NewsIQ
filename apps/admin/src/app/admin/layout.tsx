"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/stores/auth-store";
import { useSSE } from "@/lib/useSSE";
import {
  Shield,
  LayoutDashboard,
  GitBranch,
  Layers,
  Users,
  FileText,
  DollarSign,
  UserCheck,
  Radio,
  LogOut,
  ChevronRight,
  Activity,
  Menu,
  X,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/admin", label: "Overview", icon: LayoutDashboard },
  { href: "/admin/pipeline", label: "Pipeline DAG", icon: GitBranch },
  { href: "/admin/sources", label: "Sources", icon: Radio },
  { href: "/admin/stories", label: "Stories", icon: Layers },
  { href: "/admin/entities", label: "Entities", icon: Users },
  { href: "/admin/clusters", label: "Clusters", icon: Layers },
  { href: "/admin/prompts", label: "Prompts", icon: FileText },
  { href: "/admin/costs", label: "Cost Analytics", icon: DollarSign },
  { href: "/admin/review", label: "Review Queue", icon: UserCheck },
];

function SSEStatusDot({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    connected: "bg-emerald-500",
    connecting: "bg-amber-400 animate-pulse",
    disconnected: "bg-slate-600",
    error: "bg-red-500",
  };
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${colorMap[status] ?? "bg-slate-600"}`}
    />
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, logout, hydrate } = useAuthStore();
  const { status: sseStatus } = useSSE();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  function handleLogout() {
    logout();
    router.replace("/");
  }

  const Sidebar = (
    <aside className="flex flex-col h-full w-64 bg-card border-r border-border">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div className="w-9 h-9 rounded-xl bg-primary/15 border border-primary/20 flex items-center justify-center shadow-lg shadow-primary/15">
          <Shield className="w-5 h-5 text-primary" />
        </div>
        <div>
          <p className="text-sm font-bold text-foreground leading-none">
            NewsIQ
          </p>
          <p className="text-[10px] text-slate-500 mt-0.5 font-mono">Admin Console</p>
        </div>
      </div>

      {/* SSE Status */}
      <div className="px-5 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-xs">
          <SSEStatusDot status={sseStatus} />
          <span className="text-slate-500">
            Live Feed:{" "}
            <span className="text-slate-400 font-mono capitalize">{sseStatus}</span>
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/admin"
              ? pathname === "/admin"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setSidebarOpen(false)}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                isActive
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
              {isActive && (
                <ChevronRight className="w-3.5 h-3.5 text-primary" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* User + Logout */}
      <div className="border-t border-border px-4 py-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-rose-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
            {user?.name?.charAt(0).toUpperCase() ?? "A"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-200 truncate">
              {user?.name}
            </p>
            <p className="text-[10px] text-slate-500 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          id="admin-logout-btn"
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-red-450 hover:bg-red-500/10 transition-all border border-transparent hover:border-red-500/20"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign Out
        </button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex shrink-0">{Sidebar}</div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-50 flex">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative">{Sidebar}</div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile topbar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-border bg-card">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-slate-400 hover:text-slate-200 transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            <span className="text-sm font-bold text-slate-100">NewsIQ Admin</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <SSEStatusDot status={sseStatus} />
            <Activity className="w-4 h-4 text-slate-500" />
          </div>
        </div>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-7xl mx-auto px-6 py-8 animate-fade-in">
            {children}
          </div>
        </div>
      </main>

      {/* Close mobile sidebar btn */}
      {sidebarOpen && (
        <button
          className="lg:hidden fixed top-4 right-4 z-50 w-9 h-9 flex items-center justify-center rounded-xl bg-card border border-border text-slate-400"
          onClick={() => setSidebarOpen(false)}
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
