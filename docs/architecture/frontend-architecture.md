# Frontend Architecture Reference

This document describes the design patterns, page routing, state management, and consent integration within the NewsIQ Next.js web application.

---

## 1. Directory Structure

The frontend is located under `apps/web/` and built using Next.js, React, and TypeScript.

```text
apps/web/src/
├── app/                  # Next.js App Router Pages
│   ├── (legal)/          # Legal Policy Hub (/legal, /privacy, /tos)
│   ├── auth/             # Authentication Callbacks
│   ├── home/             # Main News Dashboard
│   ├── settings/         # User Profiles & Cookie Settings
│   └── layout.tsx        # Root HTML Layout wrapper
├── components/           # Reusable UI & Layout Components
│   ├── layout/           # Sidebar, SignalBar, Header
│   ├── legal/            # CMP Provider, Cookie Banner, Cookie Modal
│   └── ui/               # Primitive Buttons, Switches, Inputs
├── lib/                  # Clients and Utilities
│   ├── api-client.ts     # Axios wrapper with refresh-interceptors
│   └── token-store.ts    # In-memory access token storage
├── stores/               # Zustand Global State Stores
│   ├── auth-store.ts     # Logged-in User and loading states
│   └── ui-store.ts       # Themes, sidebar toggles, layouts
└── types/                # Global TypeScript Declarations
```

---

## 2. Page Routing & Navigation
NewsIQ uses **Next.js App Router** for page layouts:
- **Public Routes**: `/`, `/login`, `/signup`, `/legal`, `/tos`, `/privacy`.
- **Protected Routes**: `/home`, `/settings`, `/bookmarks`, `/trending`, `/digest`.
- **Route Guards**: Evaluated inside `AuthInitializer` ([providers.tsx](file:///c:/Users/zakau/NewsIQ/apps/web/src/components/providers.tsx)). If a user attempts to access a protected route without a valid token session, they are redirected to `/login?redirect=pathname` to prevent content flashing.

---

## 3. Client State Management (Zustand)

Global UI and authentication states are maintained in Zustand stores with persistence:

### A. Auth Store (`stores/auth-store.ts`)
- **State**: `user` (metadata), `isAuthenticated`, `isLoading`.
- **Actions**: `setUser`, `setLoading`, `logout`.
- **Mechanism**: Saves non-sensitive fields to LocalStorage (`newsiq-auth`) to bypass layout flashes during initial load.

### B. UI Store (`stores/ui-store.ts`)
- **State**: `sidebarOpen`, `preferredSummary` (`short`, `long`, `timeline`), `activeCategory`.
- **Mechanism**: Persists visual preferences under `newsiq-ui` in LocalStorage, matching the functional cookies category.

---

## 4. API Client & Refresh Interceptor
All HTTP requests to the backend API are routed through `apiClient` in [api-client.ts](file:///c:/Users/zakau/NewsIQ/apps/web/src/lib/api-client.ts).
- **Credentials**: `withCredentials: true` is configured to ensure that the backend's HTTP-Only cookies are transmitted securely.
- **In-Memory JWT**: Access tokens are kept strictly in-memory (`token-store.ts`) to eliminate XSS token theft vectors.
- **Token Rotation Interceptor**:
  1. Requests append `Authorization: Bearer <in_memory_token>` in a request interceptor.
  2. If the API returns a `401 Unauthorized` response, the interceptor pauses the request queue, triggers a POST to `/auth/refresh` using the HTTP-only `refresh_token` cookie, sets the new in-memory `access_token`, and retries all failed requests in the queue.
  3. If the refresh fails, it redirects the browser to `/login`.

---

## 5. Consent Management Integration (CMP)
The frontend blocks all analytics/marketing scripts using `ConsentProvider` ([consent-provider.tsx](file:///c:/Users/zakau/NewsIQ/apps/web/src/components/legal/consent-provider.tsx)):
1. **Initial Mount**: Pulls the unique `niq_anonymous_id` from local storage (or generates a new one).
2. **Region & Preferences Sync**:
   - Queries `GET /consent/region` to determine if the country demands explicit opt-in (EU/UK/IN) or opt-out (CA/ROW).
   - Queries `GET /consent/preferences` to check if settings already exist.
   - If not found or if the version does not match `CONSENT_VERSION`, it opens the floating `CookieBanner`.
3. **Tracker Enforcement**: Checks toggles in real-time. Script tags for Google Analytics, PostHog, Meta, and LinkedIn are injected only if consent is active. On withdrawal, it reloads the browser to flush tracking variables.
