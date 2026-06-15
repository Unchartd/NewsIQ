"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Mail, ArrowLeft, Zap, RefreshCw, CheckCircle2 } from "lucide-react";
import apiClient from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

function VerifyEmailConfirmContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const email = searchParams.get("email") || "";

  const [isResending, setIsResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  // Load cooldown from localStorage to persist across refreshes
  useEffect(() => {
    const savedCooldown = localStorage.getItem("resend_cooldown");
    if (savedCooldown) {
      const remaining = Math.round((parseInt(savedCooldown) - Date.now()) / 1000);
      if (remaining > 0) {
        setCooldown(remaining);
      }
    }
  }, []);

  // Cooldown timer interval
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

  const handleResend = async () => {
    if (!email) {
      toast.error("No email address provided.");
      return;
    }
    if (cooldown > 0) return;

    setIsResending(true);
    try {
      await apiClient.post("/auth/resend-verification", { email });
      toast.success("Verification email resent!");
      
      // Set 60 seconds cooldown
      const expiry = Date.now() + 60 * 1000;
      localStorage.setItem("resend_cooldown", expiry.toString());
      setCooldown(60);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "Failed to resend verification link.";
      toast.error(msg);
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
        <div className="flex justify-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-sm">
              <Zap className="w-4.5 h-4.5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight">NewsIQ</span>
          </Link>
        </div>

        {/* Card Header & Icon */}
        <div className="text-center space-y-4 mb-8">
          <div className="w-14 h-14 bg-primary/10 text-primary rounded-full flex items-center justify-center mx-auto shadow-sm">
            <Mail className="w-6 h-6" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "var(--font-heading)" }}>
              Verify your email
            </h1>
            <p className="text-sm text-muted-foreground leading-normal">
              We have sent a verification link to your email address:
            </p>
            {email && (
              <div className="inline-block bg-muted/50 px-3 py-1.5 rounded-lg border border-border/50">
                <span className="text-xs font-semibold text-foreground select-all">{email}</span>
              </div>
            )}
          </div>
        </div>

        {/* Details & Help */}
        <div className="space-y-6">
          <div className="text-xs text-muted-foreground leading-normal space-y-3 bg-muted/20 p-4 rounded-xl border border-border/40">
            <p className="font-medium text-foreground">Next steps:</p>
            <ol className="list-decimal list-inside space-y-1.5">
              <li>Open your email inbox.</li>
              <li>Look for the verification email from NewsIQ.</li>
              <li>Click the <strong>Verify Email</strong> button inside.</li>
            </ol>
            <p className="text-[10px] text-muted-foreground/80 mt-2">
              Note: The verification link will expire in 24 hours. Please check your spam or promotions folder if you cannot find the email.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3 pt-2">
            <Button
              onClick={handleResend}
              disabled={isResending || cooldown > 0}
              className="w-full h-11 rounded-xl font-medium flex items-center justify-center gap-2"
              variant={cooldown > 0 ? "outline" : "default"}
            >
              {isResending ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : cooldown > 0 ? (
                <span>Resend in {cooldown}s</span>
              ) : (
                <span>Resend Verification Email</span>
              )}
            </Button>

            <Button
              onClick={() => router.push("/login")}
              className="w-full h-11 rounded-xl font-medium border-border"
              variant="outline"
            >
              Go to Sign In
            </Button>
          </div>

          <div className="text-center pt-2">
            <Link
              href="/signup"
              className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground font-medium transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Sign Up
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

export default function VerifyEmailConfirmPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
      </div>
    }>
      <VerifyEmailConfirmContent />
    </Suspense>
  );
}
