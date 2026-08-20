# Google Tag (GA4) & PostHog Implementation Audit

**Date:** 2026-08-19
**Scope:** `apps/web/src/lib/analytics/*` (service, dispatcher, GA4 and PostHog
providers), the gtag bootstrap in `app/layout.tsx`, the consent layer, and
`components/analytics/analytics-tracker.tsx`.

Verified against the **live production site**, not just source.

---

## Executive summary

The instrumentation layer is genuinely well built — a typed event map, a
provider-agnostic dispatcher, consent gating, and **33 call sites** across 8
files covering pageviews, scroll depth, read time, Web Vitals, search funnels
and auth. Almost none of it reaches a analytics backend.

```text
GA4      loads with a real measurement ID (G-2RJHNS23RH)
         ...but gtag('config', ...) is NEVER called on page load
         -> no page_view, and events have no configured stream

PostHog  posthog-js is NOT a dependency, no SDK is ever loaded,
         and the token in production is a placeholder
         -> window.posthog is permanently undefined; every call no-ops
```

Live evidence:

```text
$ curl -s https://newsiq.online/home | grep -oE "gtag\('[a-z]+'"
      2 gtag('consent'
      2 gtag('js'
      0 gtag('config')          <-- the call that starts measurement

$ curl -s https://newsiq.online/home | grep -c "posthog"
      0
```

---

## A1. GA4 never receives a `config` call — CONFIRMED, P0

`layout.tsx` ships the standard preamble but stops one line short:

```js
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('consent', 'default', {...});
gtag('js', new Date());
// gtag('config', MEASUREMENT_ID)  <-- missing
```

`gtag('config', ID)` is what binds the loaded library to a measurement and
starts sending. Without it gtag.js loads (418 KB, HTTP 200 — Google serves the
library for *any* id, so a 200 proves nothing) and events queue in `dataLayer`
with nowhere to go.

The only `config` calls in the entire codebase are in
`providers/ga4.ts:31` (`identify`) and `:73` (`reset`) — both of which run
**only when a user logs in or out**. So:

| Visitor | `config` called? | Data collected |
|---|---|---|
| Anonymous (the entire public news audience) | no | **none** |
| Logged in, after `identify()` | yes | events flow |

For a public news product whose traffic is overwhelmingly anonymous, this is
effectively total data loss.

**Fix:** add `gtag('config', '<ID>', { send_page_view: false })` to the
bootstrap script, immediately after `gtag('js', ...)`. `send_page_view: false`
because `analytics-tracker.tsx:217` already sends pageviews explicitly on route
change — leaving it on would double-count every SPA navigation.

## A2. PostHog is not installed — CONFIRMED, P0

* `posthog-js` does not appear in `apps/web/package.json`.
* No script tag, no import, nothing loads it.
* `PostHogProvider.initialize()` sets `isInitialized = !!window.posthog`,
  which is always `false`, and every method early-returns on
  `if (!window.posthog) return`.
* Production carries `NEXT_PUBLIC_POSTHOG_TOKEN=phc_mock_token_newsiq` — a
  placeholder, not a project key.

The provider is written correctly and is simply never given an SDK. Every
PostHog call across all 33 instrumentation sites is a silent no-op, and has
been since the provider was written.

**Fix (decide first):** either
1. install `posthog-js`, initialise it behind analytics consent with a real
   project token, and keep the provider as-is; or
2. delete the provider and its registration.

Shipping a provider that cannot work is worse than not having one — it makes
the dashboard look instrumented.

## A3. `NEXT_PUBLIC_*` runtime env is stale and misleading — CONFIRMED, P2

The production container carries:

```text
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-NEWSIQ          # placeholder
NEXT_PUBLIC_POSTHOG_TOKEN=phc_mock_token_newsiq # placeholder
```

but the **shipped bundle** contains `G-2RJHNS23RH`. `NEXT_PUBLIC_*` values are
inlined at *build* time, so the runtime variables are inert — they neither
configure anything nor reflect what is deployed. Anyone debugging analytics by
reading the container env will reach the wrong conclusion (I nearly did).

**Fix:** remove the placeholders from the runtime environment and set them as
build args, so the deployed value and the declared value are the same thing.

## A4. Hardcoded fallback IDs mask misconfiguration — CONFIRMED, P2

`ga4.ts:30`, `ga4.ts:73` and `layout.tsx:222` all default to the literal
`"G-NEWSIQ"` when the env var is missing. A missing measurement ID should be
loud, not silently substituted with a string that looks plausible in a log and
silently discards data.

**Fix:** if the ID is absent, skip loading GA4 entirely and warn once.

## A5. Consent defaults to denied, with no observable grant path — LIKELY

`gtag('consent', 'default', ...)` reads `niq_consent_preferences` from
`localStorage` and denies `analytics_storage` when absent, which is correct
GDPR behaviour. `consent-provider.tsx:141-143` does issue
`gtag('consent', 'update', ...)` when preferences change, so the mechanism
exists.

Not verified in a browser: whether a user who accepts analytics in the cookie
modal actually flips `analytics_storage` to `granted` **and** whether anything
then calls `config`. Given A1, granting consent today still collects nothing.
Worth re-testing after A1 lands.

---

## What is already right

Worth stating plainly, because the diagnosis above is not a criticism of the
design:

* `types.ts` defines a **typed event map** (`EventPayloadMap`), so event names
  and their payloads are checked at compile time.
* The dispatcher is genuinely provider-agnostic and **gates every call on
  consent** — `getConsent()` fails closed to `analytics: false`.
* `sanitizePayload` runs on every provider path.
* Coverage is thorough: pageviews on route change, scroll depth, story read
  time and completion, engaged sessions, Web Vitals, search funnel, auth, and
  API errors.

The work needed is at the delivery layer, not the instrumentation layer. That
is the cheap end to fix.

---

## Recommended order

1. **A1** — one line in `layout.tsx`, plus `send_page_view: false`. Restores
   all GA4 collection for anonymous traffic. ~15 minutes.
2. **A2** — decide install-or-delete for PostHog. If installing: real token,
   init behind consent. If not: remove the provider so the dashboard stops
   implying it works.
3. **A3/A4** — move `NEXT_PUBLIC_*` to build args; make a missing ID fail loud.
4. **A5** — verify the consent grant path end to end in a browser once A1 is
   live, and confirm events appear in GA4 realtime.

**Verification gate for A1/A2:** GA4 realtime should show anonymous pageviews
within a minute of deploy, and `curl` on the deployed page should show a
`gtag('config'` occurrence where there are currently zero.
