"use client";

import { Navbar } from "./navbar";
import { SignalBar } from "./signal-bar";
import { ErrorBoundary } from "@/components/error-boundary";

interface AppShellProps {
  children: React.ReactNode;
  signalVariant?: "pulse" | "progress";
  signalProgress?: number;
  sidebar?: React.ReactNode;
}

export function AppShell({ children, signalVariant = "pulse", signalProgress, sidebar }: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <Navbar />
      <SignalBar variant={signalVariant} progress={signalProgress} />
      {sidebar ? (
        <div className="niq-page-layout">
          <div className="niq-main-col">
            <ErrorBoundary>
              {children}
            </ErrorBoundary>
          </div>
          <div className="niq-side-col">
            {sidebar}
          </div>
        </div>
      ) : (
        <main className="flex-1">
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </main>
      )}
    </div>
  );
}
