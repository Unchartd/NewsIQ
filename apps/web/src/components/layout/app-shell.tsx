"use client";

import { Navbar } from "./navbar";
import { SignalBar } from "./signal-bar";
import { ErrorBoundary } from "@/components/error-boundary";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { useState } from "react";
import { useIsFetching, useIsMutating } from "@tanstack/react-query";

interface AppShellProps {
  children: React.ReactNode;
  signalVariant?: "pulse" | "progress";
  signalProgress?: number;
  /** Right-hand sidebar column content */
  sidebar?: React.ReactNode;
  /**
   * Optional full-width tabs bar rendered between the signal bar and the
   * layout grid — outside .mc so it spans the entire content width without
   * needing negative-margin hacks inside the column.
   */
  categoryTabs?: React.ReactNode;
}

export function AppShell({
  children,
  signalVariant = "pulse",
  signalProgress,
  sidebar,
  categoryTabs,
}: AppShellProps) {
  const { user, isAuthenticated } = useAuthStore();
  const [sentVerification, setSentVerification] = useState(false);

  const isFetching = useIsFetching();
  const isMutating = useIsMutating();
  const isLoading = isFetching > 0 || isMutating > 0;

  const handleResendVerification = async () => {
    if (!user?.email) return;
    try {
      await apiClient.post("/auth/resend-verification", { email: user.email });
      setSentVerification(true);
    } catch {
      // Ignored for UI simplicity
    }
  };

  const showVerificationBanner = isAuthenticated && user && !user.email_verified;

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {showVerificationBanner && (
        <div
          style={{
            backgroundColor: "var(--warning-light)",
            color: "var(--warning-dark)",
            padding: "8px 16px",
            textAlign: "center",
            fontSize: 13,
            fontWeight: 500,
            borderBottom: "1px solid var(--warning)",
          }}
        >
          Please verify your email address.{" "}
          {sentVerification ? (
            <span style={{ marginLeft: 8, color: "var(--warning)" }}>Verification sent!</span>
          ) : (
            <button
              onClick={handleResendVerification}
              style={{ marginLeft: 8, textDecoration: "underline", color: "var(--warning-dark)" }}
            >
              Resend email
            </button>
          )}
        </div>
      )}

      <Navbar />
      <SignalBar variant={signalVariant} progress={signalProgress} active={isLoading || signalVariant === "progress"} />

      {/* Full-width category tabs bar — rendered above the layout grid */}
      {categoryTabs}

      {sidebar ? (
        <div className="layout">
          <div className="mc">
            <ErrorBoundary>{children}</ErrorBoundary>
          </div>
          <div className="sc">{sidebar}</div>
        </div>
      ) : (
        <main className="flex-1">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      )}
    </div>
  );
}
