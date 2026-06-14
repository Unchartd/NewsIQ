"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, XCircle, AlertCircle, Mail, ArrowLeft, Zap } from "lucide-react";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");
  
  const [status, setStatus] = useState<"loading" | "success" | "error" | "no_token">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  
  const [email, setEmail] = useState("");
  const [isResending, setIsResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);

  const verificationAttempted = useRef(false);

  useEffect(() => {
    if (verificationAttempted.current) return;
    verificationAttempted.current = true;

    if (!token) {
      setStatus("no_token");
      return;
    }

    const verify = async () => {
      try {
        await apiClient.post(`/auth/verify-email?token=${token}`);
        setStatus("success");
      } catch (err: any) {
        setStatus("error");
        setErrorMsg(
          err.response?.data?.detail || "The verification link is invalid or has expired."
        );
      }
    };

    verify();
  }, [token]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    setIsResending(true);
    setResendSuccess(false);

    try {
      await apiClient.post("/auth/resend-verification", { email });
      setResendSuccess(true);
      toast.success("Verification email sent!");
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Failed to resend verification link.");
    } finally {
      setIsResending(false);
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

        {/* Loading State */}
        {status === "loading" && (
          <div className="text-center py-6 space-y-4">
            <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin mx-auto" />
            <h2 className="text-lg font-semibold">Verifying email...</h2>
            <p className="text-sm text-muted-foreground">Please wait while we confirm your email address.</p>
          </div>
        )}

        {/* Success State */}
        {status === "success" && (
          <div className="text-center space-y-5">
            <div className="w-12 h-12 bg-emerald-500/10 text-emerald-500 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-2">
              <h2 className="text-xl font-semibold">Email Verified!</h2>
              <p className="text-sm text-muted-foreground leading-normal">
                Your email has been verified successfully. You can now access all features of your NewsIQ account.
              </p>
            </div>
            <Button className="w-full rounded-xl" onClick={() => router.push("/login")}>
              Sign In to Your Account
            </Button>
          </div>
        )}

        {/* Error or No Token State */}
        {(status === "error" || status === "no_token") && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <div className="w-12 h-12 bg-destructive/10 text-destructive rounded-full flex items-center justify-center mx-auto">
                {status === "no_token" ? <AlertCircle className="w-6 h-6" /> : <XCircle className="w-6 h-6" />}
              </div>
              <div className="space-y-1">
                <h2 className="text-xl font-semibold">
                  {status === "no_token" ? "Invalid Verification Link" : "Verification Failed"}
                </h2>
                <p className="text-sm text-muted-foreground leading-normal">
                  {status === "no_token"
                    ? "No verification token was provided in the link."
                    : errorMsg}
                </p>
              </div>
            </div>

            {resendSuccess ? (
              <div className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 p-4 rounded-xl text-xs flex items-start gap-2.5">
                <Mail className="w-4 h-4 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Check your inbox</p>
                  <p className="mt-0.5 leading-normal">
                    We&apos;ve sent a new verification link to <strong>{email}</strong>. Please check your spam folder if you don&apos;t receive it within a few minutes.
                  </p>
                </div>
              </div>
            ) : (
              <form onSubmit={handleResend} className="space-y-4 pt-2 border-t border-border/40">
                <p className="text-xs text-muted-foreground leading-normal">
                  Need a new verification link? Enter your email address below to resend it:
                </p>
                <div className="space-y-2">
                  <Label htmlFor="email" className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    Email Address
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="rounded-xl h-10 border-border"
                    disabled={isResending}
                  />
                </div>
                <Button type="submit" disabled={isResending || !email} className="w-full rounded-xl">
                  {isResending ? "Sending..." : "Resend Verification Link"}
                </Button>
              </form>
            )}

            <div className="text-center pt-2">
              <Link
                href="/login"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Sign In
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
