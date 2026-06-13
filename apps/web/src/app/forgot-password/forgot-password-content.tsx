"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Mail } from "lucide-react";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";

export default function ForgotPasswordContent() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setIsLoading(true);
    setError("");

    try {
      await apiClient.post("/auth/forgot-password", { email });
      setIsSuccess(true);
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(
        error.response?.data?.detail || "Failed to send reset link. Please try again later."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{
        padding: "16px 24px",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
      }}>
        <Button variant="ghost" onClick={() => router.back()} style={{ padding: "0 8px" }}>
          <ChevronLeft size={20} style={{ marginRight: 4 }} />
          Back
        </Button>
      </header>

      <main style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 24px"
      }}>
        <div style={{
          maxWidth: 400,
          width: "100%",
          padding: 32,
          border: "1px solid var(--border)",
          borderRadius: 12,
          backgroundColor: "var(--card-bg)"
        }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 8, color: "var(--ink-1)" }}>
            Reset password
          </h1>
          
          {isSuccess ? (
            <div style={{ textAlign: "center", marginTop: 24 }}>
              <div style={{
                width: 48, height: 48, borderRadius: "50%",
                backgroundColor: "var(--primary-light)",
                color: "var(--primary)",
                display: "flex", alignItems: "center", justifyContent: "center",
                margin: "0 auto 16px"
              }}>
                <Mail size={24} />
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 500, marginBottom: 8, color: "var(--ink-1)" }}>
                Check your email
              </h2>
              <p style={{ color: "var(--ink-3)", fontSize: 14, lineHeight: 1.5, marginBottom: 24 }}>
                We&apos;ve sent a password reset link to <strong>{email}</strong>.
              </p>
              <Link href="/login" style={{ width: "100%", display: "block" }}>
                <Button variant="default" style={{ width: "100%" }}>Return to log in</Button>
              </Link>
            </div>
          ) : (
            <>
              <p style={{ color: "var(--ink-3)", fontSize: 14, marginBottom: 24, lineHeight: 1.5 }}>
                Enter your email address and we&apos;ll send you a link to reset your password.
              </p>

              {error && (
                <div style={{
                  padding: 12, borderRadius: 6, backgroundColor: "#fee2e2",
                  color: "#991b1b", fontSize: 13, marginBottom: 16
                }}>
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label htmlFor="email" style={{
                    display: "block", fontSize: 13, fontWeight: 500, color: "var(--ink-2)", marginBottom: 6
                  }}>
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    disabled={isLoading}
                    style={{
                      width: "100%", padding: "10px 12px", borderRadius: 6,
                      border: "1px solid var(--border)", fontSize: 14,
                      outline: "none", transition: "border-color 0.2s"
                    }}
                  />
                </div>

                <Button
                  variant="default"
                  type="submit"
                  disabled={isLoading || !email}
                  style={{ width: "100%", marginTop: 8 }}
                >
                  {isLoading ? "Sending..." : "Send reset link"}
                </Button>
              </form>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
