# NewsIQ Analytics Architecture

This document describes the unified, provider-agnostic analytics architecture designed for NewsIQ.

## System Overview

To avoid coupling the frontend application code to specific analytics providers (such as Google Analytics or PostHog), the platform implements a decoupled, event-driven analytics architecture.

```
[UI Components / Hooks / Interceptors]
                 │
                 ▼ (Calls type-safe helper)
        [Analytics Service]  <--- Scrubbing & Enrichment (Removes PII, Adds default context)
                 │
                 ▼
     [Central Event Dispatcher]
                 │
        ┌────────┴────────┐
        ▼                 ▼
   [GA4 Provider]   [PostHog Provider]
   (Consent Mode v2) (Opt-in only)
```

## Core Components

1. **Analytics Service (`lib/analytics/service.ts`)**:
   Exposes the public API (`analytics.track`, `analytics.pageView`, etc.) used by components. Handles default property enrichment (e.g., path, URL, timestamp) and automatically triggers initialization.

2. **Central Event Dispatcher (`lib/analytics/dispatcher.ts`)**:
   Coordinates delivery of events to all registered providers. Integrates directly with `localStorage` cached consent preferences to enforce GDPR/CCPA privacy rules.

3. **Providers (`lib/analytics/providers/`)**:
   Wrappers that map unified events to provider-specific syntax (such as GA4's `gtag` or PostHog's `capture`).
   - **Base Provider (`base.ts`)**: Contains shared debugging loggers and a strict validation/PII-scrubbing filter.
   - **GA4 Provider (`ga4.ts`)**: Maps properties to Custom Dimensions and handles Consent Mode v2 states.
   - **PostHog Provider (`posthog.ts`)**: Standard product clickstream telemetry provider.

## Privacy & Consent Filtering

- **Essential (Strictly Necessary)**: Core authentication cookies. No tracking is allowed here.
- **Performance & Analytics**: Controls whether provider scripts can track user identities or write cookies.
- **Marketing & Targeting**: Controls whether tracking pixels (e.g., Meta Pixel) can be enabled.

The dispatching system behaves differently depending on the provider and active consent:
- **GA4**: Dispatched always. Google Consent Mode v2 receives the user's consent flags. If analytics or marketing is `denied`, GA4 uses cookieless signals, sending anonymized hits for data modeling.
- **PostHog / Other Third Parties**: Blocked completely unless explicit `analytics` consent is resolved to `true`.
