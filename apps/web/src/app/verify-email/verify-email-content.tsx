"use client";

import { useEffect, useState, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, AlertCircle, Mail, ArrowLeft, Zap, RefreshCw } from "lucide-react";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";

export default function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token");
  
  const { user, isAuthenticated, setUser } = useAuthStore();
  const [status, setStatus] = useState<"loading" | "success" | "error" | "no_token">("loading");
  const [errorMsg, setErrorMsg] = useState("");
  
  const [email, setEmail] = useState("");
  const [isResending, setIsResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const verificationAttempted = useRef(false);

  // Load resend cooldown from localStorage
  useEffect(() => {
    const savedCooldown = localStorage.getItem("resend_cooldown");
    if (savedCooldown) {
      const remaining = Math.round((parseInt(savedCooldown) - Date.now()) / 1000);
      if (remaining > 0) {
        setCooldown(remaining);
      }
    }
  }, []);

  // Cooldown interval timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const interval = setInterval(() => {
      setCooldown((prev) => {
        const next = prev - 1;
        if (next <= 0) {
          localStorage.removeItem("resend_cooldown");
          return 0;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldown]);

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
        // Automatically mark the user as verified if logged in
        if (user) {
          setUser({ ...user, email_verified: true });
        }
        toast.success("Email verified successfully!");
      } catch (err: any) {
        setStatus("error");
        setErrorMsg(
          err.response?.data?.detail || "The verification link is invalid or has expired."
        );
      }
    };

    verify();
  }, [token, user, setUser]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    if (cooldown > 0) return;

    setIsResending(true);

    try {
      await apiClient.post("/auth/resend-verification", { email });
      toast.success("Verification email sent!");
      
      // Set 60 seconds cooldown
      const expiry = Date.now() + 60 * 1000;
      localStorage.setItem("resend_cooldown", expiry.toString());
      setCooldown(60);
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

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="w-full max-w-md bg-card border border-border rounded-2xl p-8 shadow-sm relative z-10"
      >
        {/* Logo */}
        <div className="flex justify-center mb-6">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-sm">
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
          <div className="text-center space-y-6">
            <div className="w-14 h-14 bg-emerald-500/10 text-emerald-500 rounded-full flex items-center justify-center mx-auto shadow-sm">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-heading)" }}>
                Email Verified!
              </h2>
              <p className="text-sm text-muted-foreground leading-normal">
                Your email has been verified successfully. You can now access all features of your NewsIQ account.
              </p>
            </div>

            {isAuthenticated ? (
              <Button className="w-full h-11 rounded-xl font-medium" onClick={() => router.push("/home")}>
                Go to Dashboard
              </Button>
            ) : (
              <Button className="w-full h-11 rounded-xl font-medium" onClick={() => router.push("/login")}>
                Sign In to Your Account
              </Button>
            )}
          </div>
        )}

        {/* Error or No Token State */}
        {(status === "error" || status === "no_token") && (
          <div className="space-y-6">
            <div className="text-center space-y-4">
              <div className="w-14 h-14 bg-destructive/10 text-destructive rounded-full flex items-center justify-center mx-auto shadow-sm">
                {status === "no_token" ? <AlertCircle className="w-6 h-6" /> : <XCircle className="w-6 h-6" />}
              </div>
              <div className="space-y-1">
                <h2 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-heading)" }}>
                  {status === "no_token" ? "Invalid Link" : "Verification Failed"}
                </h2>
                <p className="text-sm text-muted-foreground leading-normal">
                  {status === "no_token"
                    ? "No verification token was provided in the link."
                    : errorMsg}
                </p>
              </div>
            </div>

            <form onSubmit={handleResend} className="space-y-4 pt-4 border-t border-border/60">
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
                  className="rounded-xl h-11 border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:border-primary transition-all"
                  disabled={isResending}
                />
              </div>
              
              <Button 
                type="submit" 
                disabled={isResending || cooldown > 0 || !email} 
                className="w-full h-11 rounded-xl font-medium flex items-center justify-center gap-2"
                variant={cooldown > 0 ? "outline" : "default"}
              >
                {isResending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : cooldown > 0 ? (
                  <span>Resend in {cooldown}s</span>
                ) : (
                  <span>Resend Verification Link</span>
                )}
              </Button>
            </form>

            <div className="text-center pt-2">
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Sign In
              </Link>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
