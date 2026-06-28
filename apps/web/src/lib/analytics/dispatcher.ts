import { AnalyticsProvider, EventName, EventPayloadMap, CustomDimensions, UserTraits } from "./types";
import { GA4Provider } from "./providers/ga4";
import { PostHogProvider } from "./providers/posthog";

export interface ConsentPreferences {
  essential: boolean;
  functional: boolean;
  analytics: boolean;
  marketing: boolean;
}

export class AnalyticsDispatcher {
  private providers: AnalyticsProvider[] = [];

  constructor() {
    this.registerProvider(new GA4Provider());
    this.registerProvider(new PostHogProvider());
  }

  private registerProvider(provider: AnalyticsProvider): void {
    this.providers.push(provider);
  }

  initializeProviders(): void {
    this.providers.forEach((provider) => {
      try {
        provider.initialize();
      } catch (err) {
        console.error(`Failed to initialize analytics provider ${provider.name}:`, err);
      }
    });
  }

  private getConsent(): ConsentPreferences {
    if (typeof window === "undefined") {
      return { essential: true, functional: false, analytics: false, marketing: false };
    }
    try {
      const stored = localStorage.getItem("niq_consent_preferences");
      if (stored) {
        return JSON.parse(stored);
      }
    } catch {}
    
    // Fail-safe fallback default
    return { essential: true, functional: false, analytics: false, marketing: false };
  }

  identify(userId: string, traits?: UserTraits): void {
    const consent = this.getConsent();
    this.providers.forEach((provider) => {
      try {
        // Only run identify if analytics consent is granted
        if (consent.analytics) {
          provider.identify(userId, traits);
        }
      } catch (err) {
        console.error(`Failed to identify user on provider ${provider.name}:`, err);
      }
    });
  }

  setUserProperties(properties: Partial<CustomDimensions>): void {
    const consent = this.getConsent();
    this.providers.forEach((provider) => {
      try {
        if (consent.analytics) {
          provider.setUserProperties(properties);
        }
      } catch (err) {
        console.error(`Failed to set user properties on provider ${provider.name}:`, err);
      }
    });
  }

  track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void {
    const consent = this.getConsent();
    
    this.providers.forEach((provider) => {
      try {
        // Google Analytics 4 tracks events even in cookieless Advanced Consent Mode v2,
        // so we always dispatch to GA4 and let Google handle filtering.
        // For PostHog and other third parties, we strictly block dispatching if analytics consent is denied.
        if (provider.name === "GA4") {
          provider.track(eventName, params);
        } else if (consent.analytics) {
          provider.track(eventName, params);
        }
      } catch (err) {
        console.error(`Failed to track event ${eventName} on provider ${provider.name}:`, err);
      }
    });
  }

  pageView(path: string, title: string): void {
    const consent = this.getConsent();
    this.providers.forEach((provider) => {
      try {
        if (provider.name === "GA4") {
          provider.pageView(path, title);
        } else if (consent.analytics) {
          provider.pageView(path, title);
        }
      } catch (err) {
        console.error(`Failed to track pageview on provider ${provider.name}:`, err);
      }
    });
  }

  reset(): void {
    this.providers.forEach((provider) => {
      try {
        provider.reset();
      } catch (err) {
        console.error(`Failed to reset provider ${provider.name}:`, err);
      }
    });
  }
}
