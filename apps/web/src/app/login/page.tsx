"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Eye, EyeOff, Mail, Lock, Zap, ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { setAccessToken } from "@/lib/token-store";

export default function LoginPage() {
  const router = useRouter();
  const { setUser, isAuthenticated, isLoading: isAuthLoading } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (!isAuthLoading && isAuthenticated) {
      router.replace("/home");
    }
  }, [isAuthenticated, isAuthLoading, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const { data } = await apiClient.post("/auth/login", { email, password });
      setAccessToken(data.access_token);
      setUser(data.user);
      toast.success("Login successful.");
      router.push("/home");
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      const message =
        error.response?.data?.detail || "Invalid credentials.";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    window.location.href = `${apiBaseUrl}/auth/google`;
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-surface">
      {/* Left Column: Editorial Showcase */}
      <div className="hidden lg:flex flex-col bg-card border-r border-border relative overflow-hidden">
        {/* Decorative background gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-primary/8 via-transparent to-primary/3 pointer-events-none" />
        {/* Subtle grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.03] pointer-events-none"
          style={{
            backgroundImage:
              "linear-gradient(to right, currentColor 1px, transparent 1px), linear-gradient(to bottom, currentColor 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />

        {/* Logo — top-left */}
        <div className="relative z-10 p-12 pb-0">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-sm">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-2xl font-bold tracking-tight text-foreground">NewsIQ</span>
          </Link>
        </div>

        {/* Centered editorial content */}
        <div className="relative z-10 flex-1 flex flex-col justify-center px-12 py-8">
          <p className="text-[11px] font-bold tracking-[0.2em] text-primary uppercase mb-6 flex items-center gap-3">
            <span className="w-8 h-px bg-primary inline-block" />
            Editorial Intelligence
          </p>
          <h2
            className="text-[2.6rem] text-foreground leading-[1.12] mb-6"
            style={{ fontFamily: "var(--font-display)", fontWeight: 500 }}
          >
            Understand the nuance of any major story across the globe in under 30 seconds.
          </h2>
          <p className="text-base text-muted-foreground leading-relaxed max-w-md" style={{ fontFamily: "var(--font-body)" }}>
            A dense, multi-source comprehension engine built for those who value speed, accuracy, and depth over endless scrolling.
          </p>

          {/* Social proof strip */}
          <div className="mt-10 flex items-center gap-6">
            <div className="flex flex-col">
              <span className="text-2xl font-bold text-foreground">10k+</span>
              <span className="text-xs text-muted-foreground mt-0.5">Active readers</span>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="flex flex-col">
              <span className="text-2xl font-bold text-foreground">50+</span>
              <span className="text-xs text-muted-foreground mt-0.5">Sources daily</span>
            </div>
            <div className="w-px h-10 bg-border" />
            <div className="flex flex-col">
              <span className="text-2xl font-bold text-foreground">&lt;30s</span>
              <span className="text-xs text-muted-foreground mt-0.5">Story digest</span>
            </div>
          </div>
        </div>

        {/* Footer — bottom of left panel */}
        <div className="relative z-10 p-12 pt-0 flex items-center gap-4 text-xs text-muted-foreground">
          <span>&copy; {new Date().getFullYear()} NewsIQ.</span>
          <Link href="/tos" className="hover:text-foreground transition-colors">Terms of Service</Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
        </div>
      </div>

      {/* Right Column: Form */}
      <div className="flex flex-col min-h-screen relative">
        {/* Back to site — aligned to form */}
        <div className="flex-none px-6 sm:px-12 lg:px-16 pt-8">
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="text-sm font-medium">Back to site</span>
          </Link>
        </div>

        {/* Vertically centered form */}
        <div className="flex-1 flex items-center justify-center px-6 sm:px-12 lg:px-16 py-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="w-full max-w-sm"
          >
            <div className="mb-8">
              <h1 className="text-3xl font-semibold mb-2" style={{ fontFamily: "var(--font-display)" }}>
                Sign in to NewsIQ
              </h1>
              <p className="text-sm text-muted-foreground">
                Welcome back to your intelligence dashboard.
              </p>
            </div>

            <div className="space-y-5">
              {/* Google OAuth */}
              <Button
                variant="outline"
                className="w-full h-11 text-sm font-medium gap-3 border-border hover:bg-card transition-colors"
                onClick={handleGoogleLogin}
                type="button"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
                Continue with Google
              </Button>

              {/* OR divider — polished */}
              <div className="relative flex items-center gap-3 my-2">
                <div className="flex-1 h-px bg-border" />
                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-[0.15em] shrink-0">
                  or continue with email
                </span>
                <div className="flex-1 h-px bg-border" />
              </div>

              {/* Email/Password Form */}
              <form onSubmit={handleLogin} className="space-y-5">
                <div className="space-y-1.5">
                  <Label htmlFor="email" className="text-[11px] font-medium text-muted-foreground/80 tracking-wide">
                    Email address
                  </Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="pl-10 h-11 bg-card border-border focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:border-primary transition-all"
                      required
                      autoComplete="email"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password" className="text-[11px] font-medium text-muted-foreground/80 tracking-wide">
                      Password
                    </Label>
                    <Link
                      href="/forgot-password"
                      className="text-xs text-primary font-medium hover:underline"
                    >
                      Forgot password?
                    </Link>
                  </div>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pl-10 pr-10 h-11 bg-card border-border focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:border-primary transition-all"
                      required
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                <Button
                  type="submit"
                  className="w-full h-11 text-sm font-semibold bg-primary hover:bg-primary/90 text-white mt-1"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                  ) : (
                    "Sign in"
                  )}
                </Button>
              </form>

              <p className="text-center text-sm text-muted-foreground">
                Don&apos;t have an account?{" "}
                <Link
                  href="/signup"
                  className="text-foreground font-semibold underline underline-offset-4 decoration-border hover:decoration-primary transition-colors"
                >
                  Sign up
                </Link>
              </p>
            </div>
          </motion.div>
        </div>

        {/* Footer — pinned to bottom of right column, visible on all sizes */}
        <div className="flex-none px-6 sm:px-12 lg:px-16 pb-8 flex items-center justify-center gap-4 text-xs text-muted-foreground">
          <span className="lg:hidden">&copy; {new Date().getFullYear()} NewsIQ.</span>
          <Link href="/tos" className="hover:text-foreground transition-colors lg:hidden">Terms of Service</Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors lg:hidden">Privacy Policy</Link>
        </div>
      </div>
    </div>
  );
}
