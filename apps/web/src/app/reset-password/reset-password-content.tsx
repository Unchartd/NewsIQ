"use client";

import { useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Lock, CheckCircle2, AlertCircle, ArrowLeft, Zap } from "lucide-react";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError("No reset token provided. Please request a new password reset link.");
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      await apiClient.post("/auth/reset-password", {
        token,
        new_password: password,
      });
      setIsSuccess(true);
      toast.success("Password reset successfully.");
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Failed to reset password. The link may have expired."
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden">
      {/* Decorative background gradient */}
      <div className="absolute top-0 right-0 w-full h-full bg-gradient-to-br from-primary/5 to-transparent opacity-50 pointer-events-none" />

      <div className="w-full max-w-md bg-card border border-border rounded-2xl p-8 shadow-sm relative z-10">
        {/* Logo */}
        <div className="flex justify-center mb-6">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
              <Zap className="w-4.5 h-4.5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">NewsIQ</span>
          </Link>
        </div>

        <h1 className="text-2xl font-semibold mb-2 text-center" style={{ fontFamily: "var(--font-display)" }}>
          Reset Password
        </h1>

        {!token ? (
          <div className="space-y-5 mt-4 text-center">
            <div className="w-12 h-12 bg-destructive/10 text-destructive rounded-full flex items-center justify-center mx-auto">
              <AlertCircle className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-semibold">Missing Reset Token</h2>
              <p className="text-sm text-muted-foreground leading-normal">
                No password reset token was detected in the URL. Please request a new password reset link.
              </p>
            </div>
            <Link href="/forgot-password" style={{ display: "block" }}>
              <Button className="w-full rounded-xl">Request Reset Link</Button>
            </Link>
          </div>
        ) : isSuccess ? (
          <div className="text-center space-y-5 mt-4">
            <div className="w-12 h-12 bg-emerald-500/10 text-emerald-500 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-2">
              <h2 className="text-lg font-semibold">Password Updated</h2>
              <p className="text-sm text-muted-foreground leading-normal">
                Your password has been reset successfully. You can now use your new password to sign in.
              </p>
            </div>
            <Button className="w-full rounded-xl" onClick={() => router.push("/login")}>
              Go to Sign In
            </Button>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground text-center mb-6 leading-normal">
              Enter your new password below. Ensure it is at least 8 characters long.
            </p>

            {error && (
              <div className="p-3.5 bg-destructive/5 border border-destructive/20 rounded-xl text-xs text-destructive leading-normal mb-5 flex gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="password" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  New Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10 pr-10 rounded-xl h-11 border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:border-primary transition-all"
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Confirm Password
                </Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="pl-10 rounded-xl h-11 border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:border-primary transition-all"
                    disabled={isLoading}
                  />
                </div>
              </div>

              <Button type="submit" disabled={isLoading} className="w-full rounded-xl h-11 text-sm font-semibold">
                {isLoading ? "Updating..." : "Reset Password"}
              </Button>
            </form>

            <div className="text-center mt-6">
              <Link
                href="/login"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Sign In
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
