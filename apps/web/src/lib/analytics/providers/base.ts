import { AnalyticsProvider, EventName, EventPayloadMap, CustomDimensions, UserTraits } from "../types";

export abstract class BaseAnalyticsProvider implements AnalyticsProvider {
  abstract name: string;
  protected isInitialized = false;

  abstract initialize(): void;
  abstract identify(userId: string, traits?: UserTraits): void;
  abstract setUserProperties(properties: Partial<CustomDimensions>): void;
  abstract track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void;
  abstract pageView(path: string, title: string): void;
  abstract reset(): void;

  protected debugLog(message: string, ...optionalParams: any[]): void {
    if (
      process.env.NODE_ENV === "development" ||
      process.env.NEXT_PUBLIC_ANALYTICS_DEBUG === "true"
    ) {
      console.log(
        `%c[Analytics:${this.name}] ${message}`,
        "color: #10B981; font-weight: bold;",
        ...optionalParams
      );
    }
  }

  protected sanitizePayload<T>(params: T): T {
    if (!params || typeof params !== "object") return params;
    const clean = { ...params } as any;
    
    // Explicitly search and scrub PII patterns
    const piiKeys = ["email", "name", "password", "phone", "token", "jwt", "authorization", "secret"];
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;

    for (const key in clean) {
      if (Object.prototype.hasOwnProperty.call(clean, key)) {
        const val = clean[key];

        // Scrub keys that match PII names
        if (piiKeys.some((piiKey) => key.toLowerCase().includes(piiKey))) {
          clean[key] = "[REDACTED_PII]";
        } else if (typeof val === "string") {
          // Scrub email patterns inside strings
          if (emailRegex.test(val)) {
            clean[key] = val.replace(emailRegex, "[REDACTED_EMAIL]");
          }
        }
      }
    }
    return clean;
  }
}
