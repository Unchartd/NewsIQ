import { BaseAnalyticsProvider } from "./base";
import { EventName, EventPayloadMap, CustomDimensions, UserTraits } from "../types";

declare global {
  interface Window {
    posthog?: any;
  }
}

export class PostHogProvider extends BaseAnalyticsProvider {
  name = "PostHog";

  initialize(): void {
    if (typeof window === "undefined") return;
    this.isInitialized = !!window.posthog;
    if (this.isInitialized) {
      this.debugLog("Loaded PostHog provider.");
    } else {
      this.debugLog("posthog not found on window. PostHog provider is standby.");
    }
  }

  identify(userId: string, traits?: UserTraits): void {
    if (!window.posthog || typeof window === "undefined") return;
    const cleanTraits = this.sanitizePayload(traits);
    window.posthog.identify(userId, cleanTraits);
    this.debugLog(`Identified user ${userId}`, cleanTraits);
  }

  setUserProperties(properties: Partial<CustomDimensions>): void {
    if (!window.posthog || typeof window === "undefined") return;
    const cleanProps = this.sanitizePayload(properties);
    window.posthog.register(cleanProps);
    this.debugLog("Set user properties (super properties)", cleanProps);
  }

  track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void {
    if (!window.posthog || typeof window === "undefined") return;
    const cleanParams = this.sanitizePayload(params);
    window.posthog.capture(eventName, cleanParams);
    this.debugLog(`Tracked event: ${eventName}`, cleanParams);
  }

  pageView(path: string, title: string): void {
    if (!window.posthog || typeof window === "undefined") return;
    window.posthog.capture("$pageview", {
      $current_url: window.location.href,
      $pathname: path,
      $title: title,
    });
    this.debugLog(`Tracked pageview: ${path} (${title})`);
  }

  reset(): void {
    if (!window.posthog || typeof window === "undefined") return;
    window.posthog.reset();
    this.debugLog("Reset user identity");
  }
}
