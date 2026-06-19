"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import "./legal.css";

export default function LegalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { theme, setTheme } = useTheme();
  const router = useRouter();

  const [mounted, setMounted] = useState(false);
  const { isAuthenticated } = useAuthStore();

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  const toggleTheme = () => {
    setTheme(theme === "dark" ? "light" : "dark");
  };

  const isDark = mounted && theme === "dark";

  return (
    <>
      {/* SVG SPRITE */}
      <svg style={{ display: "none" }}>
        <symbol id="i-shield" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M10 2l7 3v5c0 4-3 7-7 8-4-1-7-4-7-8V5l7-3z" strokeLinejoin="round" />
        </symbol>
        <symbol id="i-doc" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M5 3h8l3 3v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" strokeLinejoin="round" />
          <path d="M13 3v3h3M7 9h6M7 12h4" strokeLinecap="round" />
        </symbol>
        <symbol id="i-check" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M4 10l5 5 7-7" strokeLinecap="round" strokeLinejoin="round" />
        </symbol>
        <symbol id="i-mail" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="2" y="5" width="16" height="12" rx="1.5" />
          <path d="M2 7l8 5 8-5" strokeLinecap="round" strokeLinejoin="round" />
        </symbol>
        <symbol id="i-sun" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="10" cy="10" r="3.5" />
          <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42" strokeLinecap="round" />
        </symbol>
        <symbol id="i-moon" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M17 11.5A7 7 0 0 1 8.5 3a7 7 0 1 0 8.5 8.5z" strokeLinejoin="round" />
        </symbol>
        <symbol id="i-ext" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M9 5H5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h9a1 1 0 0 0 1-1v-4" strokeLinejoin="round" />
          <path d="M12 3h5v5M16 4l-7 7" strokeLinecap="round" />
        </symbol>
        <symbol id="i-copy" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="8" y="8" width="9" height="9" rx="1" />
          <path d="M5 12H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v1" strokeLinecap="round" />
        </symbol>
        <symbol id="i-info" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="10" cy="10" r="7.5" />
          <path d="M10 9v5M10 7v.5" strokeLinecap="round" />
        </symbol>
        <symbol id="i-alert" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M10 3 2 17h16L10 3z" strokeLinejoin="round" />
          <path d="M10 8v4M10 14.5v.5" strokeLinecap="round" />
        </symbol>
        <symbol id="i-back" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M12 5L7 10l5 5" strokeLinecap="round" strokeLinejoin="round" />
        </symbol>
        <symbol id="i-lock" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="4" y="9" width="12" height="9" rx="1.5" />
          <path d="M7 9V7a3 3 0 0 1 6 0v2" strokeLinecap="round" />
        </symbol>
        <symbol id="i-eye" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M2 10s3-6 8-6 8 6 8 6-3 6-8 6-8-6-8-6z" />
          <circle cx="10" cy="10" r="2.5" />
        </symbol>
        <symbol id="i-trash" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M4 6h12M8 6V4h4v2M7 9v6M13 9v6M5 6l1 10h8l1-10" strokeLinecap="round" strokeLinejoin="round" />
        </symbol>
        <symbol id="i-download" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M10 3v9M6 8l4 4 4-4M4 14v2a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-2" strokeLinecap="round" />
        </symbol>
        <symbol id="i-user" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="10" cy="6.5" r="3" />
          <path d="M3 17c0-3.3 3.1-6 7-6s7 2.7 7 6" strokeLinecap="round" />
        </symbol>
        <symbol id="i-home" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M3 9.5 10 3l7 6.5V17a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9.5z" strokeLinejoin="round" />
          <path d="M7 18v-6h6v6" strokeLinejoin="round" />
        </symbol>
      </svg>

      <div className="scr on" style={{ minHeight: "100vh" }}>
        {/* Navbar */}
        <nav className="nav">
          <div className="nav-inner">
            <Link href={isAuthenticated ? "/home" : "/"} style={{ textDecoration: "none" }}>
              <div className="logo"><b>News</b><i>IQ</i></div>
            </Link>
            <div className="nav-divider"></div>
            <span className="nav-pill">Legal</span>
            <div style={{ marginLeft: "auto", display: "flex", gap: "8px", alignItems: "center" }}>
              <span className="nav-back" onClick={() => { toast.info("Navigating back..."); router.push(isAuthenticated ? "/home" : "/"); }}>
                <svg width="14" height="14"><use href="#i-back" /></svg>Back to NewsIQ
              </span>
              <div style={{ width: "1px", height: "16px", background: "var(--border)", margin: "0 4px" }}></div>
              <button className="nibn" onClick={toggleTheme}>
                <svg width="16" height="16" className="ti">
                  <use href={isDark ? "#i-moon" : "#i-sun"} />
                </svg>
              </button>
            </div>
          </div>
        </nav>

        {children}
      </div>
    </>
  );
}
