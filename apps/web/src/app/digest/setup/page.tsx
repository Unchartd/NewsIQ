"use client";

import React, { useState, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { SidebarWidgets } from "@/components/sidebar/sidebar-widgets";
import { Navbar } from "@/components/layout/navbar";
import apiClient from "@/lib/api-client";
import type { Story } from "@/types";
import {
  ChevronLeft,
  ArrowRight,
  Check,
  Bell,
  Bookmark,
  Search,
  Mail,
  Smartphone,
  Send,
  Info,
  Clock,
  Calendar,
  Lock,
  Sun,
  Moon,
  Sparkles,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useAuthStore } from "@/stores/auth-store";
import { toast } from "sonner";
import { SignalBar } from "@/components/layout/signal-bar";

type Step = "intro" | "topics" | "schedule" | "channels" | "preview" | "confirm" | "success" | "manage";

const CATEGORIES = [
  { id: "politics", name: "Politics", icon: "🏛️", storiesPerDay: 24, color: "var(--cat-pol)" },
  { id: "technology", name: "Technology", icon: "💻", storiesPerDay: 18, color: "var(--cat-tec)" },
  { id: "business", name: "Business", icon: "📈", storiesPerDay: 15, color: "var(--cat-biz)" },
  { id: "sports", name: "Sports", icon: "⚽", storiesPerDay: 20, color: "var(--cat-spo)" },
  { id: "health", name: "Health", icon: "❤️", storiesPerDay: 10, color: "var(--cat-hlt)" },
  { id: "science", name: "Science", icon: "🔬", storiesPerDay: 8, color: "var(--cat-sci)" },
  { id: "world", name: "World", icon: "🌍", storiesPerDay: 22, color: "var(--cat-wld)" },
  { id: "weather", name: "Weather", icon: "🌦️", storiesPerDay: 6, color: "var(--cat-wea)" },
  { id: "entertainment", name: "Entertainment", icon: "🎬", storiesPerDay: 12, color: "var(--primary)" },
];

const TIMES = [
  { value: "6:00", label: "Early" },
  { value: "7:00", label: "Default" },
  { value: "8:00", label: "Later" },
  { value: "9:00", label: "Commute" },
];

const MIDDAY_TIMES = [
  { value: "12:00", label: "Noon" },
  { value: "1:00", label: "Lunch" },
  { value: "2:00", label: "After" },
  { value: "3:00", label: "Tea" },
];

const EVENING_TIMES = [
  { value: "5:00", label: "Early" },
  { value: "6:00", label: "Default" },
  { value: "7:00", label: "Dinner" },
  { value: "9:00", label: "Night" },
];

export default function DigestSetupPage() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Flow State
  const [step, setStep] = useState<Step>("intro");
  const [selectedCats, setSelectedCats] = useState<Set<string>>(new Set(["politics", "technology", "sports"]));
  const [storyCount, setStoryCount] = useState(5);
  const [prioritizeLocal, setPrioritizeLocal] = useState(true);
  const [includeWorld, setIncludeWorld] = useState(true);
  
  const [editions, setEditions] = useState({
    morning: true,
    midday: false,
    evening: false,
  });
  
  const [deliveryTimes, setDeliveryTimes] = useState({
    morning: "7:00",
    midday: "1:00",
    evening: "6:00",
  });
  
  const [frequency, setFrequency] = useState<"daily" | "weekdays" | "custom">("daily");
  const [customDays, setCustomDays] = useState<Set<string>>(new Set(["Mon", "Tue", "Wed", "Thu", "Fri"]));
  const [weeklyWrap, setWeeklyWrap] = useState(true);
  
  const [channels, setChannels] = useState({
    email: true,
    app: true,
    telegram: false,
    push: false,
  });
  
  const [emailFormat, setEmailFormat] = useState<"html" | "text">("html");
  const [isSubscribing, setIsSubscribing] = useState(false);

  const { data: trendingStories = [], isLoading: isTrendingLoading } = useQuery<Story[]>({
    queryKey: ["stories", "trending-sidebar"],
    queryFn: async () => {
      const response = await apiClient.get("/stories", {
        params: {
          trending: "true",
          limit: 4,
        },
      });
      return response.data;
    },
  });

  useEffect(() => {
    const fetchSettings = async () => {
      if (!isAuthenticated) {
        setMounted(true);
        return;
      }
      try {
        const response = await apiClient.get("/users/preferences");
        if (response.data && response.data.digest_settings) {
          const ds = response.data.digest_settings;
          if (response.data.categories) {
            setSelectedCats(new Set(response.data.categories));
          }
          if (ds.story_count !== undefined) setStoryCount(ds.story_count);
          if (ds.prioritize_local !== undefined) setPrioritizeLocal(ds.prioritize_local);
          if (ds.include_world !== undefined) setIncludeWorld(ds.include_world);
          if (ds.editions !== undefined) setEditions(ds.editions);
          if (ds.delivery_times !== undefined) setDeliveryTimes(ds.delivery_times);
          if (ds.frequency !== undefined) setFrequency(ds.frequency);
          if (ds.custom_days !== undefined) setCustomDays(new Set(ds.custom_days));
          if (ds.weekly_wrap !== undefined) setWeeklyWrap(ds.weekly_wrap);
          if (ds.channels !== undefined) setChannels(ds.channels);
          if (ds.email_format !== undefined) setEmailFormat(ds.email_format);
          
          setStep("manage");
        }
      } catch (err) {
        console.error("Failed to fetch digest settings", err);
      } finally {
        setMounted(true);
      }
    };
    fetchSettings();
  }, [isAuthenticated]);

  if (!mounted) return null;

  const toggleCat = (id: string) => {
    const next = new Set(selectedCats);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedCats(next);
  };

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

  const go = (s: Step) => {
    setStep(s);
    window.scrollTo(0, 0);
  };

  const handleSubscribe = async () => {
    if (!isAuthenticated) {
      toast.error("Please sign in to subscribe to the digest.");
      return;
    }
    setIsSubscribing(true);
    try {
      const payload = {
        categories: Array.from(selectedCats),
        story_count: storyCount,
        prioritize_local: prioritizeLocal,
        include_world: includeWorld,
        editions,
        delivery_times: deliveryTimes,
        frequency,
        custom_days: Array.from(customDays),
        weekly_wrap: weeklyWrap,
        channels,
        email_format: emailFormat,
      };
      await apiClient.post("/users/digests/setup", payload);
      go("success");
      toast.success("Subscribed! First digest arrives tomorrow 🎉");
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      console.error("Failed to subscribe to digest", error);
      toast.error(error.response?.data?.detail || "Failed to set up digest subscription. Please try again.");
    } finally {
      setIsSubscribing(false);
    }
  };

  const handleUnsubscribe = async () => {
    try {
      await apiClient.delete("/users/digests/unsubscribe");
      toast.success("Successfully unsubscribed from digest");
      
      // Reset settings states to default
      setSelectedCats(new Set(["politics", "technology", "sports"]));
      setStoryCount(5);
      setPrioritizeLocal(true);
      setIncludeWorld(true);
      setEditions({ morning: true, midday: false, evening: false });
      setDeliveryTimes({ morning: "7:00", midday: "1:00", evening: "6:00" });
      setFrequency("daily");
      setCustomDays(new Set(["Mon", "Tue", "Wed", "Thu", "Fri"]));
      setWeeklyWrap(true);
      setChannels({ email: true, app: true, telegram: false, push: false });
      setEmailFormat("html");

      go("intro");
    } catch (err) {
      console.error("Failed to unsubscribe", err);
      toast.error("Failed to unsubscribe. Please try again.");
    }
  };

  const handleBack = () => {
    if (step === "topics") go("intro");
    else if (step === "schedule") go("topics");
    else if (step === "channels") go("schedule");
    else if (step === "preview") go("channels");
    else if (step === "confirm") go("preview");
    else if (step === "manage") go("intro");
  };

  const getStepTitle = () => {
    if (step === "topics") return "Topics";
    if (step === "schedule") return "Schedule";
    if (step === "channels") return "Channels";
    if (step === "preview") return "Preview";
    if (step === "confirm") return "Confirm";
    if (step === "manage") return "Manage Digest";
    return undefined;
  };

  const getStepIndex = () => {
    if (step === "topics") return 1;
    if (step === "schedule") return 2;
    if (step === "channels") return 3;
    if (step === "preview") return 4;
    if (step === "confirm") return 5;
    return 0;
  };

  const renderStepBar = (current: number) => (
    <div className="step-wrap w-full">
      <div className="step-wrap-inner">
        <button 
          className="nibn" 
          style={{ width: 32, height: 32, flexShrink: 0, border: "1.5px solid var(--border)", position: "absolute", left: "0", top: "50%", transform: "translateY(-50%)" }}
          onClick={handleBack}
          title="Go back"
        >
          <ChevronLeft size={18} />
        </button>

        <div className="step-bar">
          {[
            { n: 1, l: "Topics" },
            { n: 2, l: "Schedule" },
            { n: 3, l: "Channels" },
            { n: 4, l: "Preview" },
            { n: 5, l: "Confirm" },
          ].map((s) => (
            <React.Fragment key={s.n}>
              <div className="step-node">
                <div className={`step-circle ${current === s.n ? "active" : current > s.n ? "done" : ""}`}>
                  {current > s.n ? <Check size={14} /> : s.n}
                </div>
                <div className={`step-label ${current === s.n ? "active" : current > s.n ? "done" : ""}`}>
                  {s.l}
                </div>
              </div>
              {s.n < 5 && <div className={`step-line ${current > s.n ? "done" : ""}`} />}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );

  const stepIndex = getStepIndex();
  const isIntroOrSuccess = step === "intro" || step === "success";

  return (
    <div className="min-h-screen bg-[var(--surface)] text-[var(--ink)] font-sans relative">
      <Navbar title="Digest Setup" />
      <div className="layout">
        <div className="mc mt-0">
          {!isIntroOrSuccess && step !== "manage" && renderStepBar(stepIndex)}

          <AnimatePresence mode="wait">
            {/* SCREEN 1: INTRO */}
            {step === "intro" && (
              <motion.div key="intro" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="page-onb" style={{ maxWidth: 680 }}>
                  <div style={{ padding: "40px 0 32px", textAlign: "center" }}>
                    <div style={{ 
                      width: 72, height: 72, borderRadius: "var(--r16)", 
                      background: "linear-gradient(135deg, #C41E3A, #8B1429)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      margin: "0 auto 20px", fontSize: 30, boxShadow: "0 8px 24px rgba(196,30,58,0.3)"
                    }}>📰</div>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: "var(--primary)", marginBottom: 12 }}>
                      NewsIQ Daily Digest
                    </div>
                    <h1 style={{ fontFamily: "var(--fd)", fontSize: 32, fontWeight: 600, color: "var(--ink)", lineHeight: 1.2, marginBottom: 14 }}>
                      Your world, briefed.<br />Every morning.
                    </h1>
                    <p style={{ fontSize: 16, color: "var(--ink3)", lineHeight: 1.7, maxWidth: 460, margin: "0 auto 32px" }}>
                      Top stories across your chosen topics, delivered at the exact time you pick. AI-summarised. Source-verified. Ready in 3 minutes.
                    </p>
                    <button className="btnp-onb" style={{ padding: "14px 32px", fontSize: 16, marginBottom: 12 }} onClick={() => go("topics")}>
                      Set up my digest
                      <ArrowRight size={16} />
                    </button>
                    <div style={{ fontSize: 13, color: "var(--ink3)" }}>Free for all users · No credit card needed</div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 32 }}>
                    {[
                      { i: "🎯", t: "Your topics only", d: "Choose exactly what categories matter to you" },
                      { i: "⏰", t: "Your schedule", d: "Pick morning, lunch, evening — or all three" },
                      { i: "✦", t: "AI-summarised", d: "Each story in 50 words. Full context, zero waffle" },
                    ].map((f) => (
                      <div key={f.t} className="crd crd-p" style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 24, marginBottom: 8 }}>{f.i}</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--ink)", marginBottom: 4 }}>{f.t}</div>
                        <div style={{ fontSize: 12, color: "var(--ink3)", lineHeight: 1.5 }}>{f.d}</div>
                      </div>
                    ))}
                  </div>

                  <div className="slbl">What it looks like</div>
                  <div style={{ border: "1px solid var(--border)", borderRadius: "var(--r10)", overflow: "hidden", marginBottom: 28, boxShadow: "var(--sh1)" }}>
                    <div style={{ background: "linear-gradient(135deg, #C41E3A, #8B1429)", padding: "16px 18px", color: "#fff" }}>
                      <div style={{ fontSize: 11, opacity: 0.75, marginBottom: 4, fontWeight: 600, letterSpacing: ".05em" }}>NEWSIQ · MORNING DIGEST</div>
                      <div style={{ fontFamily: "var(--fd)", fontSize: 18, fontWeight: 600 }}>Monday, June 16 · 7:00 AM</div>
                      <div style={{ fontSize: 12, opacity: 0.7, marginTop: 3 }}>Top 5 stories · ~3 min read · 8 sources avg</div>
                    </div>
                    <div style={{ padding: "16px 18px" }}>
                      {[
                        { n: 1, c: "Technology", cl: "var(--cat-tec)", t: "OpenAI releases GPT-5 with 40% reasoning improvement across 12 languages", m: "12 sources · 43 min ago" },
                        { n: 2, c: "Politics", cl: "var(--cat-pol)", t: "Supreme Court delivers landmark verdict on electoral bonds", m: "9 sources · 1h ago" },
                        { n: 3, c: "Business", cl: "var(--cat-biz)", t: "RBI holds repo rate at 6.5% for seventh consecutive meeting", m: "9 sources · 2h ago" },
                      ].map((s) => (
                        <div key={s.n} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: s.n < 3 ? "1px solid var(--border)" : "none" }}>
                          <span style={{ fontFamily: "var(--fd)", fontSize: 18, fontWeight: 700, color: s.n === 1 ? "var(--primary)" : "var(--border)", minWidth: 20 }}>{s.n}</span>
                          <div>
                            <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".06em", color: s.cl, marginBottom: 3 }}>{s.c}</div>
                            <div style={{ fontFamily: "var(--fd)", fontSize: 14, fontWeight: 500, color: "var(--ink)", marginBottom: 3, lineHeight: 1.3 }}>{s.t}</div>
                            <div style={{ fontSize: 11, color: "var(--ink3)" }}>{s.m}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ padding: "12px 18px", borderTop: "1px solid var(--border)", background: "var(--surface)", fontSize: 12, color: "var(--ink3)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span>+ 2 more stories</span>
                      <span style={{ color: "var(--blue)", fontWeight: 500, cursor: "pointer" }} onClick={() => go("preview")}>See full preview →</span>
                    </div>
                  </div>

                  <div style={{ textAlign: "center", paddingBottom: 20 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 4, marginBottom: 6 }}>
                      {[1, 2, 3, 4, 5].map((i) => <span key={i} style={{ color: "#F59E0B", fontSize: 14 }}>★</span>)}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--ink3)" }}>Loved by <strong style={{ color: "var(--ink)" }}>14,000+ readers</strong> · 4.8 rating</div>
                  </div>

                  <button className="btnp-onb btn-full" style={{ fontSize: 16, padding: 14 }} onClick={() => go("topics")}>
                    Get started — it&apos;s free
                    <ArrowRight size={16} />
                  </button>
                </div>
              </motion.div>
            )}

            {/* SCREEN 2: TOPICS */}
            {step === "topics" && (
              <motion.div key="topics" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="page-onb">
                  <div className="page-hdr">
                    <div className="page-hdr-icon">🎯</div>
                    <div className="page-hdr-step">Step 1 of 5</div>
                    <h1 className="page-hdr-title">What topics should your digest cover?</h1>
                    <p className="page-hdr-sub">Pick the categories that matter to you. Your digest will prioritise these — in the order they trend.</p>
                  </div>

                  <div className="slbl">
                    Choose categories 
                    <span id="topicCount" style={{ fontSize: 11, fontWeight: 600, color: "var(--primary)", background: "rgba(196,30,58,0.1)", padding: "1px 6px", borderRadius: 99, marginLeft: 4 }}>
                      {selectedCats.size} selected
                    </span>
                  </div>
                  <div className="cat-grid" style={{ marginBottom: 24 }}>
                    {CATEGORIES.map((cat) => (
                      <div key={cat.id} className={`cat-opt ${selectedCats.has(cat.id) ? "sel" : ""}`} onClick={() => toggleCat(cat.id)}>
                        <div className="cat-chk"><Check size={10} color="#fff" /></div>
                        <div className="cat-icon">{cat.icon}</div>
                        <div className="cat-name">{cat.name}</div>
                        <div className="cat-count">~{cat.storiesPerDay} stories/day</div>
                      </div>
                    ))}
                  </div>

                  <div className="slbl">Digest length</div>
                  <div className="crd crd-p" style={{ marginBottom: 24 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>Stories per digest</div>
                        <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>More stories = longer read time</div>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <button onClick={() => setStoryCount(Math.max(3, storyCount - 1))} style={{ width: 32, height: 32, borderRadius: "50%", border: "1.5px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: "var(--ink2)", cursor: "pointer", transition: "all .15s" }}>−</button>
                        <div style={{ minWidth: 60, textAlign: "center" }}>
                          <span style={{ fontFamily: "var(--fd)", fontSize: 24, fontWeight: 700, color: "var(--ink)" }}>{storyCount}</span>
                          <div style={{ fontSize: 11, color: "var(--ink3)" }}>~{Math.ceil(storyCount * 0.6)} min read</div>
                        </div>
                        <button onClick={() => setStoryCount(Math.min(15, storyCount + 1))} style={{ width: 32, height: 32, borderRadius: "50%", border: "1.5px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: "var(--ink2)", cursor: "pointer", transition: "all .15s" }}>+</button>
                      </div>
                    </div>
                    <input type="range" min="3" max="15" value={storyCount} onChange={(e) => setStoryCount(parseInt(e.target.value))} style={{ width: "100%", accentColor: "var(--primary)", height: 4, cursor: "pointer" }} />
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--ink3)", marginTop: 6 }}>
                      <span>3 stories · ~2 min</span>
                      <span>15 stories · ~8 min</span>
                    </div>
                  </div>

                  <div className="slbl">Location filter <span style={{ fontSize: 11, fontWeight: 400, color: "var(--ink3)", marginLeft: 4, letterSpacing: 0, textTransform: "none" }}>(optional)</span></div>
                  <div className="crd crd-p" style={{ marginBottom: 28 }}>
                    <div className="tog-row">
                      <div className="tog-info">
                        <div className="tog-label">Prioritise local & national news</div>
                        <div className="tog-sub">Include stories from India and Bengaluru at the top of your digest before world news</div>
                      </div>
                      <label className="toggle">
                        <input type="checkbox" checked={prioritizeLocal} onChange={(e) => setPrioritizeLocal(e.target.checked)} />
                        <div className="tog-track"></div>
                        <div className="tog-thumb"></div>
                      </label>
                    </div>
                    <div className="tog-row" style={{ borderBottom: "none" }}>
                      <div className="tog-info">
                        <div className="tog-label">Include world stories when local is quiet</div>
                        <div className="tog-sub">Fill remaining slots with top world stories if your local topics have fewer than {storyCount}</div>
                      </div>
                      <label className="toggle">
                        <input type="checkbox" checked={includeWorld} onChange={(e) => setIncludeWorld(e.target.checked)} />
                        <div className="tog-track"></div>
                        <div className="tog-thumb"></div>
                      </label>
                    </div>
                  </div>

                  <div className="btn-row" style={{ justifyContent: "flex-end" }}>
                    <button className="btnp-onb" onClick={() => go("schedule")}>
                      Continue — Schedule
                      <ArrowRight size={15} />
                    </button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* SCREEN 3: SCHEDULE */}
            {step === "schedule" && (
              <motion.div key="schedule" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="page-onb">
                  <div className="page-hdr">
                    <div className="page-hdr-icon">⏰</div>
                    <div className="page-hdr-step">Step 2 of 5</div>
                    <h1 className="page-hdr-title">When should we send<br />your digest?</h1>
                    <p className="page-hdr-sub">Choose one or more daily digests. Each is curated fresh at that time.</p>
                  </div>

                  <div className="slbl">Digest editions</div>
                  <div style={{ marginBottom: 24 }}>
                    <div className={`channel-opt ${editions.morning ? "sel" : ""}`} onClick={() => setEditions({...editions, morning: !editions.morning})} style={{ alignItems: "flex-start" }}>
                      <div className="ch-icon" style={{ background: "rgba(217,119,6,0.12)", fontSize: 22 }}>🌅</div>
                      <div style={{ flex: 1 }}>
                        <div className="ch-name">Morning Digest</div>
                        <div className="ch-desc">Start your day informed. Top stories from overnight and early morning.</div>
                        {editions.morning && (
                          <div style={{ marginTop: 10 }}>
                            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "var(--ink3)", marginBottom: 8 }}>Delivery time</div>
                            <div className="time-grid">
                              {TIMES.map((t) => (
                                <div key={t.value} className={`time-chip ${deliveryTimes.morning === t.value ? "sel" : ""}`} onClick={(e) => { e.stopPropagation(); setDeliveryTimes({...deliveryTimes, morning: t.value}); }}>
                                  <div className="tc-time">{t.value}</div>
                                  <div className="tc-label">{t.label}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="ch-sel-dot">{editions.morning && <Check size={10} color="#fff" />}</div>
                    </div>

                    <div className={`channel-opt ${editions.midday ? "sel" : ""}`} onClick={() => setEditions({...editions, midday: !editions.midday})} style={{ alignItems: "flex-start" }}>
                      <div className="ch-icon" style={{ background: "rgba(26,86,219,0.1)", fontSize: 22 }}>☀️</div>
                      <div style={{ flex: 1 }}>
                        <div className="ch-name">Midday Briefing</div>
                        <div className="ch-desc">Catch up on the morning&apos;s biggest developments during your lunch break.</div>
                        {editions.midday && (
                          <div style={{ marginTop: 10 }}>
                            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "var(--ink3)", marginBottom: 8 }}>Delivery time</div>
                            <div className="time-grid">
                              {MIDDAY_TIMES.map((t) => (
                                <div key={t.value} className={`time-chip ${deliveryTimes.midday === t.value ? "sel" : ""}`} onClick={(e) => { e.stopPropagation(); setDeliveryTimes({...deliveryTimes, midday: t.value}); }}>
                                  <div className="tc-time">{t.value}</div>
                                  <div className="tc-label">{t.label}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="ch-sel-dot">{editions.midday && <Check size={10} color="#fff" />}</div>
                    </div>

                    <div className={`channel-opt ${editions.evening ? "sel" : ""}`} onClick={() => setEditions({...editions, evening: !editions.evening})} style={{ alignItems: "flex-start" }}>
                      <div className="ch-icon" style={{ background: "rgba(107,33,168,0.1)", fontSize: 22 }}>🌆</div>
                      <div style={{ flex: 1 }}>
                        <div className="ch-name">Evening Wrap-Up</div>
                        <div className="ch-desc">End the day knowing everything that happened. Great for winding down.</div>
                        {editions.evening && (
                          <div style={{ marginTop: 10 }}>
                            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: "var(--ink3)", marginBottom: 8 }}>Delivery time</div>
                            <div className="time-grid">
                              {EVENING_TIMES.map((t) => (
                                <div key={t.value} className={`time-chip ${deliveryTimes.evening === t.value ? "sel" : ""}`} onClick={(e) => { e.stopPropagation(); setDeliveryTimes({...deliveryTimes, evening: t.value}); }}>
                                  <div className="tc-time">{t.value}</div>
                                  <div className="tc-label">{t.label}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="ch-sel-dot">{editions.evening && <Check size={10} color="#fff" />}</div>
                    </div>
                  </div>

                  <div className="slbl">Frequency</div>
                  <div className="freq-grid" style={{ marginBottom: 24 }}>
                    {[
                      { id: "daily", i: "📅", n: "Daily", d: "Mon – Sun every day" },
                      { id: "weekdays", i: "🗓️", n: "Weekdays", d: "Mon – Fri only" },
                      { id: "custom", i: "📆", n: "Custom", d: "Pick specific days" },
                    ].map((f) => (
                      <div key={f.id} className={`freq-opt ${frequency === f.id ? "sel" : ""}`} onClick={() => setFrequency(f.id as "daily" | "weekdays" | "custom")}>
                        <div className="freq-icon">{f.i}</div>
                        <div className="freq-name">{f.n}</div>
                        <div className="freq-desc">{f.d}</div>
                      </div>
                    ))}
                  </div>

                  {frequency === "custom" && (
                    <div style={{ marginBottom: 24 }}>
                      <div className="crd crd-p">
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 12 }}>Select days</div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                            <div key={d} className={`time-chip ${customDays.has(d) ? "sel" : ""}`} onClick={() => { const next = new Set(customDays); if (next.has(d)) next.delete(d); else next.add(d); setCustomDays(next); }} style={{ flex: 1, minWidth: 70 }}>
                              <div className="tc-time">{d}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="slbl">Weekly special</div>
                  <div className="crd crd-p" style={{ marginBottom: 28 }}>
                    <div className="tog-row" style={{ borderBottom: "none" }}>
                      <div className="tog-info">
                        <div className="tog-label" style={{ display: "flex", alignItems: "center", gap: 6 }}><span>🏆</span>Weekly Top Stories</div>
                        <div className="tog-sub">Every Sunday — the biggest stories of the past 7 days, with context on how they evolved</div>
                      </div>
                      <label className="toggle">
                        <input type="checkbox" checked={weeklyWrap} onChange={(e) => setWeeklyWrap(e.target.checked)} />
                        <div className="tog-track"></div>
                        <div className="tog-thumb"></div>
                      </label>
                    </div>
                  </div>

                  <div className="btn-row" style={{ justifyContent: "flex-end" }}>
                    <button className="btnp-onb" onClick={() => go("channels")}>Continue — Channels<ArrowRight size={15} /></button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* SCREEN 4: CHANNELS */}
            {step === "channels" && (
              <motion.div key="channels" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="page-onb">
                  <div className="page-hdr">
                    <div className="page-hdr-icon">📬</div>
                    <div className="page-hdr-step">Step 3 of 5</div>
                    <h1 className="page-hdr-title">Where should we send it?</h1>
                    <p className="page-hdr-sub">Choose one or more delivery channels. At least one is required.</p>
                  </div>

                  <div className="slbl">Delivery channels</div>
                  
                  <div className={`channel-opt ${channels.email ? "sel" : ""}`} onClick={() => setChannels({...channels, email: !channels.email})}>
                    <div className="ch-icon" style={{ background: "rgba(26,86,219,0.1)" }}><Mail size={22} color="var(--blue)" /></div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                        <div className="ch-name">Email</div>
                        <span className="ch-badge ch-free">Free</span>
                      </div>
                      <div className="ch-desc">Beautifully formatted HTML digest — includes summaries, source links, and story timeline.</div>
                      {channels.email && (
                        <div style={{ marginTop: 10 }}>
                          <input type="email" defaultValue={user?.email || "aarav.mehta@gmail.com"} className="email-input" style={{ height: 38, fontSize: 13 }} onClick={(e) => e.stopPropagation()} />
                          <div style={{ fontSize: 11, color: "var(--green)", marginTop: 4, display: "flex", alignItems: "center", gap: 4 }}><Check size={11} />Verified email</div>
                        </div>
                      )}
                    </div>
                    <div className="ch-sel-dot">{channels.email && <Check size={10} color="#fff" />}</div>
                  </div>

                  <div className={`channel-opt ${channels.app ? "sel" : ""}`} onClick={() => setChannels({...channels, app: !channels.app})}>
                    <div className="ch-icon" style={{ background: "rgba(22,163,74,0.1)" }}><Bell size={22} color="var(--green)" /></div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                        <div className="ch-name">In-app feed</div>
                        <span className="ch-badge ch-free">Free</span>
                      </div>
                      <div className="ch-desc">A dedicated Digest tab in NewsIQ — read your briefing directly in the app, any time.</div>
                    </div>
                    <div className="ch-sel-dot">{channels.app && <Check size={10} color="#fff" />}</div>
                  </div>

                  <div className={`channel-opt ${channels.telegram ? "sel" : ""}`} onClick={() => setChannels({...channels, telegram: !channels.telegram})}>
                    <div className="ch-icon" style={{ background: "rgba(0,136,204,0.1)" }}><Send size={22} color="#0088cc" /></div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                        <div className="ch-name">Telegram</div>
                        <span className="ch-badge ch-free">Free</span>
                      </div>
                      <div className="ch-desc">Get your digest as a Telegram message. Connect once — works on mobile and desktop.</div>
                      {channels.telegram && <div style={{ marginTop: 8 }}><button className="btno-onb btnsm" onClick={(e) => { e.stopPropagation(); toast.info("Connecting Telegram..."); }} style={{ fontSize: 12 }}>Connect Telegram →</button></div>}
                    </div>
                    <div className="ch-sel-dot">{channels.telegram && <Check size={10} color="#fff" />}</div>
                  </div>

                  <div className="channel-opt" style={{ marginBottom: 8, opacity: 0.7, cursor: "default" }}>
                    <div className="ch-icon" style={{ background: "rgba(37,211,102,0.1)" }}><span style={{ fontSize: 22 }}>💬</span></div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                        <div className="ch-name">WhatsApp</div>
                        <span className="ch-badge ch-coming">Coming soon</span>
                      </div>
                      <div className="ch-desc">Digest as a WhatsApp message. Launching Q3 2026.</div>
                    </div>
                    <div className="ch-sel-dot"></div>
                  </div>

                  <div className={`channel-opt ${channels.push ? "sel" : ""}`} onClick={() => setChannels({...channels, push: !channels.push})} style={{ marginBottom: 24 }}>
                    <div className="ch-icon" style={{ background: "rgba(196,30,58,0.1)" }}><Smartphone size={22} color="var(--primary)" /></div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                        <div className="ch-name">Push notification</div>
                        <span className="ch-badge ch-free">Free</span>
                      </div>
                      <div className="ch-desc">A brief push alert with headline count. Tap to open the full digest in-app.</div>
                    </div>
                    <div className="ch-sel-dot">{channels.push && <Check size={10} color="#fff" />}</div>
                  </div>

                  <div className="slbl">Email format <span style={{ fontSize: 11, fontWeight: 400, color: "var(--ink3)", marginLeft: 4, letterSpacing: 0, textTransform: "none" }}>(when email is selected)</span></div>
                  <div className="crd crd-p" style={{ marginBottom: 24 }}>
                    <div className={`radio-opt ${emailFormat === "html" ? "sel" : ""}`} onClick={() => setEmailFormat("html")}>
                      <div className="radio-circle"><div className="radio-dot"></div></div>
                      <div style={{ flex: 1 }}><div className="radio-main">Rich HTML</div><div className="radio-desc">Full formatting with category colours, source links, and story summaries. Looks great on mobile.</div></div>
                      <span className="radio-badge">Recommended</span>
                    </div>
                    <div className={`radio-opt ${emailFormat === "text" ? "sel" : ""}`} onClick={() => setEmailFormat("text")}>
                      <div className="radio-circle"><div className="radio-dot"></div></div>
                      <div style={{ flex: 1 }}><div className="radio-main">Plain text</div><div className="radio-desc">No images or styling — just headlines and summaries. Works in all email clients.</div></div>
                    </div>
                  </div>

                  <div className="btn-row" style={{ justifyContent: "flex-end" }}>
                    <button className="btnp-onb" onClick={() => go("preview")}>Preview digest<ArrowRight size={15} /></button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* SCREEN 5: PREVIEW */}
            {step === "preview" && (
              <motion.div key="preview" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="page-onb" style={{ maxWidth: 680 }}>
                  <div className="page-hdr">
                    <div className="page-hdr-icon">👁️</div>
                    <div className="page-hdr-step">Step 4 of 5</div>
                    <h1 className="page-hdr-title">Here&apos;s what your digest<br />will look like</h1>
                    <p className="page-hdr-sub">This is a real preview built from today&apos;s top stories in your chosen topics.</p>
                  </div>

                  <div className="digest-preview" style={{ marginBottom: 24 }}>
                    <div className="dp-header">
                      <div className="dp-logo"><Sparkles size={14} style={{ opacity: 0.8 }} /> NewsIQ · Morning Digest</div>
                      <div className="dp-title">Monday, June 16 · 7:00 AM</div>
                      <div className="dp-meta"><span>{storyCount} stories</span><span>·</span><span>~{Math.ceil(storyCount * 0.6)} min read</span><span>·</span><span>{selectedCats.size} topics</span></div>
                    </div>
                    <div className="dp-body">
                      <div className="dp-section-lbl">🎯 {Array.from(selectedCats).map(c => CATEGORIES.find(cat => cat.id === c)?.name).join(" · ")}</div>
                      {[
                        { n: 1, c: "Technology", cl: "var(--cat-tec)", t: "OpenAI releases GPT-5 with 40% reasoning improvement and native multimodal capabilities", s: "OpenAI launched GPT-5, scoring 40% higher on MMLU benchmarks. Enterprise pricing starts at $60/M tokens. Consumer rollout in two weeks.", m: "12 sources · 43 min ago" },
                        { n: 2, c: "Politics", cl: "var(--cat-pol)", t: "Supreme Court delivers landmark verdict on electoral bonds, orders SBI to disclose donor data", s: "The court ordered SBI to release all electoral bond data within 24 hours. Opposition parties hailed the ruling.", m: "9 sources · 1h ago" },
                        { n: 3, c: "Politics", cl: "var(--cat-pol)", t: "Parliament session extended two weeks as opposition demands debate on data protection bill", s: "Three opposition parties walked out before agreeing to the extension. The bill faces scrutiny over consent provisions.", m: "7 sources · 2h ago" },
                        { n: 4, c: "Sports", cl: "var(--cat-spo)", t: "India advances to ICC Champions Trophy semi-final after dramatic win over Australia in Chennai", s: "Kohli scored 94 off 88 balls as India chased 287 with 3 wickets in hand. Semi-final against South Africa on June 20.", m: "11 sources · 5h ago" },
                        { n: 5, c: "Technology", cl: "var(--cat-tec)", t: "Google announces Pixel 10 Pro with on-device Gemini Nano 2 and 7-year software guarantee", s: "The Pixel 10 Pro ships with dedicated AI chips running Gemini Nano 2 fully offline. Available India pricing: ₹89,999 from July 4.", m: "8 sources · 6h ago" },
                      ].slice(0, storyCount).map((s) => (
                        <div key={s.n} className="dp-story" style={{ borderBottom: s.n === Math.min(storyCount, 5) ? "none" : "1px solid var(--border)" }}>
                          <div className={`dp-rank ${s.n === 1 ? "r1" : ""}`}>{s.n}</div>
                          <div className="dp-stbody">
                            <div className="dp-st-cat" style={{ color: s.cl }}>{s.c}</div>
                            <div className="dp-st-title">{s.t}</div>
                            <div className="dp-st-sum">{s.s}</div>
                            <div className="dp-st-srcs"><div style={{ display: "flex", gap: 3 }}><div style={{ width: 6, height: 6, borderRadius: "50%", background: "#DC2626" }}></div><div style={{ width: 6, height: 6, borderRadius: "50%", background: "#1D4ED8" }}></div><div style={{ width: 6, height: 6, borderRadius: "50%", background: "#16A34A" }}></div></div>{s.m}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="dp-footer"><div className="dp-footer-txt">Sent by NewsIQ · {user?.email || "aarav.mehta@gmail.com"}</div><div style={{ display: "flex", gap: 12 }}><span className="dp-footer-link">Unsubscribe</span><span className="dp-footer-link">Manage digest</span></div></div>
                  </div>

                  <div className="info-box green" style={{ marginBottom: 24 }}>
                    <Info size={16} style={{ color: "var(--green)", flexShrink: 0, marginTop: 1 }} />
                    <div className="info-txt">This preview uses today&apos;s real stories. Every digest is freshly curated — stories are re-ranked at delivery time to reflect what&apos;s most important right now.</div>
                  </div>

                  <div className="btn-row" style={{ justifyContent: "flex-end" }}>
                    <button className="btnp-onb" onClick={() => go("confirm")}>Looks good — confirm<ArrowRight size={15} /></button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* SCREEN 6: CONFIRM */}
            {step === "confirm" && (
              <motion.div key="confirm" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
                <div className="page-onb">
                  <div className="page-hdr">
                    <div className="page-hdr-icon">✅</div>
                    <div className="page-hdr-step">Step 5 of 5</div>
                    <h1 className="page-hdr-title">Review your digest settings</h1>
                    <p className="page-hdr-sub">Everything look right? You can change any of this later in your profile.</p>
                  </div>

                  <div className="crd" style={{ marginBottom: 20, overflow: "hidden" }}>
                    <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "flex-start", gap: 12 }}>
                      <div style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(196,30,58,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 16 }}>🎯</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>TOPICS · {selectedCats.size} SELECTED</div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {Array.from(selectedCats).map(c => (
                            <span key={c} className="topic-tag">
                              <span style={{ color: "var(--primary)", marginRight: 4 }}>●</span>
                              {CATEGORIES.find(cat => cat.id === c)?.name}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", padding: "4px 8px", background: "none", border: "none" }} onClick={() => go("topics")}>Edit</button>
                    </div>

                    <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "flex-start", gap: 12 }}>
                      <div style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(217,119,6,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 16 }}>⏰</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>SCHEDULE</div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)", marginBottom: 3 }}>
                          {editions.morning && `Morning (${deliveryTimes.morning})`}
                          {editions.midday && `${editions.morning ? ", " : ""}Midday (${deliveryTimes.midday})`}
                          {editions.evening && `${(editions.morning || editions.midday) ? ", " : ""}Evening (${deliveryTimes.evening})`}
                          {` · ${frequency.charAt(0).toUpperCase() + frequency.slice(1)}`}
                        </div>
                        <div style={{ fontSize: 13, color: "var(--ink3)" }}>{storyCount} stories per digest · ~{Math.ceil(storyCount * 0.6)} min read · {weeklyWrap ? "+ Weekly wrap-up" : "No weekly wrap"}</div>
                      </div>
                      <button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", padding: "4px 8px", background: "none", border: "none" }} onClick={() => go("schedule")}>Edit</button>
                    </div>

                    <div style={{ padding: "16px 20px", display: "flex", alignItems: "flex-start", gap: 12 }}>
                      <div style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(26,86,219,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 16 }}>📬</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, color: "var(--ink3)", marginBottom: 5, fontWeight: 600 }}>DELIVERY CHANNELS</div>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          {channels.email && <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)", display: "flex", alignItems: "center", gap: 6 }}><Mail size={14} color="var(--blue)" /> Email · {user?.email || "aarav.mehta@gmail.com"} · {emailFormat.toUpperCase()}</div>}
                          {channels.app && <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)", display: "flex", alignItems: "center", gap: 6 }}><Bell size={14} color="var(--green)" /> In-app digest feed</div>}
                          {channels.telegram && <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)", display: "flex", alignItems: "center", gap: 6 }}><Send size={14} color="#0088cc" /> Telegram</div>}
                        </div>
                      </div>
                      <button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", padding: "4px 8px", background: "none", border: "none" }} onClick={() => go("channels")}>Edit</button>
                    </div>
                  </div>

                  <div className="info-box green" style={{ marginBottom: 24 }}>
                    <Clock size={16} style={{ color: "var(--green)", flexShrink: 0, marginTop: 1 }} />
                    <div className="info-txt"><strong style={{ color: "var(--ink)" }}>First digest arrives tomorrow, Monday June 16 at 7:00 AM.</strong> You&apos;ll get a confirmation email right after subscribing.</div>
                  </div>

                  <div className="crd crd-p" style={{ marginBottom: 24 }}>
                    <div className="tog-row" style={{ borderBottom: "none" }}>
                      <div className="tog-info"><div className="tog-label">I agree to receive the NewsIQ Digest</div><div className="tog-sub">You can unsubscribe any time from the footer of any digest email or from your profile settings.</div></div>
                      <label className="toggle"><input type="checkbox" defaultChecked id="consent" /><div className="tog-track"></div><div className="tog-thumb"></div></label>
                    </div>
                  </div>

                  <div className="btn-row" style={{ justifyContent: "flex-end", marginBottom: 12 }}>
                    <button className="btnp-onb" style={{ flex: 1 }} onClick={handleSubscribe} disabled={isSubscribing}>
                      {isSubscribing ? (
                        <span style={{ display: "flex", alignItems: "center", gap: 8 }}><div style={{ width: 18, height: 18, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }}></div>Subscribing…</span>
                      ) : (<><Bell size={18} />Subscribe — it&apos;s free</>)}
                    </button>
                  </div>
                  <div style={{ textAlign: "center", fontSize: 12, color: "var(--ink3)" }}><Lock size={12} style={{ display: "inline", marginRight: 4 }} />No spam. Unsubscribe with one click. We never share your email.</div>
                </div>
              </motion.div>
            )}

            {/* SCREEN 7: SUCCESS */}
            {step === "success" && (
              <motion.div key="success" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}>
                <div className="success-wrap">
                  <div className="success-icon"><Check size={38} color="var(--green)" /></div>
                  <h1 className="success-title">You&apos;re subscribed! 🎉</h1>
                  <p className="success-sub">Your first NewsIQ Morning Digest lands in your inbox tomorrow at <strong>7:00 AM</strong>. We&apos;ve also sent you a confirmation email.</p>
                  <div className="success-card">
                    <div className="sc-row"><div className="sc-icon"><Bell size={16} /></div><div><div className="sc-lbl">Digest edition</div><div className="sc-val">🌅 Morning Digest · Daily</div></div></div>
                    <div className="sc-row"><div className="sc-icon"><Clock size={16} /></div><div><div className="sc-lbl">Delivery time</div><div className="sc-val">7:00 AM · First on Jun 16</div></div></div>
                    <div className="sc-row"><div className="sc-icon"><Smartphone size={16} /></div><div><div className="sc-lbl">Stories per digest</div><div className="sc-val">{storyCount} stories · ~{Math.ceil(storyCount * 0.6)} min read</div></div></div>
                    <div className="sc-row"><div className="sc-icon"><Mail size={16} /></div><div><div className="sc-lbl">Sending to</div><div className="sc-val">{user?.email || "aarav.mehta@gmail.com"}</div></div></div>
                    <div className="sc-row" style={{ borderBottom: "none" }}><div className="sc-icon" style={{ background: "rgba(196,30,58,0.08)" }}><Sparkles size={14} color="var(--primary)" /></div><div><div className="sc-lbl">Topics</div><div className="sc-val">{Array.from(selectedCats).map(c => CATEGORIES.find(cat => cat.id === c)?.name).join(" · ")}</div></div></div>
                  </div>
                  <div style={{ textAlign: "left", width: "100%", maxWidth: 420, marginBottom: 28 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".09em", textTransform: "uppercase", color: "var(--ink3)", marginBottom: 12 }}>While you wait…</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                      {[
                        { i: "⚙️", t: "Manage your digest settings", d: "Change topics, time, or channels anytime", a: () => go("manage") },
                        { i: "🏠", t: "Browse today's stories", d: "Don't wait — catch up on the feed right now", a: () => router.push("/home") },
                        { i: "👁️", t: "Preview today's digest", d: "See what tomorrow's would look like right now", a: () => go("preview") },
                      ].map((item, idx) => (
                        <div key={idx} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", background: "var(--card)", border: "1px solid var(--border)", borderRadius: "var(--r6)", cursor: "pointer", transition: "box-shadow 0.15s" }} onClick={item.a}>
                          <span style={{ fontSize: 18 }}>{item.i}</span>
                          <div style={{ flex: 1 }}><div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)" }}>{item.t}</div><div style={{ fontSize: 12, color: "var(--ink3)" }}>{item.d}</div></div>
                          <ArrowRight size={14} color="var(--ink3)" />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* SCREEN 8: MANAGE */}
            {step === "manage" && (
              <motion.div key="manage" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="page-onb" style={{ maxWidth: 660 }}>
                  <div className="page-hdr" style={{ textAlign: "left", padding: "28px 0 24px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}><h1 style={{ fontFamily: "var(--fd)", fontSize: 24, fontWeight: 600, color: "var(--ink)" }}>Daily Digest</h1><span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 99, background: "rgba(22,163,74,0.1)", color: "var(--green)" }}>● Active</span></div>
                    <p style={{ fontSize: 14, color: "var(--ink3)" }}>Managing your digest preferences. Changes apply from the next send.</p>
                  </div>
                  <div className="slbl">Active editions</div>
                  <div className="crd" style={{ marginBottom: 20, overflow: "hidden" }}>
                    {editions.morning && (
                      <div style={{ padding: "16px 20px", borderBottom: (editions.midday || editions.evening) ? "1px solid var(--border)" : "none", display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ fontSize: 20 }}>🌅</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>Morning Digest</div>
                          <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>
                            {frequency.charAt(0).toUpperCase() + frequency.slice(1)} · {deliveryTimes.morning} · {storyCount} stories · {Object.keys(channels).filter(c => channels[c as keyof typeof channels]).map(c => c === "app" ? "In-app" : c.charAt(0).toUpperCase() + c.slice(1)).join(" + ")}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          <button className="btno-onb btnsm" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => go("schedule")}>Edit</button>
                        </div>
                      </div>
                    )}
                    {editions.midday && (
                      <div style={{ padding: "16px 20px", borderBottom: editions.evening ? "1px solid var(--border)" : "none", display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ fontSize: 20 }}>☀️</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>Midday Briefing</div>
                          <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>
                            {frequency.charAt(0).toUpperCase() + frequency.slice(1)} · {deliveryTimes.midday} · {storyCount} stories · {Object.keys(channels).filter(c => channels[c as keyof typeof channels]).map(c => c === "app" ? "In-app" : c.charAt(0).toUpperCase() + c.slice(1)).join(" + ")}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          <button className="btno-onb btnsm" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => go("schedule")}>Edit</button>
                        </div>
                      </div>
                    )}
                    {editions.evening && (
                      <div style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ fontSize: 20 }}>🌆</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink)" }}>Evening Wrap-Up</div>
                          <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>
                            {frequency.charAt(0).toUpperCase() + frequency.slice(1)} · {deliveryTimes.evening} · {storyCount} stories · {Object.keys(channels).filter(c => channels[c as keyof typeof channels]).map(c => c === "app" ? "In-app" : c.charAt(0).toUpperCase() + c.slice(1)).join(" + ")}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                          <button className="btno-onb btnsm" style={{ fontSize: 12, padding: "4px 8px" }} onClick={() => go("schedule")}>Edit</button>
                        </div>
                      </div>
                    )}
                    {!editions.morning && !editions.midday && !editions.evening && (
                      <div style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 12, cursor: "pointer" }} onClick={() => go("schedule")}>
                        <span style={{ fontSize: 20, filter: "grayscale(1)", opacity: 0.5 }}>📰</span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink3)" }}>No active editions</div>
                          <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>Tap to set up editions</div>
                        </div>
                        <ArrowRight size={14} color="var(--ink3)" />
                      </div>
                    )}
                  </div>
                  <div className="slbl">Current settings</div>
                  <div className="crd" style={{ marginBottom: 20 }}>
                    <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}><div style={{ fontSize: 13, color: "var(--ink3)", minWidth: 90 }}>Topics</div><div style={{ flex: 1, display: "flex", flexWrap: "wrap", gap: 4 }}>{Array.from(selectedCats).map(c => (<span key={c} className="topic-tag">{CATEGORIES.find(cat => cat.id === c)?.icon} {CATEGORIES.find(cat => cat.id === c)?.name}</span>))}</div><button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", background: "none", border: "none" }} onClick={() => go("topics")}>Edit</button></div>
                    <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}><div style={{ fontSize: 13, color: "var(--ink3)", minWidth: 90 }}>Schedule</div><div style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{editions.morning && "Morning"} {editions.midday && "Midday"} {editions.evening && "Evening"} · {frequency.charAt(0).toUpperCase() + frequency.slice(1)}</div><button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", background: "none", border: "none" }} onClick={() => go("schedule")}>Edit</button></div>
                    <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}><div style={{ fontSize: 13, color: "var(--ink3)", minWidth: 90 }}>Length</div><div style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{storyCount} stories · ~{Math.ceil(storyCount * 0.6)} min read</div><button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", background: "none", border: "none" }} onClick={() => go("topics")}>Edit</button></div>
                    <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 10 }}><div style={{ fontSize: 13, color: "var(--ink3)", minWidth: 90 }}>Channels</div><div style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{Object.keys(channels).filter(c => channels[c as keyof typeof channels]).map(c => c === "app" ? "In-app" : c.charAt(0).toUpperCase() + c.slice(1)).join(" · ")}</div><button style={{ fontSize: 12, color: "var(--blue)", fontWeight: 500, cursor: "pointer", background: "none", border: "none" }} onClick={() => go("channels")}>Edit</button></div>
                    <div style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 10 }}><div style={{ fontSize: 13, color: "var(--ink3)", minWidth: 90 }}>Weekly</div><div style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{weeklyWrap ? "Weekly wrap-up · Sunday" : "Disabled"}</div><label className="toggle"><input type="checkbox" checked={weeklyWrap} onChange={(e) => {
                      setWeeklyWrap(e.target.checked);
                      toast.success(e.target.checked ? "Weekly wrap enabled" : "Weekly wrap disabled");
                    }} /><div className="tog-track"></div><div className="tog-thumb"></div></label></div>
                  </div>
                  <div className="slbl">Past digests</div>
                  <div className="crd" style={{ marginBottom: 28 }}>
                    {[
                      { d: "Monday, Jun 16 · Morning", t: "5 stories · Delivered 7:00 AM" },
                      { d: "Sunday, Jun 15 · Morning", t: "5 stories · Delivered 7:00 AM" },
                      { d: "Sunday, Jun 15 · Weekly Wrap-Up", t: "10 stories · Delivered 9:00 AM" },
                    ].map((item, idx) => (
                      <div key={idx} style={{ padding: "13px 20px", borderBottom: idx < 2 ? "1px solid var(--border)" : "none", display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}><div style={{ flex: 1 }}><div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{item.d}</div><div style={{ fontSize: 12, color: "var(--ink3)" }}>{item.t}</div></div><span style={{ fontSize: 11, fontWeight: 700, padding: "2px 7px", borderRadius: 99, background: "rgba(22,163,74,0.1)", color: "var(--green)" }}>Sent</span><ArrowRight size={13} color="var(--ink3)" /></div>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 10, paddingTop: 4 }}><button className="btno-onb" style={{ flex: 1 }} onClick={() => toast.info("Digest paused for 7 days")}>Pause for 7 days</button><button style={{ flex: 1, background: "transparent", color: "var(--err)", border: "1.5px solid rgba(220,38,38,0.2)", borderRadius: "var(--r6)", padding: 12, fontSize: 14, fontWeight: 600, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }} onClick={handleUnsubscribe}>Unsubscribe</button></div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <div className="sc hidden lg:block">
          <SidebarWidgets trendingStories={trendingStories} isLoading={isTrendingLoading} />
        </div>
      </div>
    </div>
  );
}
