"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import apiClient from "@/lib/api-client";
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

  // 3. Dynamic Script Injection when consent changes
  useEffect(() => {
    if (loading) return;

    if (state.analytics) {
      initializeAnalytics();
    }
    if (state.marketing) {
      initializeMarketing();
    }
  }, [state.analytics, state.marketing, loading]);

  const initializeAnalytics = () => {
    if (typeof window === "undefined") return;
    
    // Check if scripts are already loaded
    if (document.getElementById("gtag-script")) {
      logConsent("Analytics", "Google Analytics & PostHog already initialized.");
      return;
    }

    logConsent("Analytics", "Initializing Google Analytics (G-NEWS-IQ) & PostHog Client.");

    // Inject Google Analytics
    const gtagScript = document.createElement("script");
    gtagScript.src = "https://www.googletagmanager.com/gtag/js?id=G-NEWSIQ";
    gtagScript.id = "gtag-script";
    gtagScript.async = true;
    document.head.appendChild(gtagScript);

    const inlineScript = document.createElement("script");
    inlineScript.id = "gtag-inline-script";
    inlineScript.innerHTML = `
      window.dataLayer = window.dataLayer || [];
      function gtag(){dataLayer.push(arguments);}
      gtag('js', new Date());
      gtag('config', 'G-NEWSIQ', { 'anonymize_ip': true });
    `;
    document.head.appendChild(inlineScript);

    // Inject PostHog (Mock/Console Loader in dev, real script setup)
    const phScript = document.createElement("script");
    phScript.id = "posthog-script";
    phScript.innerHTML = `
      !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="capture identify alias people.set people.set_once set_config register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset get_distinct_id".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
      posthog.init('phc_mock_token_newsiq', {api_host:'https://app.posthog.com'});
    `;
    document.head.appendChild(phScript);
  };

  const initializeMarketing = () => {
    if (typeof window === "undefined") return;

    if (document.getElementById("meta-pixel-script")) {
      logConsent("Marketing", "Meta Pixel & LinkedIn Insight already initialized.");
      return;
    }

    logConsent("Marketing", "Initializing Meta Pixel & LinkedIn Insight Tag.");

    // Inject Meta Pixel
    const fbScript = document.createElement("script");
    fbScript.id = "meta-pixel-script";
    fbScript.innerHTML = `
      !function(f,b,e,v,n,t,s)
      {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
      n.callMethod.apply(n,arguments):n.queue.push(arguments)};
      if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
      n.queue=[];t=b.createElement(e);t.async=!0;
      t.src=v;s=b.getElementsByTagName(e)[0];
      s.parentNode.insertBefore(t,s)}(window, document,'script',
      'https://connect.facebook.net/en_US/fbevents.js');
      fbq('init', '1234567890');
      fbq('track', 'PageView');
    `;
    document.head.appendChild(fbScript);

    // Inject LinkedIn Insight
    const liScript = document.createElement("script");
    liScript.id = "linkedin-insight-script";
    liScript.innerHTML = `
      _linkedin_data_partner_id = "mock_li_partner_id";
      window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
      window._linkedin_data_partner_ids.push(_linkedin_data_partner_id);
      (function(l) {
      if (!l){window.lintrk = function(a,b){window.lintrk.q.push([a,b])};
      window.lintrk.q=[]}
      var s = document.getElementsByTagName("script")[0];
      var b = document.createElement("script");
      b.type = "text/javascript";b.async = true;
      b.src = "https://snap.licdn.com/li.lms-analytics/insight.min.js";
      s.parentNode.insertBefore(b, s);})(window.lintrk);
    `;
    document.head.appendChild(liScript);
  };

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
