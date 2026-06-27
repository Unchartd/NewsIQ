"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { Eye, EyeOff, Mail, Lock, Zap, ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
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
    // Redirect to backend OAuth endpoint
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    window.location.href = `${apiBaseUrl}/auth/google`;
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-surface">
      {/* Left Column: Form */}
      <div className="flex flex-col justify-center px-6 sm:px-12 lg:px-24 py-12 relative">
        <div className="absolute top-8 left-6 sm:left-12">
          <Link href="/" className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors group">
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
            <span className="text-sm font-medium">Back to site</span>
          </Link>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
          className="w-full max-w-sm mx-auto"
        >
          <div className="mb-8">
            <h1 className="text-3xl font-semibold mb-2" style={{ fontFamily: "var(--font-display)" }}>Sign in to NewsIQ</h1>
            <p className="text-sm text-muted-foreground">
              Welcome back to your intelligence dashboard.
            </p>
          </div>

          <div className="space-y-6">
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

            <div className="relative">
              <Separator className="bg-border" />
              <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-surface px-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                or email
              </span>
            </div>

            {/* Email/Password Form */}
            <form onSubmit={handleLogin} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Email Address</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10 h-11 bg-card border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:border-primary transition-all"
                    required
                    autoComplete="email"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Password</Label>
                  <Link
                    href="/forgot-password"
                    className="text-xs text-primary font-medium hover:underline"
                  >
                    Forgot?
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
                    className="pl-10 pr-10 h-11 bg-card border-border focus-visible:ring-1 focus-visible:ring-primary focus-visible:border-primary transition-all"
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
                className="w-full h-11 text-sm font-semibold bg-primary hover:bg-primary/90 text-white"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : (
                  "Sign In"
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

      {/* Right Column: Editorial Showcase */}
      <div className="hidden lg:flex flex-col justify-between bg-card border-l border-border p-12 relative overflow-hidden">
        {/* Subtle decorative background element */}
        <div className="absolute top-0 right-0 w-full h-full bg-gradient-to-br from-primary/5 to-transparent opacity-50" />
        
        <div className="relative z-10">
          <Link href="/" className="inline-flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-sm">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <span className="text-2xl font-bold tracking-tight text-foreground">NewsIQ</span>
          </Link>
        </div>

        <div className="relative z-10 max-w-lg">
          <p className="text-[11px] font-bold tracking-[0.15em] text-primary uppercase mb-6 flex items-center gap-2">
            <span className="w-6 h-px bg-primary inline-block"></span>
            Editorial Intelligence
          </p>
          <h2 className="text-4xl text-foreground leading-[1.15]" style={{ fontFamily: "var(--font-display)", fontWeight: 500 }}>
            &quot;Understand the nuance of any major story across the globe in under 30 seconds.&quot;
          </h2>
          <p className="mt-6 text-lg text-muted-foreground" style={{ fontFamily: "var(--font-body)" }}>
            A dense, multi-source comprehension engine built for those who value speed, accuracy, and depth over endless scrolling.
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-4 text-xs text-muted-foreground">
          <span>&copy; {new Date().getFullYear()} NewsIQ.</span>
          <Link href="/tos" className="hover:text-foreground transition-colors">Terms of Service</Link>
          <Link href="/privacy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
        </div>
      </div>
    </div>
  );
}
