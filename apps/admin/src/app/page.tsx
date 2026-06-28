"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api-client";
import { Loader2 } from "lucide-react";
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
      router.replace("/admin");
    }
  }, [isAuthenticated, router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) return;

    setIsLoading(true);
    try {
      const res = await apiClient.post("/auth/login", {
        email,
        password,
      });

      const { access_token } = res.data;

      // Fetch current user profile to verify admin role
      const meRes = await apiClient.get("/auth/me", {
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
      router.replace("/admin");
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
    <>
      <style dangerouslySetInnerHTML={{ __html: `
        .page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background: #0f0f11;
          padding: 2rem;
        }

        .card {
          width: 100%;
          max-width: 420px;
          background: #18181c;
          border: 0.5px solid #2a2a30;
          border-radius: 16px;
          overflow: hidden;
        }

        .card-header {
          padding: 2rem 2rem 1.5rem;
          border-bottom: 0.5px solid #2a2a30;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.75rem;
          text-align: center;
        }

        .logo-wrap {
          width: 44px;
          height: 44px;
          border-radius: 10px;
          background: #2a1a1a;
          border: 0.5px solid #3d2020;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .logo-wrap svg {
          width: 22px;
          height: 22px;
        }

        .brand-name {
          font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
          font-size: 18px;
          font-weight: 600;
          color: #f5f5f5;
          letter-spacing: -0.3px;
        }

        .brand-name span {
          color: #e05c5c;
        }

        .console-label {
          font-size: 12px;
          font-weight: 500;
          color: #888;
          letter-spacing: 0.6px;
          text-transform: uppercase;
        }

        .tag-row {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
          justify-content: center;
          margin-top: 2px;
        }

        .tag {
          font-size: 11px;
          color: #555;
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .tag-dot {
          width: 3px;
          height: 3px;
          border-radius: 50%;
          background: #3a3a40;
        }

        .card-body {
          padding: 1.75rem 2rem 2rem;
          display: flex;
          flex-direction: column;
          gap: 1.1rem;
        }

        .field {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .field-label {
          font-size: 11.5px;
          font-weight: 500;
          color: #666;
          letter-spacing: 0.4px;
          text-transform: uppercase;
        }

        .input-wrap {
          position: relative;
          display: flex;
          align-items: center;
        }

        .input-icon {
          position: absolute;
          left: 12px;
          color: #444;
          display: flex;
          align-items: center;
          pointer-events: none;
        }

        .input-field {
          width: 100%;
          height: 42px;
          background: #111113;
          border: 0.5px solid #2a2a30;
          border-radius: 8px;
          font-size: 13.5px;
          color: #d0d0d8;
          padding: 0 40px;
          font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
          transition: border-color 0.15s;
          outline: none;
        }

        .input-field:focus {
          border-color: #e05c5c;
          box-shadow: 0 0 0 3px rgba(224, 92, 92, 0.08);
        }

        .input-field::placeholder {
          color: #3d3d45;
        }

        .eye-btn {
          position: absolute;
          right: 12px;
          background: none;
          border: none;
          color: #444;
          cursor: pointer;
          display: flex;
          padding: 0;
          transition: color 0.15s;
        }

        .eye-btn:hover { color: #888; }

        .divider {
          height: 0.5px;
          background: #2a2a30;
          margin: 0.25rem 0;
        }

        .sign-in-btn {
          width: 100%;
          height: 42px;
          background: #e05c5c;
          border: none;
          border-radius: 8px;
          font-size: 13.5px;
          font-weight: 600;
          color: #fff;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 7px;
          letter-spacing: 0.1px;
          font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
          transition: background 0.15s, transform 0.1s;
        }

        .sign-in-btn:hover { background: #cc4e4e; }
        .sign-in-btn:active { transform: scale(0.99); }
        .sign-in-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .restricted-row {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding-top: 0.25rem;
        }

        .restricted-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: rgba(224, 92, 92, 0.13);
          border: 1px solid rgba(224, 92, 92, 0.27);
          flex-shrink: 0;
        }

        .restricted-text {
          font-size: 11px;
          color: #444;
          letter-spacing: 0.2px;
        }

        .card-footer {
          padding: 0.85rem 2rem;
          border-top: 0.5px solid #1f1f25;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .footer-version {
          font-size: 11px;
          color: #333;
          font-family: 'SF Mono', 'Fira Code', monospace;
          letter-spacing: 0.3px;
        }

        .footer-status {
          display: flex;
          align-items: center;
          gap: 5px;
          font-size: 11px;
          color: #3a8a4a;
        }

        .status-dot {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: #3a8a4a;
        }
      ` }} />

      <div className="page">
        <div className="card">

          <div className="card-header">
            <div className="logo-wrap">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L4 6v6c0 5.25 3.5 10.15 8 11.35C16.5 22.15 20 17.25 20 12V6L12 2z" fill="#e05c5c" opacity="0.18"/>
                <path d="M12 2L4 6v6c0 5.25 3.5 10.15 8 11.35C16.5 22.15 20 17.25 20 12V6L12 2z" stroke="#e05c5c" strokeWidth={1.5} strokeLinejoin="round"/>
                <circle cx={12} cy={11} r={2.5} fill="#e05c5c"/>
                <path d="M12 13.5V16" stroke="#e05c5c" strokeWidth={1.5} strokeLinecap="round"/>
              </svg>
            </div>

            <div>
              <div className="brand-name">News<span>IQ</span></div>
            </div>

            <div className="console-label">Admin Console</div>

            <div className="tag-row">
              <span className="tag">AI Observability</span>
              <span className="tag-dot"></span>
              <span className="tag">Pipeline Tracing</span>
              <span className="tag-dot"></span>
              <span className="tag">Replay Engine</span>
            </div>
          </div>

          <form onSubmit={handleLogin} className="card-body">

            <div className="field">
              <label htmlFor="admin-email" className="field-label">Email</label>
              <div className="input-wrap">
                <span className="input-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="4" width="20" height="16" rx="2"/>
                    <path d="M2 7l10 7 10-7"/>
                  </svg>
                </span>
                <input
                  id="admin-email"
                  className="input-field"
                  type="email"
                  placeholder="admin@newsiq.io"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="admin-password" className="field-label">Password</label>
              <div className="input-wrap">
                <span className="input-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2"/>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                  </svg>
                </span>
                <input
                  id="admin-password"
                  className="input-field"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••••"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="eye-btn"
                  aria-label="Toggle password visibility"
                  style={{ opacity: showPassword ? 1 : 0.6 }}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                </button>
              </div>
            </div>

            <div className="divider"></div>

            <button type="submit" disabled={isLoading} className="sign-in-btn">
              {isLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Authenticating...
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                    <polyline points="10 17 15 12 10 7"/>
                    <line x1="15" y1="12" x2="3" y2="12"/>
                  </svg>
                  Sign in to Admin Console
                </>
              )}
            </button>

            <div className="restricted-row">
              <div className="restricted-dot"></div>
              <span className="restricted-text">Access restricted to administrators only</span>
            </div>

          </form>

          <div className="card-footer">
            <span className="footer-version">v1.0 · SRE Platform</span>
            <div className="footer-status">
              <div className="status-dot"></div>
              <span>All systems operational</span>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
