# NewsIQ Frontend Audit — Public Web App and Admin Dashboard

**Date:** 2026-08-17
**Scope:** `apps/web` (121 files, 21,450 lines) and `apps/admin` (23 files, 7,253 lines)
**Dimensions:** correctness and data wiring, performance, accessibility, SEO

## Method and its limits

Static analysis of the source, plus a production build and queries against the
production database to confirm what data actually exists. Every number below is
counted, not estimated.

**What this audit did not do**, and what would be needed to close it out:

* No browser was driven. No axe-core, Lighthouse, or screen-reader pass was run,
  so contrast ratios, focus order, and real Core Web Vitals are unmeasured.
* No visual or responsive review — nothing here says whether the product *looks*
  right, only how it is built.
* Findings are labelled **CONFIRMED** (counted in source or measured in
  production) or **LIKELY** (strong structural evidence, not executed).

---

## Executive summary

```text
SEO:            8/10   genuinely well built; two landing pages invisible to crawlers
Correctness:    6/10   story page exemplary; ~39 queries render nothing on failure
Performance:    5/10   no code splitting, 66 of 95 files client-side, no images
Accessibility:  3/10   57% of inputs unnamed, 46 keyboard-inaccessible controls
Admin UI:       6/10   structurally cleaner than web, but almost no error states
```

The public app's **SEO work is the strongest part of this codebase** — better
than most news products. Accessibility is the weakest and has the clearest legal
and user-impact exposure.

---

## P0 — Accessibility failures

### A1. 31 of 54 inputs have no accessible name — CONFIRMED

Classified every non-hidden `<input>` by how it obtains a name:

```text
named — wrapping <label> contains text : 22
named — aria-label / aria-labelledby   :  0
named — id + htmlFor                   :  1
UNNAMED — label wraps but has no text  :  2
UNNAMED — no label at all              : 29
                                   → 31 of 54 (57%) unnamed
```

A screen reader announces these as "edit text, blank". Affected surfaces include
search (`search-client.tsx:160`), bookmarks (`bookmarks/page.tsx:130`) and the
digest setup flow (four separate fields).

The two "label wraps but has no text" cases are toggles whose `<label>` contains
only styling `<div>`s (`digest/setup/page.tsx:450`) — the association is valid,
there is simply nothing to announce.

**WCAG 4.1.2 (Name, Role, Value), Level A.**

**Fix:** `aria-label` on standalone inputs; give toggle labels a visually-hidden
text node. Roughly a one-line change per field.

### A2. 46 keyboard-inaccessible click targets — CONFIRMED

```text
<div|span|li> with onClick        : 46
…of those with onKeyDown/role/tabIndex : 0
```

Every one is mouse-only: not reachable by Tab, not activatable by Enter or
Space, and not announced as interactive.

**WCAG 2.1.1 (Keyboard), Level A.**

**Fix:** use `<button type="button">` with reset styling. Adding
`role="button" tabIndex={0}` plus a key handler works but has to be repeated
correctly 46 times; the element swap is less error-prone.

### A3. No skip link — CONFIRMED

No "skip to content" affordance anywhere. With 9 `<nav>` blocks, a keyboard user
tabs through the full navigation on every page load. **WCAG 2.4.1, Level A.**

### A4. Heading structure — ~~CONFIRMED~~ **WITHDRAWN**

> **This finding was wrong.** It counted `<h1>` occurrences in source, not
> simultaneously rendered ones. Both `digest/setup` (8) and `onboarding` (4) gate
> every step behind `step === "…"` conditionals, so exactly one `<h1>` is in the
> DOM at any time. The document outline is correct and nothing needed changing.
>
> The original text hedged — "probably not simultaneously visible" — and then
> listed it as a defect anyway. Counting source occurrences is not the same as
> measuring rendered output, and the hedge should have been resolved before the
> finding was raised.

Separately, and this one holds: **zero `<article>` elements existed** in a news
product — story content was rendered in `<div>`s, leaving assistive tech and
reader modes no way to identify where the story begins. Fixed on the story page.

### What is already right

`lang="en"` is set, `prefers-reduced-motion` is respected in `globals.css`,
`focus-visible` styling is present (9 rules), and 8 pages carry a `<main>`
landmark. The foundations exist — they are just applied inconsistently.

---

## P1 — SEO: two landing pages are invisible to crawlers

### S1. `/home` and `/trending` render no content server-side — CONFIRMED

Both are thin server wrappers around client components:

```text
/home     → HomeContent      "use client" + useQuery/useInfiniteQuery
/trending → TrendingPage     "use client" + useQuery
```

The build confirms both as static (`○`), so the prerendered HTML contains the
shell and **no stories**. A crawler that does not execute JavaScript indexes an
empty page, and the LCP element requires a JS bundle plus a client round-trip.

This matters because they are the product's primary landing pages. `/story/[id]`
and `/category/[slug]` are correctly dynamic (`ƒ`) and server-rendered.

**Fix:** fetch on the server and pass through as `initialData`, exactly as the
story page already does — the pattern is in the codebase and works.

### S2. Legal pages carry no metadata — CONFIRMED

`(legal)/legal`, `(legal)/privacy` and `(legal)/tos` are client components, so
they cannot export `metadata` and inherit only the root layout's defaults. They
are indexable, publicly linked, and title-less.

**Fix:** move the metadata into a `layout.tsx` per route, or split the client
half into a child component.

### What is already right — and it is a lot

