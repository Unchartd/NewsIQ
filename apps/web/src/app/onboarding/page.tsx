"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Landmark,
  Cpu,
  Briefcase,
  Trophy,
  HeartPulse,
  FlaskConical,
  Clapperboard,
  CloudSun,
  Globe,
  ArrowRight,
  ArrowLeft,
  Check,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";

const CATEGORIES = [
  { slug: "politics", name: "Politics", icon: Landmark },
  { slug: "technology", name: "Technology", icon: Cpu },
  { slug: "business", name: "Business", icon: Briefcase },
  { slug: "sports", name: "Sports", icon: Trophy },
  { slug: "health", name: "Health", icon: HeartPulse },
  { slug: "science", name: "Science", icon: FlaskConical },
  { slug: "entertainment", name: "Entertainment", icon: Clapperboard },
  { slug: "weather", name: "Weather", icon: CloudSun },
  { slug: "world", name: "World", icon: Globe },
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
  enter: (dir: number) => ({ x: dir > 0 ? 300 : -300, opacity: 0 }),
  center: { x: 0, opacity: 1 },
  exit: (dir: number) => ({ x: dir > 0 ? -300 : 300, opacity: 0 }),
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
      toast.error("Please select at least one category.");
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
      toast.success("You're all set!");
      router.push("/home");
    } catch {
      toast.error("Unable to save preferences.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <Zap className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="text-2xl font-bold tracking-tight">NewsIQ</span>
          </div>
          <h1 className="text-2xl font-bold">Personalize your feed</h1>
          <p className="text-muted-foreground mt-1">
            Step {step + 1} of {totalSteps}
          </p>
        </div>

        {/* Progress bar */}
        <div className="flex gap-2 mb-8">
          {Array.from({ length: totalSteps }).map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${
                i <= step ? "bg-primary" : "bg-muted"
              }`}
            />
          ))}
        </div>

        {/* Steps */}
        <Card className="border-border/50 shadow-lg overflow-hidden">
          <CardContent className="p-6 min-h-[320px]">
            <AnimatePresence mode="wait" custom={direction}>
              <motion.div
                key={step}
                custom={direction}
                variants={slideVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.25, ease: "easeInOut" }}
              >
                {/* Step 1: Categories */}
                {step === 0 && (
                  <div>
                    <h2 className="text-lg font-semibold mb-4">
                      What topics interest you?
                    </h2>
                    <div className="grid grid-cols-3 gap-3">
                      {CATEGORIES.map((cat) => {
                        const selected = selectedCategories.includes(cat.slug);
                        const Icon = cat.icon;
                        return (
                          <button
                            key={cat.slug}
                            onClick={() =>
                              toggleItem(
                                cat.slug,
                                selectedCategories,
                                setSelectedCategories
                              )
                            }
                            className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 hover:scale-[1.02] ${
                              selected
                                ? "border-primary bg-primary/5 text-primary"
                                : "border-border hover:border-primary/50"
                            }`}
                          >
                            <Icon className="w-6 h-6" />
                            <span className="text-sm font-medium">
                              {cat.name}
                            </span>
                            {selected && (
                              <Check className="w-4 h-4 text-primary" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Step 2: Countries */}
                {step === 1 && (
                  <div>
                    <h2 className="text-lg font-semibold mb-1">
                      Which countries do you follow?
                    </h2>
                    <p className="text-sm text-muted-foreground mb-4">
                      Optional — skip to get global news.
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      {COUNTRIES.map((country) => {
                        const selected = selectedCountries.includes(
                          country.code
                        );
                        return (
                          <button
                            key={country.code}
                            onClick={() =>
                              toggleItem(
                                country.code,
                                selectedCountries,
                                setSelectedCountries
                              )
                            }
                            className={`flex items-center gap-3 p-3 rounded-xl border-2 transition-all duration-200 ${
                              selected
                                ? "border-primary bg-primary/5"
                                : "border-border hover:border-primary/50"
                            }`}
                          >
                            <span className="text-2xl">{country.flag}</span>
                            <span className="text-sm font-medium">
                              {country.name}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Step 3: Cities */}
                {step === 2 && (
                  <div>
                    <h2 className="text-lg font-semibold mb-1">
                      Any specific cities?
                    </h2>
                    <p className="text-sm text-muted-foreground mb-4">
                      Optional — for local news.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {CITIES.map((city) => {
                        const selected = selectedCities.includes(city);
                        return (
                          <Badge
                            key={city}
                            variant={selected ? "default" : "outline"}
                            className={`cursor-pointer text-sm px-4 py-2 transition-all duration-200 hover:scale-105 ${
                              selected ? "" : "hover:bg-primary/10"
                            }`}
                            onClick={() =>
                              toggleItem(
                                city,
                                selectedCities,
                                setSelectedCities
                              )
                            }
                          >
                            {city}
                          </Badge>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Step 4: Summary preference */}
                {step === 3 && (
                  <div>
                    <h2 className="text-lg font-semibold mb-4">
                      How detailed should summaries be?
                    </h2>
                    <div className="space-y-3">
                      {SUMMARY_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => setSummaryType(opt.value)}
                          className={`w-full flex items-center justify-between p-4 rounded-xl border-2 transition-all duration-200 ${
                            summaryType === opt.value
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50"
                          }`}
                        >
                          <div className="text-left">
                            <p className="font-medium">{opt.label}</p>
                            <p className="text-sm text-muted-foreground">
                              {opt.desc}
                            </p>
                          </div>
                          {summaryType === opt.value && (
                            <Check className="w-5 h-5 text-primary flex-shrink-0" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            </AnimatePresence>
          </CardContent>
        </Card>

        {/* Navigation */}
        <div className="flex justify-between mt-6">
          <Button
            variant="ghost"
            onClick={prevStep}
            disabled={step === 0}
            className="gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Button>

          {step < totalSteps - 1 ? (
            <Button onClick={nextStep} className="gap-2">
              Continue
              <ArrowRight className="w-4 h-4" />
            </Button>
          ) : (
            <Button
              onClick={handleFinish}
              disabled={isLoading}
              className="gap-2"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  Finish
                  <Check className="w-4 h-4" />
                </>
              )}
            </Button>
          )}
        </div>

        {/* Skip */}
        <div className="text-center mt-4">
          <button
            onClick={() => router.push("/home")}
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Skip for now
          </button>
        </div>
      </div>
    </div>
  );
}
