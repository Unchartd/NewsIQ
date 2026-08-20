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
    
    // layout.tsx loads gtag.js and issues consent defaults + config. It
    // renders nothing at all when no measurement id was supplied at build
    // time, so an absent window.gtag means GA4 is deliberately disabled.
    this.isInitialized = !!window.gtag;
    if (this.isInitialized) {
      this.debugLog("Loaded GA4 provider.");
    } else {
      console.warn(
        "[analytics] GA4 is disabled: no gtag on window. " +
          "Set NEXT_PUBLIC_GA_MEASUREMENT_ID at build time to enable it."
      );
    }
  }

  identify(userId: string, traits?: UserTraits): void {
    if (!window.gtag || typeof window === "undefined") return;
    const cleanTraits = this.sanitizePayload(traits);

    // `set` rather than a second `config`: the tag is configured once at page
    // load now, and re-issuing config re-initialises the tag and can restart
    // the session. This only needs to attach identity to the existing one.
    window.gtag("set", {
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

    // Clear identity without reconfiguring the tag (see identify above).
    window.gtag("set", { user_id: null, user_tier: null, subscription_status: null });
    this.debugLog("Reset user identity");
  }
}
