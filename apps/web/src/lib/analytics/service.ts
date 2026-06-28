import { AnalyticsDispatcher } from "./dispatcher";
import { EventName, EventPayloadMap, CustomDimensions, UserTraits } from "./types";

class AnalyticsService {
  private dispatcher = new AnalyticsDispatcher();
  private isInitialized = false;

  initialize(): void {
    if (typeof window === "undefined" || this.isInitialized) return;
    this.dispatcher.initializeProviders();
    this.isInitialized = true;
    
    if (
      process.env.NODE_ENV === "development" ||
      process.env.NEXT_PUBLIC_ANALYTICS_DEBUG === "true"
    ) {
      console.log(
        "%c[AnalyticsService] Core Framework Initialized Successfully.",
        "color: #10B981; font-weight: bold; font-size: 11px;"
      );
    }
  }

  identify(userId: string, traits?: UserTraits): void {
    if (typeof window === "undefined") return;
    this.ensureInitialized();
    this.dispatcher.identify(userId, traits);
  }

  setUserProperties(properties: Partial<CustomDimensions>): void {
    if (typeof window === "undefined") return;
    this.ensureInitialized();
    this.dispatcher.setUserProperties(properties);
  }

  track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void {
    if (typeof window === "undefined") return;
    this.ensureInitialized();
    
    // Add default session parameters if available
    const enrichedParams = {
      ...params,
      url: window.location.href,
      path: window.location.pathname,
      referrer: document.referrer,
      timestamp: new Date().toISOString(),
    };
    
    this.dispatcher.track(eventName, enrichedParams);
  }

  pageView(path: string, title: string): void {
    if (typeof window === "undefined") return;
    this.ensureInitialized();
    this.dispatcher.pageView(path, title);
  }

  reset(): void {
    if (typeof window === "undefined") return;
    this.ensureInitialized();
    this.dispatcher.reset();
  }

  private ensureInitialized(): void {
    if (!this.isInitialized) {
      this.initialize();
    }
  }
}

export const analytics = new AnalyticsService();
