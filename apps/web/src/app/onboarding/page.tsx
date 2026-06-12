"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Check, ArrowLeft, ArrowRight } from "lucide-react";
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
        style={{
          height: "var(--navbar-h)",
          background: "var(--card)",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          padding: "0 24px",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <span
            style={{
              fontFamily: "var(--font-inter)",
              fontWeight: 700,
              fontSize: 16,
              letterSpacing: "-0.02em",
              color: "var(--ink)",
            }}
          >
            News
          </span>
          <span
            style={{
              fontFamily: "var(--font-newsreader)",
              fontStyle: "italic",
              fontWeight: 700,
              fontSize: 18,
              color: "var(--primary)",
              marginLeft: 1,
            }}
          >
            IQ
          </span>
        </div>
      </nav>

      {/* Dynamic progress bar below navbar */}
      <div
        style={{
          height: "var(--signal-h)",
          background: "var(--border)",
          width: "100%",
          position: "sticky",
          top: "var(--navbar-h)",
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

      <div className="niq-onboard-wrap">
        <div className="niq-onboard-card">
          {/* Custom segmented step indicators */}
          <div className="niq-onboard-step-bar">
            {Array.from({ length: totalSteps }).map((_, i) => {
              let segClass = "";
              if (i < step) segClass = "done";
              else if (i === step) segClass = "active";
              return <div key={i} className={`niq-step-seg ${segClass}`} />;
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
                  <h1 className="niq-onboard-title">What do you follow?</h1>
                  <p className="niq-onboard-sub">
                    Pick at least one topic. Your feed is built around these.
                  </p>
                  <div className="niq-cat-grid">
                    {CATEGORIES.map((cat) => {
                      const isSelected = selectedCategories.includes(cat.slug);
                      return (
                        <div
                          key={cat.slug}
                          className={`niq-cat-option ${isSelected ? "selected" : ""}`}
                          onClick={() =>
                            toggleItem(
                              cat.slug,
                              selectedCategories,
                              setSelectedCategories
                            )
                          }
                        >
                          {isSelected && (
                            <div
                              style={{
                                position: "absolute",
                                top: 6,
                                right: 6,
                                width: 16,
                                height: 16,
                                backgroundColor: "var(--primary)",
                                borderRadius: "50%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                              <Check className="w-2.5 h-2.5 text-white" />
                            </div>
                          )}
                          <div className="niq-cat-icon">{cat.icon}</div>
                          <div className="niq-cat-name">{cat.name}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 2: Countries */}
              {step === 1 && (
                <div>
                  <h1 className="niq-onboard-title">Which countries do you follow?</h1>
                  <p className="niq-onboard-sub">
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
                          className={`niq-cat-option ${isSelected ? "selected" : ""}`}
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
                          {isSelected && (
                            <div
                              style={{
                                position: "absolute",
                                top: 6,
                                right: 6,
                                width: 16,
                                height: 16,
                                backgroundColor: "var(--primary)",
                                borderRadius: "50%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                              <Check className="w-2.5 h-2.5 text-white" />
                            </div>
                          )}
                          <div style={{ fontSize: 20 }}>{country.flag}</div>
                          <div className="niq-cat-name">{country.name}</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 3: Cities */}
              {step === 2 && (
                <div>
                  <h1 className="niq-onboard-title">Any specific cities?</h1>
                  <p className="niq-onboard-sub">
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
                          className={`niq-filter-chip ${isSelected ? "active" : ""}`}
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
                  <h1 className="niq-onboard-title">How detailed should summaries be?</h1>
                  <p className="niq-onboard-sub">
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
                          className={`niq-cat-option ${isSelected ? "selected" : ""}`}
                          style={{
                            alignItems: "flex-start",
                            textAlign: "left",
                            padding: "16px",
                          }}
                          onClick={() => setSummaryType(opt.value)}
                        >
                          {isSelected && (
                            <div
                              style={{
                                position: "absolute",
                                top: 16,
                                right: 16,
                                width: 16,
                                height: 16,
                                backgroundColor: "var(--primary)",
                                borderRadius: "50%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                              }}
                            >
                              <Check className="w-2.5 h-2.5 text-white" />
                            </div>
                          )}
                          <div className="niq-cat-name" style={{ fontSize: 15 }}>
                            {opt.label}
                          </div>
                          <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>
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
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginTop: 24,
            }}
          >
            {step > 0 ? (
              <button
                type="button"
                className="niq-btn-outline"
                style={{ padding: "6px 12px", fontSize: 13 }}
                onClick={prevStep}
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            ) : (
              <button
                type="button"
                className="niq-btn-outline"
                style={{
                  border: "none",
                  padding: "6px 0",
                  color: "var(--ink-3)",
                }}
                onClick={() => router.push("/home")}
              >
                Skip Onboarding
              </button>
            )}

            {step < totalSteps - 1 ? (
              <button
                type="button"
                className="niq-btn-primary"
                onClick={nextStep}
              >
                Continue
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                className="niq-btn-primary"
                disabled={isLoading}
                onClick={handleFinish}
              >
                {isLoading ? "Saving..." : "Finish Setup"}
                <Check className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
