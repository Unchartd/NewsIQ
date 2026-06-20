"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import {
  Shield,
  Eye,
  EyeOff,
  Lock,
  Mail,
  Activity,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

export default function LoginPage() {
  const router = useRouter();
  const { login, hydrate, isAuthenticated } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Hydrate from localStorage on mount
  useEffect(() => {
    hydrate();
  }, [hydrate]);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;

    setIsLoading(true);
    try {
      // OAuth2 password flow — FastAPI expects form data
      const params = new URLSearchParams();
      params.append("username", email);
      params.append("password", password);

      const res = await apiClient.post("/auth/login", params, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const { access_token } = res.data;

      // Fetch current user profile to verify admin role
      const meRes = await apiClient.get("/users/me", {
        headers: { Authorization: `Bearer ${access_token}` },
      });

      const user = meRes.data;

      if (user.role !== "admin") {
        toast.error("Access denied — admin role required.");
        setIsLoading(false);
        return;
      }

      login(
        {
          id: user.id,
          email: user.email,
          name: user.full_name || user.email,
          role: user.role,
        },
        access_token
      );

      toast.success(`Welcome back, ${user.full_name || user.email}!`);
      router.replace("/dashboard");
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail || "Invalid credentials. Please try again.";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background">
      {/* Animated background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-background via-card to-background" />
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-primary/5 rounded-full blur-3xl animate-pulse [animation-delay:1s]" />
      <div className="absolute top-1/2 right-1/3 w-64 h-64 bg-primary/3 rounded-full blur-3xl animate-pulse [animation-delay:2s]" />

      {/* Login card */}
      <div className="relative z-10 w-full max-w-md mx-4 animate-fade-in">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/15 border border-primary/30 mb-4 shadow-lg shadow-primary/15">
            <Shield className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="gradient-text">NewsIQ</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1.5 font-medium">Admin Console</p>
          <p className="text-slate-500 text-xs mt-1">
            AI Observability · Pipeline Tracing · Replay Engine
          </p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl p-8 shadow-2xl shadow-black/80">
          <div className="flex items-center gap-2 mb-6">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
            <span className="text-xs text-slate-500 font-medium px-2">SECURE LOGIN</span>
            <div className="flex-1 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            {/* Email field */}
            <div className="space-y-1.5">
              <label
                htmlFor="admin-email"
                className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
              >
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  id="admin-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@newsiq.com"
                  required
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-background border border-border text-foreground text-sm placeholder-slate-600
                    focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all"
                />
              </div>
            </div>

            {/* Password field */}
            <div className="space-y-1.5">
              <label
                htmlFor="admin-password"
                className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input
                  id="admin-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••"
                  required
                  className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-background border border-border text-foreground text-sm placeholder-slate-600
                    focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/20 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>

            {/* Submit button */}
            <button
              id="admin-login-btn"
              type="submit"
              disabled={isLoading || !email || !password}
              className="w-full py-2.5 px-4 rounded-xl font-semibold text-sm text-white transition-all
                bg-gradient-to-r from-primary to-rose-600 hover:from-primary/95 hover:to-rose-500
                disabled:opacity-50 disabled:cursor-not-allowed
                shadow-lg shadow-primary/20 hover:shadow-primary/30
                flex items-center justify-center gap-2 mt-2"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Authenticating…
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4" />
                  Sign In to Admin Console
                </>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-6 pt-5 border-t border-border flex items-center justify-center gap-2">
            <Activity className="w-3.5 h-3.5 text-emerald-500" />
            <span className="text-xs text-slate-500">
              Access restricted to administrators only
            </span>
          </div>
        </div>

        {/* Version badge */}
        <p className="text-center text-[11px] text-slate-600 mt-4 font-mono">
          NewsIQ Admin v1.0 · SRE Platform
        </p>
      </div>
    </div>
  );
}
