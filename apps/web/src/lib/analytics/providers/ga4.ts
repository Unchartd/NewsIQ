import { BaseAnalyticsProvider } from "./base";
import { EventName, EventPayloadMap, CustomDimensions, UserTraits } from "../types";

declare global {
  interface Window {
    gtag?: (...args: any[]) => void;
    dataLayer?: any[];
  }
}

export class GA4Provider extends BaseAnalyticsProvider {
  name = "GA4";

  initialize(): void {
    if (typeof window === "undefined") return;
    
    // Gtag is pre-loaded inside layout.tsx for Consent Mode v2 setup
    this.isInitialized = !!window.gtag;
    if (this.isInitialized) {
      this.debugLog("Loaded GA4 provider.");
    } else {
      this.debugLog("gtag not found on window. GA4 provider is standby.");
    }
  }

  identify(userId: string, traits?: UserTraits): void {
    if (!window.gtag || typeof window === "undefined") return;
    const cleanTraits = this.sanitizePayload(traits);
    
    const measurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-NEWSIQ";
    window.gtag("config", measurementId, {
      user_id: userId,
      user_tier: cleanTraits?.user_tier,
      subscription_status: cleanTraits?.subscription_status,
    });
    this.debugLog(`Identified user ${userId}`, cleanTraits);
  }

  setUserProperties(properties: Partial<CustomDimensions>): void {
    if (!window.gtag || typeof window === "undefined") return;
    const cleanProps = this.sanitizePayload(properties);
    
    window.gtag("set", "user_properties", cleanProps);
    this.debugLog("Set user properties", cleanProps);
  }

  track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void {
    if (!window.gtag || typeof window === "undefined") return;
    const cleanParams = this.sanitizePayload(params);
    
    window.gtag("event", eventName, cleanParams);
    this.debugLog(`Tracked event: ${eventName}`, cleanParams);
  }

  pageView(path: string, title: string): void {
    if (!window.gtag || typeof window === "undefined") return;
    
    // Track page view event in GA4
    window.gtag("event", "page_view", {
      page_path: path,
      page_title: title,
      // Pass landing page details
      location: window.location.href,
      referrer: document.referrer,
    });
    this.debugLog(`Tracked page_view: ${path} (${title})`);
  }

  reset(): void {
    if (!window.gtag || typeof window === "undefined") return;
    const measurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-NEWSIQ";
    
    window.gtag("config", measurementId, {
      user_id: "",
    });
    this.debugLog("Reset user identity");
  }
}
