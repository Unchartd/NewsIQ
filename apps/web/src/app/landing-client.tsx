"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "sonner";
import "./landing.css";

export function LandingClientPage() {
  const { isAuthenticated, user } = useAuthStore();
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  // Avoid hydration mismatch for theme-dependent icons
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  // Scroll Reveal Observer
  useEffect(() => {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            revealObserver.unobserve(e.target);
          }
        });
      },
      { threshold: 0.08 },
    );
    document
      .querySelectorAll(".reveal")
      .forEach((el) => revealObserver.observe(el));
    return () => revealObserver.disconnect();
  }, []);

  // Counter Animation Observer
  useEffect(() => {
    function animateCounter(el: HTMLElement) {
      const targetVal = el.getAttribute("data-target");
      if (!targetVal) return;
      const target = parseInt(targetVal);
      const duration = 1600;
      const step = target / (duration / 16);
      let current = 0;
      const timer = setInterval(() => {
        current = Math.min(current + step, target);
        el.textContent = Math.floor(current).toLocaleString();
        if (current >= target) {
          clearInterval(timer);
          el.textContent = target.toLocaleString();
        }
      }, 16);
    }

    const counterObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target
              .querySelectorAll(".counter")
              .forEach((el) => animateCounter(el as HTMLElement));
            counterObserver.unobserve(e.target);
          }
        });
      },
      { threshold: 0.3 },
    );

    document
      .querySelectorAll(".stats-grid")
      .forEach((el) => counterObserver.observe(el));

    return () => counterObserver.disconnect();
  }, []);

  // Navbar scroll box-shadow
  useEffect(() => {
    const handleScroll = () => {
      const nav = document.querySelector(".nav") as HTMLElement;
      if (nav) {
        if (window.scrollY > 20) {
          nav.style.boxShadow =
            "0 1px 0 var(--landing-border), 0 4px 12px rgba(0,0,0,.05)";
        } else {
          nav.style.boxShadow = "none";
        }
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  };

  const showToast = (msg: string) => {
    toast.custom(() => (
      <div
        style={{
          background: "var(--landing-card)",
          border: "1px solid var(--landing-border)",
          borderLeft: "4px solid var(--landing-green)",
          borderRadius: "10px",
          padding: "11px 16px",
          fontSize: "13px",
          fontWeight: 500,
          color: "var(--landing-ink)",
          boxShadow: "0 20px 56px rgba(0,0,0,.14)",
          minWidth: "200px",
          fontFamily: "var(--landing-fb)",
        }}
      >
        {msg}
      </div>
    ));
  };

  const toggleFaq = (index: number) => {
    setOpenFaqIndex(openFaqIndex === index ? null : index);
  };

  const isDark = mounted && resolvedTheme === "dark";

  return (
    <div className="landing-body">
      {/* Signal Bar (signature brand element) */}
      <div className="signal-bar"></div>

      {/* ════════════════════════════════════════
           NAVBAR
           ════════════════════════════════════════ */}
      <nav className="nav">
        <div className="nav-inner">
          <div className="logo">
            <b>News</b>
            <i>IQ</i>
          </div>
          <div className="nav-links">
            <a className="nav-link" href="#features">
              Features
            </a>
            <a className="nav-link" href="#how">
              How it works
            </a>
            <a className="nav-link" href="#demo">
              See it live
            </a>
            {/* Pricing nav link — hidden for MVP, uncomment when pricing page is ready
            <a
              className="nav-link"
              href="#pricing"
              onClick={(e) => {
                e.preventDefault();
                document.getElementById("pricing")?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              Pricing
            </a>
            */}
          </div>
          <div className="nav-right">
            <button
              className="theme-btn"
              onClick={toggleTheme}
              id="themeBtn"
              title="Toggle theme"
            >
              {isDark ? (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  id="themeIcon"
                >
                  <path
                    d="M17 11.5A7 7 0 0 1 8.5 3a7 7 0 1 0 8.5 8.5z"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              ) : (
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  id="themeIcon"
                >
                  <circle cx="10" cy="10" r="3.5" />
                  <path
                    d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.42 1.42M14.36 14.36l1.42 1.42M4.22 15.78l1.42-1.42M14.36 5.64l1.42-1.42"
                    strokeLinecap="round"
                  />
                </svg>
              )}
            </button>
            {isAuthenticated ? (
              <Link href="/profile" title="Go to profile">
                <button className="nav-profile-btn" aria-label="Profile">
                  {user?.name?.[0]?.toUpperCase() ||
                    user?.email?.[0]?.toUpperCase() ||
                    "U"}
                </button>
              </Link>
            ) : (
              <Link href="/login">
                <button className="nav-sign-in">Sign in</button>
              </Link>
            )}
            <Link href={"/home"}>
              <button className="nav-cta">
                {isAuthenticated ? "Go to feed" : "Start reading free"}
              </button>
            </Link>
          </div>
        </div>
      </nav>

      {/* ════════════════════════════════════════
           HERO
           ════════════════════════════════════════ */}
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-badge reveal">
            <span className="hero-badge-dot"></span>
            AI-powered news intelligence
          </div>

          <h1 className="hero-title reveal reveal-delay-1">
            Understand the Story,
            <br />
            <em>Not Just the Headlines</em>
          </h1>

          <p className="hero-sub reveal reveal-delay-2">
            NewsIQ transforms dozens of articles into one clear story — with AI
            summaries, source comparisons, timelines, and transparent publisher
            links.
          </p>

          <div className="hero-btns reveal reveal-delay-3">
            <Link href={"/home"}>
              <button className="btn-primary">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                >
                  <path
                    d="M4 10h12M12 6l4 4-4 4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Start reading free
              </button>
            </Link>
            <button
              className="btn-secondary"
              onClick={() =>
                document
                  .getElementById("demo")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              Explore demo
            </button>
          </div>

          <div className="hero-stats reveal">
            <span>
              <b>12,000+</b> readers today
            </span>
            <span className="hero-stat-sep"></span>
            <span>
              <b>98%</b> clustering accuracy
            </span>
            <span className="hero-stat-sep"></span>
            <span>
              Updates every <b>5 minutes</b>
            </span>
            <span className="hero-stat-sep"></span>
            <span>
              <b>1,240</b> stories indexed
            </span>
          </div>

          {/* DASHBOARD MOCKUP */}
          <div className="hero-mockup reveal">
            {/* Browser chrome */}
            <div className="mockup-chrome">
              <div
                className="chrome-dot"
                style={{ background: "#FF5F57" }}
              ></div>
              <div
                className="chrome-dot"
                style={{ background: "#FFBD2E" }}
              ></div>
              <div
                className="chrome-dot"
                style={{ background: "#28C840" }}
              ></div>
              <div className="chrome-bar">
                newsiq.in/story/bengaluru-floods-2026
              </div>
              <div style={{ width: "24px" }}></div>
            </div>
            {/* Content */}
            <div className="mockup-body">
              <div className="mockup-main">
                <div className="mk-category">🌦️ Weather · Bengaluru</div>
                <div className="mk-headline">
                  Heavy monsoon rains flood Outer Ring Road and Marathahalli;
                  all city schools ordered closed
                </div>
                <div className="mk-meta">
                  <span
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                    }}
                  >
                    <span
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "#DC2626",
                        display: "inline-block",
                      }}
                    ></span>
                    <span
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "#1D4ED8",
                        display: "inline-block",
                        marginLeft: "2px",
                      }}
                    ></span>
                    <span
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "#16A34A",
                        display: "inline-block",
                        marginLeft: "2px",
                      }}
                    ></span>
                    <b
                      style={{ marginLeft: "5px", color: "var(--landing-ink)" }}
                    >
                      6 sources
                    </b>
                  </span>
                  <span className="mk-meta-dot"></span>
                  <span>3 hours ago</span>
                  <span className="mk-meta-dot"></span>
                  <span
                    style={{ color: "var(--landing-amber)", fontWeight: 600 }}
                  >
                    ↑ Trending
                  </span>
                </div>

                {/* AI Summary */}
                <div className="mk-summary-label">
                  <span style={{ color: "var(--landing-ink3)" }}>✦</span> AI
                  Summary
                </div>
                <div className="mk-summary-block">
                  IMD recorded 142mm rainfall in 6 hours — the highest in a
                  decade. BBMP deployed 40 pumping units across waterlogged
                  areas. BMTC suspended 12 routes serving Whitefield and
                  Electronic City. All city schools ordered closed for Friday by
                  the state government.
                </div>

                {/* Key facts */}
                <div className="mk-facts">
                  <div className="mk-fact">
                    <div className="mk-fact-lbl">Location</div>
                    <div className="mk-fact-val">Bengaluru</div>
                  </div>
                  <div className="mk-fact">
                    <div className="mk-fact-lbl">Rainfall</div>
                    <div className="mk-fact-val">142mm / 6h</div>
                  </div>
                  <div className="mk-fact">
                    <div className="mk-fact-lbl">Status</div>
                    <div
                      className="mk-fact-val"
                      style={{ color: "var(--landing-primary)" }}
                    >
                      Developing
                    </div>
                  </div>
                </div>

                {/* Timeline */}
                <div className="mk-timeline-label">How it unfolded</div>
                <div className="mk-tl">
                  <div className="mk-tl-item">
                    <div className="mk-tl-time">8:30 AM</div>
                    <div className="mk-tl-rail">
                      <div className="mk-tl-dot active"></div>
                      <div className="mk-tl-line"></div>
                    </div>
                    <div className="mk-tl-text">
                      Heavy rain begins across outer regions
                    </div>
                  </div>
                  <div className="mk-tl-item">
                    <div className="mk-tl-time">10:00 AM</div>
                    <div className="mk-tl-rail">
                      <div className="mk-tl-dot"></div>
                      <div className="mk-tl-line"></div>
                    </div>
                    <div className="mk-tl-text">
                      Outer Ring Road and Marathahalli flood
                    </div>
                  </div>
                  <div className="mk-tl-item">
                    <div className="mk-tl-time">11:15 AM</div>
                    <div className="mk-tl-rail">
                      <div className="mk-tl-dot"></div>
                      <div className="mk-tl-line"></div>
                    </div>
                    <div className="mk-tl-text">
                      BBMP issues citywide flood warning
                    </div>
                  </div>
                  <div className="mk-tl-item">
                    <div className="mk-tl-time">1:00 PM</div>
                    <div className="mk-tl-rail">
                      <div className="mk-tl-dot"></div>
                    </div>
                    <div className="mk-tl-text">
                      Schools ordered closed for Friday
                    </div>
                  </div>
                </div>
              </div>

              {/* Sidebar: Source Coverage */}
              <div className="mockup-side">
                <div className="mk-sources-label">Source Coverage</div>
                <div className="mk-source-row">
                  <div
                    className="mk-src-dot"
                    style={{ background: "#DC2626" }}
                  ></div>
                  <span className="mk-src-name">NDTV</span>
                  <span className="mk-src-focus">School closures</span>
                  <span className="mk-src-link">→</span>
                </div>
                <div className="mk-source-row">
                  <div
                    className="mk-src-dot"
                    style={{ background: "#D97706" }}
                  ></div>
                  <span className="mk-src-name">TOI</span>
                  <span className="mk-src-focus">Traffic disruption</span>
                  <span className="mk-src-link">→</span>
                </div>
                <div className="mk-source-row">
                  <div
                    className="mk-src-dot"
                    style={{ background: "#374151" }}
                  ></div>
                  <span className="mk-src-name">The Hindu</span>
                  <span className="mk-src-focus">Rainfall data</span>
                  <span className="mk-src-link">→</span>
                </div>
                <div className="mk-source-row">
                  <div
                    className="mk-src-dot"
                    style={{ background: "#065F46" }}
                  ></div>
                  <span className="mk-src-name">HT</span>
                  <span className="mk-src-focus">Govt response</span>
                  <span className="mk-src-link">→</span>
                </div>
                <div className="mk-source-row">
                  <div
                    className="mk-src-dot"
                    style={{ background: "#1D4ED8" }}
                  ></div>
                  <span className="mk-src-name">IE</span>
                  <span className="mk-src-focus">IMD forecast</span>
                  <span className="mk-src-link">→</span>
                </div>
                <div className="mk-source-row">
                  <div
                    className="mk-src-dot"
                    style={{ background: "#7C3AED" }}
                  ></div>
                  <span className="mk-src-name">Deccan</span>
                  <span className="mk-src-focus">Rescue ops</span>
                  <span className="mk-src-link">→</span>
                </div>

                {/* Coverage stats */}
                <div className="mk-coverage">
                  <div className="mk-cov-stat">
                    <div className="mk-cov-num">6</div>
                    <div className="mk-cov-lbl">Sources</div>
                  </div>
                  <div className="mk-cov-stat">
                    <div
                      className="mk-cov-num"
                      style={{ color: "var(--landing-amber)" }}
                    >
                      2
                    </div>
                    <div className="mk-cov-lbl">Conflicts</div>
                  </div>
                  <div className="mk-cov-stat">
                    <div
                      className="mk-cov-num"
                      style={{ color: "var(--landing-ink4)" }}
                    >
                      1
                    </div>
                    <div className="mk-cov-lbl">Missing</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        {/* /hero-inner */}
      </section>

      {/* ════════════════════════════════════════
           TRUSTED SOURCES MARQUEE
           ════════════════════════════════════════ */}
      <section className="sources-section">
        <div className="sources-label">
          Powered by trusted news sources worldwide
        </div>
        <div style={{ position: "relative" }}>
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              bottom: 0,
              width: "80px",
              background:
                "linear-gradient(to right,var(--landing-surface),transparent)",
              zIndex: 2,
              pointerEvents: "none",
            }}
          ></div>
          <div
            style={{
              position: "absolute",
              top: 0,
              right: 0,
              bottom: 0,
              width: "80px",
              background:
                "linear-gradient(to left,var(--landing-surface),transparent)",
              zIndex: 2,
              pointerEvents: "none",
            }}
          ></div>
          <div style={{ overflow: "hidden" }}>
            <div className="marquee-track">
              {/* Set 1 */}
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                Reuters
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#1D4ED8" }}
                ></div>
                Associated Press
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                BBC
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                CNN
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#374151" }}
                ></div>
                Bloomberg
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#065F46" }}
                ></div>
                The Guardian
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#1D4ED8" }}
                ></div>
                CNBC
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                NDTV
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#D97706" }}
                ></div>
                Times of India
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#374151" }}
                ></div>
                Indian Express
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                Hindustan Times
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#374151" }}
                ></div>
                Al Jazeera
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#7C3AED" }}
                ></div>
                Financial Times
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#065F46" }}
                ></div>
                The Hindu
              </div>
              {/* Set 2 (duplicate for seamless loop) */}
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                Reuters
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#1D4ED8" }}
                ></div>
                Associated Press
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                BBC
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                CNN
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#374151" }}
                ></div>
                Bloomberg
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#065F46" }}
                ></div>
                The Guardian
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#1D4ED8" }}
                ></div>
                CNBC
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                NDTV
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#D97706" }}
                ></div>
                Times of India
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#374151" }}
                ></div>
                Indian Express
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#DC2626" }}
                ></div>
                Hindustan Times
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#374151" }}
                ></div>
                Al Jazeera
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#7C3AED" }}
                ></div>
                Financial Times
              </div>
              <div className="source-chip">
                <div
                  className="src-color"
                  style={{ background: "#065F46" }}
                ></div>
                The Hindu
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           PROBLEM / SOLUTION
           ════════════════════════════════════════ */}
      <section className="section" id="problem">
        <div className="container">
          <div className="section-header center reveal">
            <div className="eyebrow">The problem</div>
            <h2 className="section-title">Information overload is broken</h2>
            <p className="section-sub">
              The modern news cycle forces you to read the same story ten times
              from ten different angles. There&apos;s a better way.
            </p>
          </div>

          <div className="prob-comparison reveal">
            {/* Traditional News */}
            <div className="prob-v-card prob-card-traditional">
              <div className="prob-card-hdr">
                <span className="prob-card-lbl">Traditional News</span>
                <div className="prob-card-icon">📰</div>
              </div>
              <div className="prob-timeline">
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">10 articles published</div>
                    <div className="prob-step-meta">
                      Same event, fragmented coverage
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">
                      10 different perspectives
                    </div>
                    <div className="prob-step-meta">
                      Conflicting narratives, no synthesis
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">Redundant reading</div>
                    <div className="prob-step-meta">
                      Repeating facts, missing context
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">
                      <strong>45 minutes</strong> of your day gone
                    </div>
                    <div className="prob-time-waste">
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      >
                        <circle cx="12" cy="12" r="10" />
                        <polyline points="12 6 12 12 16 14" />
                      </svg>
                      Time lost
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot final"></div>
                  </div>
                  <div className="prob-step-content">
                    <div
                      className="prob-step-txt"
                      style={{ color: "var(--landing-ink4)" }}
                    >
                      Still confused
                    </div>
                    <div className="prob-step-meta">
                      No clear picture of what happened
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* VS */}
            <div className="prob-vs-divider">
              <div className="prob-vs-line"></div>
              <div className="prob-vs-badge">VS</div>
              <div className="prob-vs-line"></div>
            </div>

            {/* NewsIQ */}
            <div className="prob-v-card prob-card-newsiq">
              <div className="prob-card-hdr">
                <span className="prob-card-lbl">NewsIQ</span>
                <div className="prob-card-icon">⚡</div>
              </div>
              <div className="prob-timeline">
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">10 articles ingested</div>
                    <div className="prob-step-meta">
                      Every source, automatically
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">AI clusters the event</div>
                    <div className="prob-step-meta">
                      Semantic grouping across sources
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">One structured story</div>
                    <div className="prob-step-meta">
                      All perspectives, organized
                    </div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot"></div>
                    <div className="prob-step-line"></div>
                  </div>
                  <div className="prob-step-content">
                    <div className="prob-step-txt">
                      <strong>Under 30 seconds</strong>
                    </div>
                    <div className="prob-time-save">⚡ 90x faster</div>
                  </div>
                </div>
                <div className="prob-step">
                  <div className="prob-step-conn">
                    <div className="prob-step-dot final"></div>
                  </div>
                  <div className="prob-step-content">
                    <div
                      className="prob-step-txt"
                      style={{
                        color: "var(--landing-primary)",
                        fontWeight: 700,
                      }}
                    >
                      Complete understanding
                    </div>
                    <div className="prob-step-meta">
                      Full context, zero redundancy
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="prob-summary reveal">
            <span className="prob-summary-txt">
              Turn <strong>45 minutes</strong> of noise into{" "}
              <strong>30 seconds</strong> of signal
            </span>
            <span className="prob-summary-arrow">→</span>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           HOW IT WORKS
           ════════════════════════════════════════ */}
      <section
        className="section"
        style={{
          background: "var(--landing-card)",
          borderTop: "1px solid var(--landing-border)",
          borderBottom: "1px solid var(--landing-border)",
        }}
        id="how"
      >
        <div className="container">
          <div className="section-header center reveal">
            <div className="eyebrow">How it works</div>
            <h2 className="section-title">From headlines to understanding</h2>
            <p className="section-sub">
              Seven automated steps from raw articles to structured intelligence
              — happening in under 5 minutes.
            </p>
          </div>
          <div className="how-grid-container reveal">
            <div className="how-grid">
              {/* Step 1 */}
              <div className="how-card">
                <div className="how-loader-area">
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-loader-icon">📡</div>
                </div>

                <h3 className="how-card-title">News Sources</h3>
                <p className="how-card-desc">
                  RSS, APIs & crawlers from 10,000+ publishers worldwide
                </p>
                <div className="how-card-footer">
                  <span className="how-tag">Ingesting</span>
                  <span className="how-time">~50K/min</span>
                </div>
              </div>

              {/* Step 2 */}
              <div className="how-card">
                <div className="how-loader-area">
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-loader-icon">📥</div>
                </div>
                <h3 className="how-card-title">Ingestion</h3>
                <p className="how-card-desc">
                  Articles collected and deduplicated in real time at scale
                </p>
                <div className="how-card-footer">
                  <span className="how-tag">Processing</span>
                  <span className="how-time">Stream OK</span>
                </div>
              </div>

              {/* Step 3 */}
              <div className="how-card">
                <div className="how-loader-area">
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-loader-icon">🧠</div>
                </div>
                <h3 className="how-card-title">AI Processing</h3>
                <p className="how-card-desc">
                  Embeddings & semantic similarity via Gemini models
                </p>
                <div className="how-card-footer">
                  <span className="how-tag">Vectorizing</span>
                  <span className="how-time">GPU Active</span>
                </div>
              </div>

              {/* Step 4 */}
              <div className="how-card">
                <div className="how-loader-area">
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-pulse-ring"></div>
                  <div className="how-loader-icon">🔗</div>
                </div>
                <h3 className="how-card-title">Clustering</h3>
                <p className="how-card-desc">
                  Related articles grouped into story objects by similarity
                </p>
                <div className="how-card-footer">
                  <span className="how-tag">Grouping</span>
                  <span className="how-time">1.2K groups</span>
                </div>
              </div>

              {/* Connector Line */}
              <div className="how-connector">
                <div className="how-connector-line">
                  <div className="how-connector-dot"></div>
                </div>
              </div>

              {/* Bottom Row */}
              <div className="how-bottom-row">
                {/* Step 5 */}
                <div className="how-card">
                  <div className="how-loader-area">
                    <div className="how-pulse-ring"></div>
                    <div className="how-pulse-ring"></div>
                    <div className="how-pulse-ring"></div>
                    <div className="how-loader-icon">📝</div>
                  </div>
                  <h3 className="how-card-title">Summaries</h3>
                  <p className="how-card-desc">
                    1-line, short & detailed AI summaries per story cluster
                  </p>
                  <div className="how-card-footer">
                    <span className="how-tag">Generating</span>
                    <span className="how-time">3 Tiers</span>
                  </div>
                </div>

                {/* Step 6 */}
                <div className="how-card">
                  <div className="how-loader-area">
                    <div className="how-pulse-ring"></div>
                    <div className="how-pulse-ring"></div>
                    <div className="how-pulse-ring"></div>
                    <div className="how-loader-icon">⚖️</div>
                  </div>
                  <h3 className="how-card-title">Difference Engine</h3>
                  <p className="how-card-desc">
                    Contradictions & gaps surfaced across all sources
                  </p>
                  <div className="how-card-footer">
                    <span className="how-tag">Analyzing</span>
                    <span className="how-time">Bias Check</span>
                  </div>
                </div>

                {/* Step 7 (Final) */}
                <div className="how-card final">
                  <div className="how-loader-area">
                    <div className="how-pulse-ring"></div>
                    <div className="how-pulse-ring"></div>
                    <div className="how-pulse-ring"></div>
                    <div className="how-loader-icon">📰</div>
                  </div>
                  <h3 className="how-card-title">NewsIQ Story</h3>
                  <p className="how-card-desc">
                    Ready to read in under 30 seconds with full context
                  </p>
                  <div className="how-card-footer">
                    <span className="how-tag">Publishing</span>
                    <span className="how-time">&lt;30s</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           FEATURES
           ════════════════════════════════════════ */}
      <section className="section" id="features">
        <div className="container">
          <div className="section-header reveal">
            <div className="eyebrow">Features</div>
            <h2 className="section-title">
              Everything you need to
              <br />
              understand the news
            </h2>
            <p className="section-sub">
              Built for people who care about what&apos;s happening — but can&apos;t spend
              hours finding out.
            </p>
          </div>
          <div className="features-grid reveal">
            {/* Row 1 */}
            <div
              className="feat-card wide"
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "24px",
                alignItems: "center",
              }}
            >
              <div>
                <div className="feat-icon">🎯</div>
                <div className="feat-title">AI Story Aggregation</div>
                <div className="feat-desc">
                  Dozens of articles about the same event become one structured
                  story. No duplicates. No noise. Just the complete picture —
                  with every source intact and visible.
                </div>
              </div>
              <div
                style={{
                  background: "var(--landing-surface)",
                  border: "1px solid var(--landing-border)",
                  borderRadius: "var(--landing-r10)",
                  padding: "16px",
                }}
              >
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    letterSpacing: ".07em",
                    textTransform: "uppercase",
                    color: "var(--landing-ink3)",
                    marginBottom: "10px",
                  }}
                >
                  12 articles → 1 story
                </div>
                <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "var(--landing-card)",
                      border: "1px solid var(--landing-border)",
                      borderRadius: "4px",
                      color: "var(--landing-ink3)",
                    }}
                  >
                    NDTV
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "var(--landing-card)",
                      border: "1px solid var(--landing-border)",
                      borderRadius: "4px",
                      color: "var(--landing-ink3)",
                    }}
                  >
                    TOI
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "var(--landing-card)",
                      border: "1px solid var(--landing-border)",
                      borderRadius: "4px",
                      color: "var(--landing-ink3)",
                    }}
                  >
                    The Hindu
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "var(--landing-card)",
                      border: "1px solid var(--landing-border)",
                      borderRadius: "4px",
                      color: "var(--landing-ink3)",
                    }}
                  >
                    Reuters
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "var(--landing-card)",
                      border: "1px solid var(--landing-border)",
                      borderRadius: "4px",
                      color: "var(--landing-ink3)",
                    }}
                  >
                    HT
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "var(--landing-card)",
                      border: "1px solid var(--landing-border)",
                      borderRadius: "4px",
                      color: "var(--landing-ink3)",
                    }}
                  >
                    IE
                  </span>
                  <span
                    style={{
                      fontSize: "11px",
                      padding: "3px 8px",
                      background: "rgba(196,30,58,.1)",
                      border: "1px solid rgba(196,30,58,.2)",
                      borderRadius: "4px",
                      color: "var(--landing-primary)",
                      fontWeight: 600,
                    }}
                  >
                    +6 more
                  </span>
                </div>
                <div
                  style={{
                    marginTop: "12px",
                    height: "3px",
                    background: "var(--landing-border)",
                    borderRadius: "99px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: "80%",
                      background: "var(--landing-primary)",
                      borderRadius: "99px",
                      animation: "loadBar 6s ease-in-out infinite alternate",
                    }}
                  ></div>
                </div>
                <style>{`@keyframes loadBar{from{width:40%}to{width:95%}}`}</style>
                <div
                  style={{
                    fontSize: "11px",
                    color: "var(--landing-ink4)",
                    marginTop: "6px",
                  }}
                >
                  Clustering confidence: 98.2%
                </div>
              </div>
            </div>

            <div className="feat-card">
              <div className="feat-icon">📊</div>
              <div className="feat-title">Source Comparison</div>
              <div className="feat-desc">
                See exactly what each publisher emphasised, what they missed,
                and where they contradict each other.
              </div>
            </div>

            {/* Row 2 */}
            <div className="feat-card">
              <div className="feat-icon">⏱️</div>
              <div className="feat-title">Multi-Level Summaries</div>
              <div className="feat-desc">
                Switch between 1-line, Short, and Detailed summaries to match
                your available time. From 8 words to 150.
              </div>
              <div style={{ marginTop: "14px", display: "flex", gap: "6px" }}>
                <div
                  style={{
                    padding: "5px 10px",
                    borderRadius: "var(--landing-r6)",
                    background: "var(--landing-primary)",
                    color: "#fff",
                    fontSize: "11px",
                    fontWeight: 700,
                  }}
                >
                  Short
                </div>
                <div
                  style={{
                    padding: "5px 10px",
                    borderRadius: "var(--landing-r6)",
                    background: "var(--landing-surface)",
                    border: "1px solid var(--landing-border)",
                    color: "var(--landing-ink3)",
                    fontSize: "11px",
                    fontWeight: 600,
                  }}
                >
                  1-line
                </div>
                <div
                  style={{
                    padding: "5px 10px",
                    borderRadius: "var(--landing-r6)",
                    background: "var(--landing-surface)",
                    border: "1px solid var(--landing-border)",
                    color: "var(--landing-ink3)",
                    fontSize: "11px",
                    fontWeight: 600,
                  }}
                >
                  Detailed
                </div>
              </div>
            </div>

            <div className="feat-card">
              <div className="feat-icon">📅</div>
              <div className="feat-title">Story Timeline</div>
              <div className="feat-desc">
                Understand how events evolved chronologically — from first
                report to latest update — with source attribution on every
                event.
              </div>
            </div>

            <div className="feat-card">
              <div className="feat-icon">📍</div>
              <div className="feat-title">Location-Based Feed</div>
              <div className="feat-desc">
                Drill from World → Country → State → City. Your Bengaluru news
                stays separate from global headlines.
              </div>
            </div>

            {/* Row 3 */}
            <div className="feat-card">
              <div className="feat-icon">🔥</div>
              <div className="feat-title">Trending Intelligence</div>
              <div className="feat-desc">
                Stories are scored by source count, recency, and velocity. See
                what&apos;s gaining coverage right now — not just what&apos;s newest.
              </div>
            </div>

            <div
              className="feat-card wide"
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "24px",
                alignItems: "center",
              }}
            >
              <div>
                <div className="feat-icon">⚖️</div>
                <div className="feat-title">The Difference Engine</div>
                <div className="feat-desc">
                  Our most distinctive feature: a table that shows every factual
                  discrepancy between publishers covering the same story.
                  Contradictions are flagged. Missing facts are surfaced. Hidden
                  gaps become visible.
                </div>
              </div>
              <div
                style={{
                  background: "var(--landing-surface)",
                  border: "1px solid var(--landing-border)",
                  borderRadius: "var(--landing-r10)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    fontSize: "9px",
                    fontWeight: 700,
                    letterSpacing: ".08em",
                    textTransform: "uppercase",
                    color: "var(--landing-ink3)",
                    padding: "10px 12px",
                    borderBottom: "1px solid var(--landing-border)",
                  }}
                >
                  Fact · Reuters · TechCrunch
                </div>
                <div
                  style={{
                    padding: "8px 12px",
                    borderBottom: "1px solid var(--landing-border)",
                    fontSize: "11px",
                    display: "flex",
                    gap: "8px",
                  }}
                >
                  <span
                    style={{
                      minWidth: "80px",
                      color: "var(--landing-ink)",
                      fontWeight: 600,
                    }}
                  >
                    Benchmark
                  </span>
                  <span>+40%</span>
                  <span
                    style={{
                      color: "var(--landing-amber)",
                      display: "flex",
                      alignItems: "center",
                      gap: "3px",
                    }}
                  >
                    ⚠ ~32%
                  </span>
                </div>
                <div
                  style={{
                    padding: "8px 12px",
                    borderBottom: "1px solid var(--landing-border)",
                    fontSize: "11px",
                    display: "flex",
                    gap: "8px",
                    background: "rgba(217,119,6,.04)",
                  }}
                >
                  <span
                    style={{
                      minWidth: "80px",
                      color: "var(--landing-ink)",
                      fontWeight: 600,
                    }}
                  >
                    Rollout date
                  </span>
                  <span>2 weeks</span>
                  <span style={{ color: "var(--landing-amber)" }}>
                    ⚠ &quot;No date&quot;
                  </span>
                </div>
                <div
                  style={{
                    padding: "8px 12px",
                    fontSize: "11px",
                    display: "flex",
                    gap: "8px",
                  }}
                >
                  <span
                    style={{
                      minWidth: "80px",
                      color: "var(--landing-ink)",
                      fontWeight: 600,
                    }}
                  >
                    India price
                  </span>
                  <span
                    style={{
                      color: "var(--landing-ink4)",
                      fontStyle: "italic",
                    }}
                  >
                    —
                  </span>
                  <span
                    style={{
                      color: "var(--landing-ink4)",
                      fontStyle: "italic",
                    }}
                  >
                    —
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           STORY DEMO
           ════════════════════════════════════════ */}
      <section
        className="section"
        style={{
          background: "var(--landing-card)",
          borderTop: "1px solid var(--landing-border)",
          borderBottom: "1px solid var(--landing-border)",
        }}
        id="demo"
      >
        <div className="container">
          <div className="section-header center reveal">
            <div className="eyebrow">Live example</div>
            <h2 className="section-title">See NewsIQ in action</h2>
            <p className="section-sub">
              This is a real NewsIQ story — the same layout you&apos;ll see every day
              in the app.
            </p>
          </div>
          <div className="demo-card reveal">
            {/* Header */}
            <div className="demo-header">
              <div className="demo-header-cat">🌦️ Weather · Bengaluru</div>
              <div className="demo-header-title">
                Heavy monsoon rains cause widespread flooding across Bengaluru,
                disrupting transport and forcing school closures
              </div>
              <div className="demo-header-meta">
                <span>6 sources</span>
                <span>·</span>
                <span>Updated 12 min ago</span>
                <span>·</span>
                <span>↑ High Trending</span>
              </div>
            </div>
            {/* Body */}
            <div className="demo-body">
              <div className="demo-col">
                <div className="demo-label">✦ AI Summary</div>
                <p className="demo-summary-text">
                  Continuous heavy rainfall since Tuesday night has caused
                  severe waterlogging across several key areas of Bengaluru. The
                  IMD recorded 142mm in just 6 hours — the highest single-day
                  rainfall in a decade. BBMP deployed 40 pumping units. The
                  state government ordered all city schools closed for Friday.
                  BMTC suspended 12 routes covering Whitefield and Electronic
                  City.
                </p>
                <div style={{ marginTop: "20px" }}>
                  <div className="demo-label">Key Facts</div>
                  <div className="demo-facts">
                    <div className="demo-fact-row">
                      <span className="demo-fact-key">Location</span>
                      <span className="demo-fact-val">
                        Bengaluru, Karnataka
                      </span>
                    </div>
                    <div className="demo-fact-row">
                      <span className="demo-fact-key">Category</span>
                      <span className="demo-fact-val">Weather</span>
                    </div>
                    <div className="demo-fact-row">
                      <span className="demo-fact-key">Rainfall</span>
                      <span className="demo-fact-val">142mm / 6h</span>
                    </div>
                    <div className="demo-fact-row">
                      <span className="demo-fact-key">Org</span>
                      <span className="demo-fact-val">BBMP, IMD, BMTC</span>
                    </div>
                    <div className="demo-fact-row">
                      <span className="demo-fact-key">Status</span>
                      <span
                        className="demo-fact-val"
                        style={{ color: "var(--landing-primary)" }}
                      >
                        Developing
                      </span>
                    </div>
                  </div>
                </div>
              </div>
              <div className="demo-col">
                <div className="demo-label">⏱ Timeline</div>
                <div>
                  <div className="demo-tl-item">
                    <span className="demo-tl-time">8:30 AM</span>
                    <span className="demo-tl-text">
                      Heavy rain begins across outer regions of Bengaluru
                    </span>
                  </div>
                  <div className="demo-tl-item">
                    <span className="demo-tl-time">10:00 AM</span>
                    <span className="demo-tl-text">
                      Outer Ring Road and Marathahalli begin flooding
                    </span>
                  </div>
                  <div className="demo-tl-item">
                    <span className="demo-tl-time">11:15 AM</span>
                    <span className="demo-tl-text">
                      BBMP issues citywide flood warning; 40 pumps deployed
                    </span>
                  </div>
                  <div className="demo-tl-item">
                    <span className="demo-tl-time">1:00 PM</span>
                    <span className="demo-tl-text">
                      State government orders all city schools closed Friday
                    </span>
                  </div>
                </div>
                <div style={{ marginTop: "20px" }}>
                  <div className="demo-label">📰 Source Coverage</div>
                  <div className="demo-src-row">
                    <div
                      className="demo-src-dot"
                      style={{ background: "#DC2626" }}
                    ></div>
                    <span
                      style={{
                        fontWeight: 600,
                        minWidth: "62px",
                        fontSize: "13px",
                      }}
                    >
                      NDTV
                    </span>
                    <span
                      style={{ color: "var(--landing-ink3)", fontSize: "12px" }}
                    >
                      School closures and parent panic
                    </span>
                  </div>
                  <div className="demo-src-row">
                    <div
                      className="demo-src-dot"
                      style={{ background: "#D97706" }}
                    ></div>
                    <span
                      style={{
                        fontWeight: 600,
                        minWidth: "62px",
                        fontSize: "13px",
                      }}
                    >
                      TOI
                    </span>
                    <span
                      style={{ color: "var(--landing-ink3)", fontSize: "12px" }}
                    >
                      Traffic congestion and commute chaos
                    </span>
                  </div>
                  <div className="demo-src-row">
                    <div
                      className="demo-src-dot"
                      style={{ background: "#374151" }}
                    ></div>
                    <span
                      style={{
                        fontWeight: 600,
                        minWidth: "62px",
                        fontSize: "13px",
                      }}
                    >
                      Indian Express
                    </span>
                    <span
                      style={{ color: "var(--landing-ink3)", fontSize: "12px" }}
                    >
                      IMD rainfall data and forecast
                    </span>
                  </div>
                  <div className="demo-src-row">
                    <div
                      className="demo-src-dot"
                      style={{ background: "#065F46" }}
                    ></div>
                    <span
                      style={{
                        fontWeight: 600,
                        minWidth: "62px",
                        fontSize: "13px",
                      }}
                    >
                      HT
                    </span>
                    <span
                      style={{ color: "var(--landing-ink3)", fontSize: "12px" }}
                    >
                      Government response and relief ops
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           STATS
           ════════════════════════════════════════ */}
      <section className="stats-section">
        <div className="container">
          <div className="stats-grid">
            <div className="stat-item reveal">
              <div className="stat-num">
                <span className="counter" data-target="12">
                  0
                </span>
                <span className="accent">k+</span>
              </div>
              <div className="stat-label">Readers today</div>
            </div>
            <div className="stat-item reveal reveal-delay-1">
              <div className="stat-num">
                <span className="counter" data-target="1240">
                  0
                </span>
                <span className="accent">+</span>
              </div>
              <div className="stat-label">Stories indexed daily</div>
            </div>
            <div className="stat-item reveal reveal-delay-2">
              <div className="stat-num">
                <span className="counter" data-target="98">
                  0
                </span>
                <span className="accent">%</span>
              </div>
              <div className="stat-label">Clustering accuracy</div>
            </div>
            <div className="stat-item reveal reveal-delay-3">
              <div className="stat-num">
                <span className="counter" data-target="50">
                  0
                </span>
                <span className="accent">+</span>
              </div>
              <div className="stat-label">Countries covered</div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           WHY DIFFERENT
           ════════════════════════════════════════ */}
      <section className="section" id="why-newsiq">
        <div className="container">
          <div className="section-header center reveal">
            <div className="eyebrow">Why NewsIQ</div>
            <h2 className="section-title">Built for understanding, not clicks</h2>
            <p className="section-sub">
              Other aggregators surface articles. NewsIQ explains stories.
            </p>
          </div>

          <div className="why-comparison reveal">
            {/* Google News */}
            <div className="why-card why-card-side">
              <div className="why-card-hdr">
                <div className="why-card-icon why-icon-google">🔍</div>
                <div className="why-card-name">Google News</div>
                <div className="why-card-tagline">
                  Lists article links from publishers. You click, you read, you repeat.
                </div>
              </div>
              <ul className="why-feat-list">
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-yes">✓</span>
                  <span className="why-feat-txt">Broad coverage</span>
                </li>
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-yes">✓</span>
                  <span className="why-feat-txt">Real-time updates</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No AI summaries</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No source comparison</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No Difference Engine</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">Clickbait headlines</span>
                </li>
              </ul>
              <div className="why-side-cta">
                <span className="why-side-lbl">Link aggregator</span>
              </div>
            </div>

            {/* NewsIQ */}
            <div className="why-card why-card-center">
              <div className="why-best-badge">Best Choice</div>
              <div className="why-card-hdr">
                <div className="why-card-icon why-icon-newsiq">📰</div>
                <div className="why-card-name">NewsIQ</div>
                <div className="why-card-tagline">
                  Understands stories. Surfaces contradictions. Gives you the full picture in 30 seconds.
                </div>
              </div>
              <ul className="why-feat-list">
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-star">★</span>
                  <span className="why-feat-txt">10,000+ sources</span>
                </li>
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-star">★</span>
                  <span className="why-feat-txt">AI story summaries</span>
                </li>
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-star">★</span>
                  <span className="why-feat-txt">Source comparison table</span>
                </li>
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-star">★</span>
                  <span className="why-feat-txt">Difference Engine</span>
                </li>
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-star">★</span>
                  <span className="why-feat-txt">Neutral headlines</span>
                </li>
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-star">★</span>
                  <span className="why-feat-txt">Story timelines</span>
                </li>
              </ul>
              <div className="why-center-cta">
                <span className="why-cta-txt">The complete news experience</span>
              </div>
            </div>

            {/* Traditional Aggregators */}
            <div className="why-card why-card-side">
              <div className="why-card-hdr">
                <div className="why-card-icon why-icon-traditional">📋</div>
                <div className="why-card-name">Traditional Aggregators</div>
                <div className="why-card-tagline">
                  Curated headline lists. Human editors. Limited AI. Still requires you to read.
                </div>
              </div>
              <ul className="why-feat-list">
                <li className="why-feat-item yes">
                  <span className="why-feat-icon why-icon-yes">✓</span>
                  <span className="why-feat-txt">Curated selection</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No AI clustering</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No source comparison</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No fact differences</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">No timelines</span>
                </li>
                <li className="why-feat-item no">
                  <span className="why-feat-icon why-icon-no">—</span>
                  <span className="why-feat-txt">Slow to update</span>
                </li>
              </ul>
              <div className="why-side-cta">
                <span className="why-side-lbl">Manual curation</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           TESTIMONIALS
           ════════════════════════════════════════ */}
      {/*  <section
        className="section"
        style={{
          background: "var(--landing-card)",
          borderTop: "1px solid var(--landing-border)",
          borderBottom: "1px solid var(--landing-border)",
        }}
      >
        <div className="container">
          <div className="section-header center reveal">
            <div className="eyebrow">What people say</div>
            <h2 className="section-title">Trusted by readers who matter</h2>
          </div>
          <div className="testimonials-grid reveal">
            <div className="testi-card">
              <div className="testi-stars">★★★★★</div>
              <p className="testi-quote">
                "I used to spend 40 minutes every morning reading the same
                Bengaluru flood story from 6 different papers. Now I get the
                full picture in under 2 minutes. The source comparison is
                genuinely brilliant."
              </p>
              <div className="testi-person">
                <div
                  className="testi-avatar"
                  style={{
                    background: "linear-gradient(135deg,#6B21A8,#4C1D95)",
                  }}
                >
                  A
                </div>
                <div>
                  <div className="testi-name">Aryan Mehta</div>
                  <div className="testi-role">Founder, Bengaluru · Startup</div>
                </div>
              </div>
            </div>
            <div className="testi-card">
              <div className="testi-stars">★★★★★</div>
              <p className="testi-quote">
                "As a journalist, the Difference Engine is something I've always
                wanted. Seeing NDTV report 5 deaths and TOI report 7 from the
                same event — flagged automatically — saves me hours of
                cross-checking."
              </p>
              <div className="testi-person">
                <div
                  className="testi-avatar"
                  style={{
                    background: "linear-gradient(135deg,#065F46,#047857)",
                  }}
                >
                  P
                </div>
                <div>
                  <div className="testi-name">Priya Venkataraman</div>
                  <div className="testi-role">
                    Senior Reporter, National Daily
                  </div>
                </div>
              </div>
            </div>
            <div className="testi-card">
              <div className="testi-stars">★★★★★</div>
              <p className="testi-quote">
                "My investment research workflow changed completely. I can track
                how the RBI policy story evolved across Bloomberg, ET, and Mint
                — all on one page, with contradictions highlighted. This is the
                future of news."
              </p>
              <div className="testi-person">
                <div
                  className="testi-avatar"
                  style={{
                    background: "linear-gradient(135deg,#1D4ED8,#1e40af)",
                  }}
                >
                  R
                </div>
                <div>
                  <div className="testi-name">Rohit Sharma</div>
                  <div className="testi-role">Portfolio Manager · Mumbai</div>
                </div>
              </div>
            </div>
            <div className="testi-card">
              <div className="testi-stars">★★★★★</div>
              <p className="testi-quote">
                "I'm a student trying to understand complex geopolitical events.
                The timeline feature alone is worth it — watching a story
                develop hour by hour, with different sources' takes, is
                something no textbook can do."
              </p>
              <div className="testi-person">
                <div
                  className="testi-avatar"
                  style={{
                    background: "linear-gradient(135deg,#D97706,#b45309)",
                  }}
                >
                  S
                </div>
                <div>
                  <div className="testi-name">Sneha Patel</div>
                  <div className="testi-role">MA Political Science, Delhi</div>
                </div>
              </div>
            </div>
            <div className="testi-card">
              <div className="testi-stars">★★★★★</div>
              <p className="testi-quote">
                "The daily digest is genuinely the first email I open every
                morning. 5 stories, 3 minutes, and I know everything important
                that happened overnight. The neutral AI headlines are a
                revelation after years of clickbait."
              </p>
              <div className="testi-person">
                <div
                  className="testi-avatar"
                  style={{
                    background: "linear-gradient(135deg,#0E7490,#155e75)",
                  }}
                >
                  K
                </div>
                <div>
                  <div className="testi-name">Kavya Nair</div>
                  <div className="testi-role">Product Manager · Hyderabad</div>
                </div>
              </div>
            </div>
            <div className="testi-card">
              <div className="testi-stars">★★★★★</div>
              <p className="testi-quote">
                "I track the US-India trade relationship for work. NewsIQ
                clusters all the relevant articles automatically, shows me who
                said what, and flags when Reuters and ET contradict each other.
                Indispensable."
              </p>
              <div className="testi-person">
                <div
                  className="testi-avatar"
                  style={{
                    background: "linear-gradient(135deg,#C41E3A,#8B1429)",
                  }}
                >
                  V
                </div>
                <div>
                  <div className="testi-name">Vikram Agarwal</div>
                  <div className="testi-role">
                    Trade Policy Analyst · New Delhi
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section> */}

      {/* ════════════════════════════════════════
           PRICING — MVP: commented out, enable when ready to launch pricing
           ════════════════════════════════════════ */}
      {/* PRICING_SECTION_START
      <section id="pricing" className="pricing-section reveal">
        <div className="container">
          <div className="pricing-eyebrow">
            <div className="eyebrow">Pricing</div>
          </div>
          <h2 className="pricing-title">
            Simple, transparent<br />
            <em>pricing that scales with you</em>
          </h2>
          <p className="pricing-sub">
            Source comparison & Difference Engine are free for everyone. Upgrade to unlock more stories and personalisation.
          </p>

          <div className="pricing-grid">
            FREE CARD — FREE PLAN
            <div className="pricing-card">
              <div className="pricing-plan-name">Free</div>
              <div className="pricing-price">₹0<span>/month</span></div>
              <div className="pricing-desc">For occasional readers who want to stay informed.</div>
              <div className="pricing-divider" />
              Features: 10 stories/day, 1-line summaries, Trending feed, Source comparison (Free tag), Difference Engine (Free tag), Personalised feed (no), AI chat (no), Ad-free (no)
            </div>

            PRO CARD
            <div className="pricing-card featured">
              <div className="pricing-badge">Most popular</div>
              <div className="pricing-plan-name">Pro</div>
              <div className="pricing-price">₹399<span>/month</span></div>
              Features: Unlimited stories, All 3 summary depths, Source comparison table, Difference Engine, Personalised feed, Daily digest email, Ad-free reading, AI chat (beta)
              CTA: Upgrade to Pro -> /premium or /signup
            </div>

            ENTERPRISE CARD
            <div className="pricing-card">
              <div className="pricing-plan-name">Enterprise</div>
              <div className="pricing-price" style={{ fontSize: '28px' }}>Custom</div>
              Features: Everything in Pro, REST API access, Bulk story exports, Advanced analytics, Dedicated support, SLA guarantees, Custom integrations
              CTA: Contact sales -> showToast
            </div>
          </div>

          CALLOUT: Source Comparison & Difference Engine are free for everyone
          NOTE: No credit card required · Free tier always available · Cancel Pro anytime · Students get 50% off at edu@newsiq.in
        </div>
      </section>
      PRICING_SECTION_END */}

      {/* ════════════════════════════════════════
           FAQ
           ════════════════════════════════════════ */}
      <section className="section">
        <div className="container-narrow">
          <div className="section-header center reveal">
            <div className="eyebrow">FAQ</div>
            <h2 className="section-title">Questions, answered</h2>
          </div>
          <div className="faq-list reveal">
            {[
              {
                q: "What exactly is NewsIQ?",
                a: "NewsIQ is an AI-powered news intelligence platform. Instead of showing you a list of articles, it groups all articles about the same event into one structured story — with a neutral headline, AI summaries at three depth levels, a chronological timeline, and a source comparison table showing how each publisher covered the story differently. Think of it as having a very well-read researcher brief you every morning.",
              },
              {
                q: "How are AI summaries generated?",
                a: "We use large language models (currently Gemini) to read all clustered articles and generate summaries at three depths: 1-line (~20 words), Short (~50 words), and Detailed (~150 words). Every summary includes a reference to its source articles — we never present AI-generated text without attribution. All summaries are marked with the ✦ symbol throughout the interface.",
              },
              {
                q: "Does NewsIQ create news or write its own articles?",
                a: "No. NewsIQ never creates or publishes original news content. We are a secondary source that aggregates, clusters, and summarises — always linking back to the original publisher. Every summary references the articles it was generated from. We are a comprehension tool, not a news outlet.",
              },
              {
                q: "Are original publisher sources preserved?",
                a: "Absolutely. Source transparency is a core principle of NewsIQ. Every story includes a Source Coverage table showing each publisher, their primary angle, their publication time, and a direct link to the original article. We never obscure where information came from.",
              },
              {
                q: "Which publishers does NewsIQ cover?",
                a: "We aggregate from 10,000+ sources globally, including Reuters, AP, BBC, Bloomberg, The Guardian, CNN, CNBC, and in India: NDTV, Times of India, The Hindu, Indian Express, Hindustan Times, Deccan Herald, and many more. We're constantly adding new sources. If you'd like a specific publication added, contact us at sources@newsiq.in.",
              },
              {
                q: "Can I compare coverage between publishers?",
                a: "Yes — and this is free for every user. Every story includes two comparison tools: the Source Coverage Table (showing what angle each publisher took) and the Difference Engine (a structured comparison of specific facts, flagging contradictions with a ⚠ symbol and missing facts with a — marker). We believe media transparency should be a right, not a premium feature.",
              },
              {
                q: "Is NewsIQ free?",
                a: "Absolutely. During early access, every NewsIQ feature is available for free with no limits. When paid plans are introduced, the free tier will include 10 stories per day, 1-line summaries, a trending feed, Source Comparison, and the Difference Engine, while Pro subscribers will enjoy unlimited stories, all summary depths, personalised feeds, Daily Digest emails, and an ad-free experience.",
              },
            ].map((faq, index) => {
              const isOpen = openFaqIndex === index;
              return (
                <div className={`faq-item ${isOpen ? "open" : ""}`} key={index}>
                  <div className="faq-q" onClick={() => toggleFaq(index)}>
                    {faq.q}
                    <span className="faq-chevron">
                      <svg
                        width="8"
                        height="6"
                        viewBox="0 0 10 6"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M1 1l4 4 4-4" />
                      </svg>
                    </span>
                  </div>
                  <div className="faq-a-wrapper">
                    <div className="faq-a-inner">
                      <div className="faq-a">{faq.a}</div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           FINAL CTA
           ════════════════════════════════════════ */}
      <section className="final-cta">
        <div className="container" style={{ position: "relative", zIndex: 1 }}>
          <div className="reveal">
            <div
              className="eyebrow"
              style={{
                color: "rgba(196,30,58,.85)",
                justifyContent: "center",
                display: "flex",
              }}
            >
              NewsIQ
            </div>
            <h2 className="final-cta-title">
              Stop reading ten articles.
              <br />
              <em>Start understanding the story.</em>
            </h2>
            <p className="final-cta-sub">
              AI-powered news intelligence with summaries, timelines, source
              comparisons, and transparent references. Free to start.
            </p>
            <div className="final-cta-btns">
              <Link href={isAuthenticated ? "/home" : "/signup"}>
                <button className="btn-white">
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 20 20"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <path
                      d="M4 10h12M12 6l4 4-4 4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  Start reading free
                </button>
              </Link>
              <button
                className="btn-ghost-white"
                onClick={() => showToast("Loading demo…")}
              >
                Explore NewsIQ
              </button>
            </div>
            <div
              style={{
                marginTop: "24px",
                fontSize: "13px",
                color: "rgba(255,255,255,.35)",
              }}
            >
              No credit card required · Free tier always available · Cancel Pro
              anytime
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════
           FOOTER
           ════════════════════════════════════════ */}
      <footer className="footer">
        <div className="container">
          <div className="footer-grid">
            {/* Brand */}
            <div className="footer-brand">
              <div className="logo">
                <b>News</b>
                <i>IQ</i>
              </div>
              <p className="footer-tagline">
                AI-powered news intelligence. Understand the world&apos;s events in
                under 30 seconds.
              </p>
              <div className="footer-social">
                <div
                  className="footer-social-btn"
                  onClick={() => showToast("Opening X…")}
                >
                  𝕏
                </div>
                <div
                  className="footer-social-btn"
                  onClick={() => showToast("Opening LinkedIn…")}
                >
                  in
                </div>
                <div
                  className="footer-social-btn"
                  onClick={() => showToast("Opening GitHub…")}
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path d="M10 2a8 8 0 0 0-2.53 15.59c.4.07.55-.17.55-.38v-1.33c-2.22.48-2.69-1.07-2.69-1.07-.36-.92-.88-1.17-.88-1.17-.72-.49.05-.48.05-.48.8.06 1.22.82 1.22.82.71 1.21 1.86.86 2.31.66.07-.52.28-.86.51-1.06-1.77-.2-3.63-.89-3.63-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 4 0c1.53-1.03 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.19c0 .21.15.46.55.38A8 8 0 0 0 10 2z" />
                  </svg>
                </div>
              </div>
            </div>
            {/* Product */}
            <div>
              <div className="footer-col-title">Product</div>
              <Link href="/home" className="footer-link">
                Home Feed
              </Link>
              <Link href="/trending" className="footer-link">
                Trending
              </Link>
              <Link href="/search" className="footer-link">
                Search
              </Link>
              <Link href="/home?tab=categories" className="footer-link">
                Categories
              </Link>
              <Link href="/premium" className="footer-link">
                Daily Digest
              </Link>
            </div>
            {/* Resources */}
            <div>
              <div className="footer-col-title">Resources</div>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Blog…")}
              >
                Blog
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Documentation…")}
              >
                Documentation
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening API…")}
              >
                API
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Status…")}
              >
                Status
              </a>
            </div>
            {/* Company */}
            <div>
              <div className="footer-col-title">Company</div>
              <a
                className="footer-link"
                onClick={() => showToast("Opening About…")}
              >
                About
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Careers…")}
              >
                Careers
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Press…")}
              >
                Press
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Contact…")}
              >
                Contact
              </a>
            </div>
            {/* Legal */}
            <div>
              <div className="footer-col-title">Legal</div>
              <Link href="/privacy" className="footer-link">
                Privacy Policy
              </Link>
              <Link href="/tos" className="footer-link">
                Terms of Service
              </Link>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Cookie Settings…")}
              >
                Cookie Settings
              </a>
              <a
                className="footer-link"
                onClick={() => showToast("Opening Grievance Officer…")}
              >
                Grievance Officer
              </a>
            </div>
          </div>
          <div className="footer-bottom">
            <span>
              © 2026 NewsIQ Technologies Private Limited. All rights reserved.
            </span>
            <div className="footer-bottom-links">
              <Link
                href="/privacy"
                className="footer-link"
                style={{ margin: 0 }}
              >
                Privacy
              </Link>
              <Link href="/tos" className="footer-link" style={{ margin: 0 }}>
                Terms
              </Link>
              <a
                className="footer-link"
                style={{ margin: 0 }}
                onClick={() => showToast("Opening Sitemap…")}
              >
                Sitemap
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
