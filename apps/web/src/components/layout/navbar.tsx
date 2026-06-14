"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { useState, useEffect } from "react";
import {
  Search,
  Sun,
  Moon,
  Bookmark,
  Bell,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const { user, isAuthenticated } = useAuthStore();
  const [searchQuery, setSearchQuery] = useState("");
  const [mounted, setMounted] = useState(false);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 0);
    return () => clearTimeout(t);
  }, []);

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?";

  const isLanding = pathname === "/";
  const isDark = mounted && theme === "dark";

  const navLinks = [
    { href: "/home", label: "Home", active: pathname === "/home" },
    { href: "/trending", label: "Trending", active: pathname === "/trending" },
    { href: "/search", label: "Search", active: pathname === "/search" },
  ];

  return (
    <nav className="nav">
      <div className="nav-inner">
        {/* Logo */}
        <Link href={isAuthenticated ? "/home" : "/"} style={{ textDecoration: "none" }}>
          <div className="logo">
            <b>News</b>
            <i>IQ</i>
          </div>
        </Link>

        {/* Search bar */}
        {!isLanding && (
          <form
            className="nsearch"
            onSubmit={(e) => {
              e.preventDefault();
              if (searchQuery.trim()) {
                router.push(`/search?q=${encodeURIComponent(searchQuery.trim())}`);
              }
            }}
          >
            <Search size={14} />
            <input
              type="text"
              placeholder="Search stories, topics, locations…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </form>
        )}

        {/* Nav links */}
        {!isLanding && isAuthenticated && (
          <div className="nlinks">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`nlink ${link.active ? "on" : ""}`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        )}

        {/* Landing nav links */}
        {isLanding && (
          <div className="nlinks">
            <Link href="/trending" className="nlink">Trending</Link>
            <Link href="/search" className="nlink">Categories</Link>
          </div>
        )}

        {/* Right actions */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginLeft: "auto" }}>
          {isAuthenticated ? (
            <>
              <Link href="/bookmarks">
                <button className="nibn" title="Bookmarks">
                  <Bookmark size={18} />
                </button>
              </Link>
              <Link href="/notifications">
                <button className="nibn" title="Notifications">
                  <Bell size={18} />
                </button>
              </Link>
              <button
                className="nibn"
                onClick={() => setTheme(isDark ? "light" : "dark")}
                title="Toggle theme"
              >
                {isDark ? <Moon size={16} /> : <Sun size={16} />}
              </button>
              <Link href="/profile">
                <div className="navtr">{initials}</div>
              </Link>
            </>
          ) : (
            <>
              <Link href="/login">
                <button className="btno" style={{ height: 34, padding: "0 14px", fontSize: 13 }}>
                  Sign in
                </button>
              </Link>
              <Link href="/signup">
                <button className="btnp" style={{ height: 34, padding: "0 14px" }}>
                  Get started
                </button>
              </Link>
              <button
                className="nibn"
                onClick={() => setTheme(isDark ? "light" : "dark")}
                title="Toggle theme"
              >
                {isDark ? <Moon size={16} /> : <Sun size={16} />}
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
