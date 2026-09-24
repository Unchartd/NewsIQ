"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
import { analytics } from "@/lib/analytics/service";
import { useAuthStore } from "@/stores/auth-store";

// Global Consent Version to force re-consent upon policy updates
export const CONSENT_VERSION = "2026-06-v1";

export interface ConsentState {
  essential: boolean;
  functional: boolean;
  analytics: boolean;
  marketing: boolean;
}

interface ConsentContextType {
  essentialEnabled: boolean;
  functionalEnabled: boolean;
  analyticsEnabled: boolean;
  marketingEnabled: boolean;
  region: string;
  consentVersion: string;
  loading: boolean;
  showBanner: boolean;
  setShowBanner: (show: boolean) => void;
  updateConsent: (newPrefs: Partial<ConsentState>) => Promise<void>;
  withdrawConsent: () => Promise<void>;
}

const ConsentContext = createContext<ConsentContextType | undefined>(undefined);

// Helper to generate UUID v4
function generateUUID() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0,
      v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Custom Logging for Consent Guard
function logConsent(service: string, message: string) {
  console.log(`%c[CMP Guard] ${service}: ${message}`, "color: #3b82f6; font-weight: bold;");
}

export function ConsentProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const [region, setRegion] = useState<string>("ROW");
  const [consentVersion, setConsentVersion] = useState<string>(CONSENT_VERSION);
  const [loading, setLoading] = useState<boolean>(true);
  const [showBanner, setShowBanner] = useState<boolean>(false);
  const [anonymousId, setAnonymousId] = useState<string>("");

  const [state, setState] = useState<ConsentState>({
    essential: true,
    functional: false,
    analytics: false,
    marketing: false,
  });

  // 1. Initialize Anonymous ID
  useEffect(() => {
    if (typeof window !== "undefined") {
      let anonId = localStorage.getItem("niq_anonymous_id");
      if (!anonId) {
        anonId = generateUUID();
        localStorage.setItem("niq_anonymous_id", anonId);
      }
      setAnonymousId(anonId);
    }
  }, []);

  // 2. Fetch Region and User/Anonymous Preferences
  useEffect(() => {
    if (!anonymousId) return;

    async function initConsent() {
      try {
        // Detect client region defaults
        const regionRes = await apiClient.get(`/consent/region`);
        const { region: detectedRegion, defaults, require_explicit_opt_in } = regionRes.data;
        setRegion(detectedRegion);

        // Fetch saved preferences from database
        const prefRes = await apiClient.get(`/consent/preferences?anonymous_id=${anonymousId}`);
        if (prefRes.data) {
          const pref = prefRes.data;
          
          // Check if consent version matches active version
          if (pref.consent_version !== CONSENT_VERSION) {
            logConsent("Version", `Outdated consent version (${pref.consent_version}). Forcing re-consent banner.`);
            setShowBanner(true);
            
            // Set defaults based on region until re-consent
            setState({
              essential: true,
              functional: defaults.functional,
              analytics: defaults.analytics,
              marketing: defaults.marketing,
            });
          } else {
            setState({
              essential: true,
              functional: pref.functional,
              analytics: pref.analytics,
              marketing: pref.marketing,
            });
            setShowBanner(false);
          }
        } else {
          // No saved preferences, show banner
          logConsent("Registry", "No existing preferences found in database. Showing consent banner.");
          setShowBanner(true);
          
          // Apply region-specific defaults
          setState({
            essential: true,
            functional: defaults.functional,
            analytics: defaults.analytics,
            marketing: defaults.marketing,
          });
        }
      } catch (err) {
        console.error("Failed to initialize consent preferences:", err);
        // Fail-safe defaults
        setShowBanner(true);
      } finally {
        setLoading(false);
      }
    }

    initConsent();
  }, [anonymousId, isAuthenticated]);

  const syncConsentSettings = (prefs: ConsentState) => {
    if (typeof window === "undefined") return;

    localStorage.setItem("niq_consent_preferences", JSON.stringify(prefs));

    if (window.gtag) {
      logConsent("ConsentMode", "Syncing consent state with Google Tag Manager...");
      window.gtag("consent", "update", {
        analytics_storage: prefs.analytics ? "granted" : "denied",
        functionality_storage: prefs.functional ? "granted" : "denied",
        personalization_storage: prefs.functional ? "granted" : "denied",
        // No advertising use, so ad signals stay denied whatever was chosen.
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
      });
    }
  };

  // 3. Dynamic Script Injection and Consent Mode syncing
  useEffect(() => {
    if (loading) return;

    syncConsentSettings(state);

    if (state.analytics) {
      initializeAnalytics();
    }
  }, [state, loading]);

  const initializeAnalytics = () => {
    if (typeof window === "undefined") return;
    // The analytics service owns PostHog (real token, consent-gated, PII
    // scrubbing). This used to inject a second copy of PostHog with a
    // placeholder-token fallback, which could run alongside it.
    logConsent("Analytics", "Analytics consent granted; enabling analytics providers.");
    analytics.applyConsent();
  };

  // No marketing trackers. This used to inject a Meta Pixel with the
  // placeholder ID 1234567890 and a LinkedIn Insight tag whenever "marketing"
  // was accepted, while the Cookie Policy promised no advertising trackers.

  const updateConsent = async (newPrefs: Partial<ConsentState>) => {
    const updatedState = { ...state, ...newPrefs };
    setState(updatedState);
    setShowBanner(false);

    try {
      logConsent("Registry", "Saving consent preferences to backend database...");
      await apiClient.post("/consent/preferences", {
        anonymous_id: anonymousId,
        functional: updatedState.functional,
        analytics: updatedState.analytics,
        marketing: updatedState.marketing,
        region,
        consent_version: CONSENT_VERSION,
      });
      logConsent("Registry", "Consent preferences saved successfully.");
    } catch (err) {
      console.error("Failed to save consent preferences to database:", err);
    }
  };

  const withdrawConsent = async () => {
    setState({
      essential: true,
      functional: false,
      analytics: false,
      marketing: false,
    });
    setShowBanner(false);

    try {
      logConsent("Registry", "Withdrawing consent preferences...");
      await apiClient.post(`/consent/withdraw?anonymous_id=${anonymousId}`);
      
      // Reload browser page to completely clear in-memory analytics variables and clean state
      logConsent("Registry", "Withdrawal processed. Reloading window to scrub active tracking modules.");
      window.location.reload();
    } catch (err) {
      console.error("Failed to withdraw consent from database:", err);
    }
  };

  return (
    <ConsentContext.Provider
      value={{
        essentialEnabled: state.essential,
        functionalEnabled: state.functional,
        analyticsEnabled: state.analytics,
        marketingEnabled: state.marketing,
        region,
        consentVersion,
        loading,
        showBanner,
        setShowBanner,
        updateConsent,
        withdrawConsent,
      }}
    >
      {children}
    </ConsentContext.Provider>
  );
}

export function useConsent() {
  const context = useContext(ConsentContext);
  if (context === undefined) {
    throw new Error("useConsent must be used within a ConsentProvider");
  }
  return context;
}
