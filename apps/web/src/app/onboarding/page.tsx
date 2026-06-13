"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

const CATEGORIES = [
  { slug: "politics", name: "Politics", icon: "🏛️" },
  { slug: "technology", name: "Technology", icon: "💻" },
  { slug: "business", name: "Business", icon: "📈" },
  { slug: "sports", name: "Sports", icon: "⚽" },
  { slug: "health", name: "Health", icon: "❤️" },
  { slug: "science", name: "Science", icon: "🔬" },
  { slug: "world", name: "World", icon: "🌍" },
  { slug: "weather", name: "Weather", icon: "🌦️" },
];

const COUNTRIES = [
  { code: "IN", name: "India", flag: "🇮🇳" },
  { code: "US", name: "United States", flag: "🇺🇸" },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧" },
  { code: "JP", name: "Japan", flag: "🇯🇵" },
  { code: "DE", name: "Germany", flag: "🇩🇪" },
  { code: "FR", name: "France", flag: "🇫🇷" },
  { code: "AU", name: "Australia", flag: "🇦🇺" },
  { code: "CA", name: "Canada", flag: "🇨🇦" },
];

const CITIES = [
  "Bengaluru",
  "Delhi",
  "Mumbai",
  "Chennai",
  "Hyderabad",
  "Pune",
  "London",
  "New York",
  "San Francisco",
  "Tokyo",
];

const SUMMARY_OPTIONS = [
  { value: "one_line", label: "One-line", desc: "~20 words — fastest scan" },
  { value: "short", label: "Short", desc: "~50 words — quick understanding" },
  { value: "detailed", label: "Detailed", desc: "~150 words — full picture" },
];

