import { BaseAnalyticsProvider } from "./base";
import { EventName, EventPayloadMap, CustomDimensions, UserTraits } from "../types";

declare global {
  interface Window {
    posthog?: any;
  }
}

/**
 * A project token must look like a real one before we load anything.
 *
 * This provider previously assumed some other code had put `posthog` on
 * `window`. Nothing ever did — `posthog-js` was not even a dependency — so
 * every call in the app silently no-opped, while production carried the
 * placeholder token `phc_mock_token_newsiq`. Both failure modes are now
 * rejected here rather than producing a provider that looks live.
 */
function resolveToken(): string | null {
  const token = process.env.NEXT_PUBLIC_POSTHOG_TOKEN?.trim();
  if (!token) return null;
  if (!token.startsWith("phc_")) return null;
  if (/mock|placeholder|dummy|changeme|example/i.test(token)) return null;
  return token;
}

type QueuedCall = () => void;

export class PostHogProvider extends BaseAnalyticsProvider {
  name = "PostHog";

  private client: any = null;
  private loading = false;
  /**
   * Calls made between initialize() and the dynamic import resolving. Without
   * this they would be dropped — which is exactly the class of silent loss
   * this provider is being fixed for.
   */
  private pending: QueuedCall[] = [];

  initialize(): void {
    if (typeof window === "undefined" || this.loading || this.client) return;

    const token = resolveToken();
    if (!token) {
      console.warn(
        "[analytics] PostHog is disabled: NEXT_PUBLIC_POSTHOG_TOKEN is unset " +
          "or a placeholder. Set a real phc_… project token at build time."
      );
      return;
    }

    this.loading = true;
    // Dynamic import keeps posthog-js out of the initial bundle entirely when
    // the token is absent — the module is only fetched once we know it is
    // usable.
    import("posthog-js")
      .then(({ default: posthog }) => {
        posthog.init(token, {
          api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
          // The dispatcher decides when a pageview happens (it already tracks
          // SPA route changes); autocapture would double-count and would also
          // bypass the consent gate and PII scrubbing in BaseAnalyticsProvider.
          capture_pageview: false,
          capture_pageleave: true,
          autocapture: false,
          // Only reached when analytics consent is granted, but keep PostHog's
          // own opt-out plumbing consistent with that.
          persistence: "localStorage+cookie",
        });
        this.client = posthog;
        window.posthog = posthog;
        this.isInitialized = true;
        this.debugLog("Loaded PostHog provider.");

        const queued = this.pending;
        this.pending = [];
        queued.forEach((call) => {
          try {
            call();
          } catch (err) {
            console.error("[analytics] queued PostHog call failed:", err);
          }
        });
      })
      .catch((err) => {
        console.error("[analytics] Failed to load posthog-js:", err);
        this.pending = [];
      })
      .finally(() => {
        this.loading = false;
      });
  }

  /** Run now if the SDK is ready, otherwise queue until it is. */
  private withClient(call: (client: any) => void): void {
    if (typeof window === "undefined") return;
    if (this.client) {
      call(this.client);
      return;
    }
    if (this.loading) {
      this.pending.push(() => call(this.client));
    }
  }

  identify(userId: string, traits?: UserTraits): void {
    const cleanTraits = this.sanitizePayload(traits);
    this.withClient((client) => {
      client.identify(userId, cleanTraits);
      this.debugLog(`Identified user ${userId}`, cleanTraits);
    });
  }

  setUserProperties(properties: Partial<CustomDimensions>): void {
    const cleanProps = this.sanitizePayload(properties);
    this.withClient((client) => {
      client.register(cleanProps);
      this.debugLog("Set user properties (super properties)", cleanProps);
    });
  }

  track<T extends EventName>(eventName: T, params: EventPayloadMap[T] & CustomDimensions): void {
    const cleanParams = this.sanitizePayload(params);
    this.withClient((client) => {
      client.capture(eventName, cleanParams);
      this.debugLog(`Tracked event: ${eventName}`, cleanParams);
    });
  }

  pageView(path: string, title: string): void {
    this.withClient((client) => {
      client.capture("$pageview", {
        $current_url: window.location.href,
        $pathname: path,
        $title: title,
      });
      this.debugLog(`Tracked pageview: ${path} (${title})`);
    });
  }

  reset(): void {
    this.withClient((client) => {
      client.reset();
      this.debugLog("Reset user identity");
    });
  }
}
