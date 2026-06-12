"use client";

import { Navbar } from "./navbar";
import { Sidebar } from "./sidebar";
import { RightPanel } from "./right-panel";
import { MobileNav } from "./mobile-nav";
import { ErrorBoundary } from "@/components/error-boundary";

interface AppShellProps {
  children: React.ReactNode;
  showRightPanel?: boolean;
}

export function AppShell({ children, showRightPanel = true }: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col pb-16 lg:pb-0 bg-background text-foreground">
      <Navbar />
      <div className="flex flex-1 relative">
        <Sidebar />
        <main className="flex-1 overflow-y-auto min-w-0">
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </main>
        {showRightPanel && <RightPanel />}
      </div>
      <MobileNav />
    </div>
  );
}