const slideVariants = {
  enter: (dir: number) => ({ x: dir > 0 ? 150 : -150, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({ x: dir > 0 ? -150 : 150, opacity: 0 }),
};

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  const [summaryType, setSummaryType] = useState("short");
  const [isLoading, setIsLoading] = useState(false);

  const totalSteps = 4;

  const toggleItem = (
    item: string,
    list: string[],
    setList: (v: string[]) => void
  ) => {
    setList(
      list.includes(item)
        ? list.filter((i) => i !== item)
        : [...list, item]
    );
  };

  const nextStep = () => {
    if (step === 0 && selectedCategories.length === 0) {
      toast.error("Please select at least one topic.");
      return;
    }
    setDirection(1);
    setStep((s) => Math.min(s + 1, totalSteps - 1));
  };

  const prevStep = () => {
    setDirection(-1);
    setStep((s) => Math.max(s - 1, 0));
  };

  const handleFinish = async () => {
    setIsLoading(true);
    try {
      await apiClient.post("/users/onboarding", {
        categories: selectedCategories,
        countries: selectedCountries,
        cities: selectedCities,
        preferred_summary_type: summaryType,
      });
      toast.success("Preferences saved successfully!");
      router.push("/home");
    } catch {
      toast.error("Unable to save preferences.");
    } finally {
      setIsLoading(false);
    }
  };

  const currentProgress = ((step + 1) / totalSteps) * 100;

  return (
    <div style={{ background: "var(--surface)", minHeight: "100vh" }}>
      {/* Mini Onboarding Navbar */}
      <nav
        className="nav"
        style={{
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        <div className="logo">
          <b>News</b>
          <i>IQ</i>
        </div>
      </nav>

      {/* Dynamic progress bar below navbar */}
      <div
        className="sig"
        style={{
          position: "sticky",
          top: "var(--nav)",
          zIndex: 100,
        }}
      >
        <div
          style={{
            height: "100%",
            background: "var(--primary)",
            width: `${currentProgress}%`,
            transition: "width 0.3s ease-in-out",
          }}
        />
      </div>

      <div className="ob-wrap">
        <div className="ob-card">
          {/* Segmented step indicators */}
          <div className="ob-sbar">
            {Array.from({ length: totalSteps }).map((_, i) => {
              let segClass = "";
              if (i < step) segClass = "done";
              else if (i === step) segClass = "act";
              return <div key={i} className={`ob-seg ${segClass}`} />;
            })}
          </div>

          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              custom={direction}
              variants={slideVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.2, ease: "easeInOut" }}
            >
              {/* Step 1: Categories */}
              {step === 0 && (
                <div>
                  <h1 className="ob-title">What do you follow?</h1>
                  <p className="ob-sub">
                    Pick at least one topic. Your feed is built around these.
                  </p>
                  <div className="catgrid">
                    {CATEGORIES.map((cat) => {
                      const isSelected = selectedCategories.includes(cat.slug);
                      return (
                        <div
                          key={cat.slug}
                          className={`catopt ${isSelected ? "sel" : ""}`}
                          onClick={() =>
                            toggleItem(
                              cat.slug,
                              selectedCategories,
                              setSelectedCategories
                            )
                          }
                        >
                          <div className="chk">
                            <svg width="10" height="10" style={{ color: "#fff" }} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="3">
                              <path d="M4 10l5 5 7-7" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </div>
                          <div className="ci">{cat.icon}</div>
                          <div className="cn">{cat.name}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 2: Countries */}
              {step === 1 && (
                <div>
                  <h1 className="ob-title">Which countries do you follow?</h1>
                  <p className="ob-sub">
                    Optional — skip or leave blank for a global layout feed.
                  </p>
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 8,
                      marginBottom: 28,
                    }}
                  >
                    {COUNTRIES.map((country) => {
                      const isSelected = selectedCountries.includes(country.code);
                      return (
                        <div
                          key={country.code}
                          className={`catopt ${isSelected ? "sel" : ""}`}
                          style={{
                            flexDirection: "row",
                            padding: "10px 14px",
                            justifyContent: "flex-start",
                            gap: 12,
                          }}
                          onClick={() =>
                            toggleItem(
                              country.code,
                              selectedCountries,
                              setSelectedCountries
                            )
                          }
                        >
                          <div className="chk">
                            <svg width="10" height="10" style={{ color: "#fff" }} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="3">
                              <path d="M4 10l5 5 7-7" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </div>
                          <div style={{ fontSize: 20 }}>{country.flag}</div>
                          <div className="cn">{country.name}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 3: Cities */}
              {step === 2 && (
                <div>
                  <h1 className="ob-title">Any specific cities?</h1>
                  <p className="ob-sub">
                    Optional — select cities to inject local updates.
                  </p>
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: 8,
                      marginBottom: 28,
                    }}
                  >
                    {CITIES.map((city) => {
                      const isSelected = selectedCities.includes(city);
                      return (
                        <button
                          key={city}
                          type="button"
                          className={`fchp ${isSelected ? "on" : ""}`}
                          style={{ padding: "6px 14px", fontSize: 13 }}
                          onClick={() =>
                            toggleItem(city, selectedCities, setSelectedCities)
                          }
                        >
                          {city}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 4: Summary Type */}
              {step === 3 && (
                <div>
                  <h1 className="ob-title">How detailed should summaries be?</h1>
                  <p className="ob-sub">
                    Select your default depth. You can toggle this on any story.
                  </p>
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 10,
                      marginBottom: 28,
                    }}
                  >
                    {SUMMARY_OPTIONS.map((opt) => {
                      const isSelected = summaryType === opt.value;
                      return (
                        <div
                          key={opt.value}
                          className={`catopt ${isSelected ? "sel" : ""}`}
                          style={{
                            alignItems: "flex-start",
                            textAlign: "left",
                            padding: "16px",
                          }}
                          onClick={() => setSummaryType(opt.value)}
                        >
                          <div className="chk">
                            <svg width="10" height="10" style={{ color: "#fff" }} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="3">
                              <path d="M4 10l5 5 7-7" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          </div>
                          <div className="cn" style={{ fontSize: 15 }}>
                            {opt.label}
                          </div>
                          <div style={{ fontSize: 12, color: "var(--ink3)", marginTop: 2 }}>
                            {opt.desc}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Navigation Buttons */}
          <div className="ob-btns">
            {step > 0 ? (
              <button
                type="button"
                className="btno"
                style={{ padding: "6px 12px", fontSize: 13 }}
                onClick={prevStep}
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            ) : (
              <button
                type="button"
                className="btng"
                onClick={() => router.push("/home")}
              >
                Skip Onboarding
              </button>
            )}

            {step < totalSteps - 1 ? (
              <button
                type="button"
                className="btnp"
                onClick={nextStep}
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                className="btnp"
                disabled={isLoading}
                onClick={handleFinish}
              >
                {isLoading ? "Saving..." : "Finish Setup"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