* `robots.ts` with an explicit AI-crawler allowlist (GPTBot, ClaudeBot,
  PerplexityBot) and auth/admin paths disallowed
* `sitemap.ts` with a 15-minute revalidate, plus a dedicated
  `news-sitemap.xml` honouring Google News's 2-day eligibility window
* `generateMetadata` on both dynamic routes, with canonical URLs
* **11 JSON-LD builders** — NewsArticle, Organization, WebSite, Breadcrumb, FAQ,
  CollectionPage, SourceCoverage, Timeline
* Open Graph images resolve to a real article image
  (`story.articles?.find(a => a.image_url)`), falling back to a default

This is materially better SEO than most news products ship.

---

## P1 — Correctness and data wiring

### C1. ~39 of 47 queries have no error state — CONFIRMED

```text
useQuery / useInfiniteQuery calls : 47
isLoading handled                 : 67 references
isError / error handled           :  8 references
```

Loading is handled almost everywhere; failure is not. A failed request renders
an empty region with no message and no retry — indistinguishable from "no
results". The admin app is worse: **48 queries, 2 error references.**

**Fix:** a shared `<QueryBoundary>` that renders skeleton, error-with-retry, and
empty states from one place.

### C2. No article imagery is rendered anywhere — CONFIRMED

```text
next/image imports : 0
<img> tags         : 0
image_url usages   : 0   (in page/component code)
```

Yet production holds **12,724 of 18,151 articles (70%) with an `image_url`**.

The data is collected by the crawler, stored, and used *only* for Open Graph
tags. Every story page, card and list is text-only.

This is a **product decision to confirm, not a defect to fix** — a deliberately
text-first news reader is a coherent choice. Flagging it because the asymmetry
(crawl it, store it, share it, never show it) looks unintended. `stories` has no
image column, so surfacing it would mean joining through articles.

### C3. Typing — CONFIRMED

`apps/web` is reasonably typed: 34 `any` occurrences, 13 of them in
`settings/page.tsx`. `apps/admin` has **50** remaining outside the pipeline page
that was typed in #131.

Three stray `console.*` calls remain in shipped code.

---

## P2 — Performance

### F1. No code splitting — **OVERSTATED, partially withdrawn**

The counts were right:

```text
next/dynamic or React.lazy : 0 occurrences
"use client" files         : 66 of 95
largest client components  : settings 2,520 lines · landing-client 2,460 lines
```

The conclusion drawn from them was not. **Next.js already code-splits per
route**, so the absence of `next/dynamic` does not mean everything ships to
everyone. The two files named as "obvious candidates" are route entry points and
are already split — lazy-loading them would achieve nothing.

Measured after the fact: 52 chunks, 1.8 MB total across all of them, and a
446 KB shared root that every route loads regardless.

`next/dynamic` only earns its place for a heavy component **inside** a route that
is not needed at first paint. The real instance was the cookie consent modal:
mounted globally through `providers.tsx`, so shipped on every page, but rendered
only once a reader opens it. It is now a separate 8.1 KB chunk, verified by
locating its text in a distinct file after the build.

The lesson matches A4 and C1: a grep count is evidence of a pattern, not of an
impact. Measure the impact before prescribing the fix.

### F2. Client-side data on landing pages

Same root cause as S1: `/home` and `/trending` cannot paint content until JS
loads and a request completes. Fixing S1 fixes this.

### F3. Story pages are fully dynamic with no ISR — LIKELY

`/story/[storyId]` builds as `ƒ`, so every request re-fetches server-side. For
published news this is a good ISR candidate (`revalidate` of a few minutes),
which would cut both API load and TTFB. Worth confirming against the freshness
requirement before changing.

---

## Admin dashboard

Structurally cleaner than the public app on the things that matter for an
internal tool:

| Check | Result |
|---|---|
| Keyboard-inaccessible click targets | **0** ✅ |
| `useQuery` calls | 48 |
| Error states handled | **2** ❌ |
| `<main>` landmarks | 1 (across 13 pages) |
| `any` remaining | 50, outside the pipeline page typed in #131 |

The typed API layer added in #131 covers the pipeline page's queries. The
remaining pages — failures, costs, clusters, entities, quality — still consume
`any` and would benefit from the same accessors, which already exist.

Accessibility is a lower priority here than for the public product, but the
missing error states are not: an internal tool that silently renders nothing on
a failed request is exactly how the observability gaps in the previous audit
stayed invisible.

---

## Recommended order

**Phase 1 — Accessibility, Level A failures (~2 days)**
A1 unnamed inputs, A2 keyboard targets, A3 skip link. These are legal-exposure
items and each is mechanical.

**Phase 2 — Make failures visible (~1 day)**
C1 shared query boundary across both apps. Cheap, and it stops both products
lying about their own state.

**Phase 3 — Server-render the landing pages (~1 day)**
S1, which also resolves F2. The pattern already exists on the story page.

**Phase 4 — SEO tidy-up (~0.5 day)**
S2 legal metadata, A4 heading structure, `<article>` semantics.

**Phase 5 — Performance (~1–2 days)**
F1 code splitting, F3 ISR evaluation.

**Open product question:** C2 — should article imagery be rendered at all?
Everything else above is a defect; that one is a decision.

---

## To close out this audit properly

The highest-value next step is not on this list: **run axe-core and Lighthouse
against the deployed site.** Static analysis found the structural failures, but
contrast, focus order, and real Core Web Vitals cannot be counted from source,
and those are exactly where remaining accessibility and performance problems
tend to hide.
