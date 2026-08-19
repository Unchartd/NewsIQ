# Breaking News & Trending Selection Audit

**Date:** 2026-08-19
**Scope:** how a story becomes "BREAKING" (home banner) and how `/trending`
and the trending sidebar rank stories — the scoring formula
(`compute_trending_score`), when it runs, what serves it, and what the UI
does with it.

Every number below is measured against production (304 active stories at
audit time).

---

## Executive summary

**"BREAKING" is fabricated.** The banner shows whatever story the feed
returns first — sorted by `updated_at`, i.e. most recently *re-clustered* —
with a hardcoded `time="Just now"`. At audit time that was a **72.9-hour-old
story** whose cluster happened to gain an article 4 minutes earlier. There
are no breaking criteria anywhere in the codebase: no recency threshold, no
source-velocity check, nothing. Every visitor sees a BREAKING banner on
every page load, always claiming "Just now".

**"Trending" is a ranking of stale snapshots.** The formula itself is
reasonable — `0.40×sources + 0.35×recency + 0.25×engagement` — but it is
evaluated only when clustering touches a story and never again. The recency
term therefore freezes at write time: a story keeps the recency it had at
its last update forever. Measured on the top 50 by score, the frozen recency
inflates scores by an average of **0.116** (max **0.350** — the entire
recency budget) versus honest evaluation. The #1 trending story was 49 hours
old; #12 was **105 hours old** (4.4 days).

**A quarter of the formula does nothing.** Engagement across all 3,880
metric rows: 213 views, 0 bookmarks, 0 shares — `engagement_score ≈ 0`
everywhere (the wiring works; the traffic isn't there yet). The effective
formula is `0.40×sources + 0.35×frozen_recency`.

**The trending page's tabs are fake.** `activeTab` ("today") changes the
React Query cache key but is never sent to the API — switching tabs refires
the identical request.

---

## How it works today, exactly

### Breaking (home banner)

`home-content.tsx:181`:

```tsx
{hasStories && (
  <BreakingBanner
    text={`${uniqueStories[0].headline} — ${uniqueStories[0].source_count} sources covering`}
    time="Just now"
    ...
```

`uniqueStories[0]` is row 1 of `GET /stories` with no sort param →
`ORDER BY updated_at DESC`. Whatever cluster was most recently touched — by
a new article, a re-synthesis, a reconciliation — is "BREAKING", labeled
"Just now" unconditionally. Measured: the current banner story was first
seen 72.9h ago.

### Trending (page + sidebar)

`GET /stories?trending=true` → `ORDER BY trend_score DESC`. No time window:
any active story is eligible forever.

`trend_score` is written by `compute_trending_score`
(`clustering_service.py:2346`) — called only from batch story creation,
incremental merge, and two admin endpoints. **No scheduled task ever
recomputes it.** Verified: nothing in the beat schedule touches trend
scores.

```text
what /trending served at audit time (top 15):
score=0.750  age= 49.4h  srcs=9   West Bengal CM Denies BJP Role...
score=0.750  age= 29.6h  srcs=5   Indian Security Forces Detain...
score=0.750  age= 12.8h  srcs=8   SIT Clears Champat Rai...
...
score=0.510  age=105.3h  srcs=3   Sukhbir Badal Undergoes Surgery...
score=0.510  age= 82.8h  srcs=11  Iran Rejects Trump's Claim...
```

Note the last row: **11 sources** — the most-covered story in the list —
ranked 15th, because (a) the source term caps at 5 (`min(n/5, 1.0)`), so 11
sources scores the same as 5, and (b) its score froze 38.7h ago.

### The formula's terms, audited

| Term | Weight | Status |
|---|---|---|
| Source diversity `min(n/5, 1)` | 0.40 | works, but caps exactly where differentiation starts mattering; 3 stories tie at the cap |
| Recency `exp(-t/6h half-life)` | 0.35 | **frozen at write time** — the defect |
| Engagement `(v + 3b + 5s)/500` | 0.25 | inert: 213 views / 0 bookmarks / 0 shares across all stories |

What's *not* in the formula: **velocity** — articles or sources added per
hour. Size and speed are different things; a 9-source story that took 3 days
is a big story, a 5-source story that took 40 minutes is a breaking one.
Trending-as-implemented measures size at a stale timestamp.

---

## Defects, ranked

| # | Defect | Severity | Where |
|---|---|---|---|
| B1 | BREAKING = most recently updated story, hardcoded "Just now" | **P0 — fabricated claim to users** | `home-content.tsx:181` |
| T1 | Recency evaluated at write time, never refreshed; no recompute task | **P0 — trending is stale by design** | `compute_trending_score` + beat schedule |
| T2 | No eligibility window — 4-day-old stories serve as "trending" | P1 | `list_stories` trending branch |
| T3 | Trending tabs don't do anything | P1 — fake UI control | `trending-client.tsx:41-54` |
| T4 | Source cap at 5 erases differentiation among the biggest stories | P2 | formula |
| T5 | Engagement term inert at current traffic; dilutes the two live terms | P2 | formula |
| B2 | "Top Stories" feed sort is `updated_at` — re-synthesis bumps old stories above new ones | P2 | `list_stories` default sort |

---

## Recommendations

### 1. Make trending honest: score at read time (fixes T1, T2)

At 304 active stories, ranking in SQL at query time is trivially cheap and
always current:

```sql
ORDER BY 0.5 * LEAST(source_count/5.0, 1.0)
       + 0.5 * EXP(-EXTRACT(EPOCH FROM (now() - first_seen_at)) / 3600 * 0.1155)
  DESC
```

Keep the stored `trend_score` for observability/back-compat, but stop
*ranking* by a frozen number. Add `WHERE updated_at > now() - interval '48
hours'` as the eligibility window. (Alternative: a beat task rescoring every
5 minutes — works, but is a second copy of truth that can silently stop,
exactly like every silent-staleness bug this audit series has found.)

### 2. Define breaking as a criterion, not a position (fixes B1)

A story is breaking when it is *young and picking up coverage fast* — both
facts already in the database:

```text
breaking :=  first_seen_at within 2h
         AND source_count >= 3
         (i.e. ≥3 independent publishers within 2 hours of first sighting)
```

Serve it from the backend (`is_breaking` in the list response, or a
`/stories/breaking` endpoint) so web, admin, and any future push
notifications agree. The banner then: renders only when a qualifying story
exists, shows the real age ("23 min ago"), and hides otherwise. An absent
banner is honest; "Just now" on a 3-day-old story is not.

### 3. Add velocity to trending (the actual "trending" signal)

`articles.created_at` per story gives arrival times for free:

```text
velocity = articles added in last 6h / total articles
```

Blend: `0.35×sources + 0.35×recency + 0.30×velocity` until engagement data
exists. When real traffic arrives, reintroduce engagement by reducing the
others — not by leaving a dead term in place.

### 4. Small fixes that fall out

* Soften the source cap: `LEAST(ln(1+n)/ln(6), 1.2)` or raise cap to 10 —
  let 11 sources beat 5.
* Make the trending tabs real (`today` → 24h window, `week` → 7d) or delete
  them.
* Feed default sort: `first_seen_at DESC` for "Top Stories" (new stories
  first), or the read-time trending expression — but not `updated_at`,
  which rewards re-synthesis churn.

### Effort

Items 1+2 are each ~half a day including tests; 3 and 4 another day
together. All are backend-decidable and testable against the measurements
above (the 105h story must leave trending; the banner must go absent when
nothing qualifies).

---

## Implementation (2026-08-19) — and a correction the data forced

Fixes 1, 3 and 4 shipped as designed. **Fix 2 did not**, because measuring
before building showed the proposed criterion was unreachable.

### The correction: there is no breaking news here

The audit proposed `first_seen_at within 2h AND source_count >= 3`. Measured
against production, that returns **zero stories, permanently**:

```text
median gap between first_seen_at and the story row being created : 72.0h
median age of reporting inside a story discovered in the last 6h : 69.1h

stories qualifying as "discovered recently AND reporting is fresh AND 3+ sources"
  discovered <2h,  newest article <6h  : 0
  discovered <2h,  newest article <12h : 0
  discovered <6h,  newest article <12h : 0
  discovered <6h,  newest article <24h : 0
  discovered <12h, newest article <24h : 0
```

Two distinct problems surfaced:

1. **`first_seen_at` is not a story age.** It is
   `min(published_at)` across the cluster, so it moves *backward* whenever an
   older article joins. It is 72h behind the story row's own `created_at` at
   the median, and its p90 gap is ~15,800h — articles carrying nonsense
   publish dates. It cannot key any freshness decision.
2. **The pipeline is ~3 days behind publication.** Even for stories
   discovered in the last six hours, the median article inside them is 69
   hours old.

A product three days behind publication cannot truthfully print BREAKING.
Shipping that label would have been the same class of defect as the
fabricated contradictions and the "AI Comparative Analysis" that was neither
— a claim the system cannot support.

**What shipped instead:** `is_top_story` — surfaced by us within 6h, with 3+
independent publishers — keyed on `created_at` (immutable, actually
monotonic). The banner reads **TOP STORY**, renders only when a story
qualifies, and makes no time claim at all, because there is no honest one to
make. Measured: 3–6 stories qualify at any moment, so the banner is useful
rather than permanently blank.

Independent corroboration: `clustering_service.py:402` already triggers
reflection on `created_at < 2h AND unique_sources >= 3` — the same criterion,
arrived at separately. (Its companion `getattr(story, "is_breaking", False)`
reads a column that does not exist and is always False.)

### Trending, verified against production

Read-time ranking replaced the frozen `trend_score`, with a 48h eligibility
window and `window_hours` for the (now functional) tabs:

```text
                      before              after
top result age        49.4h               4.2h
oldest served         105.3h              46.3h
#1 by stored score    0.750 @ 41.8h  ->   rank 13 (live 0.353)
```

Formula: `0.35 x ln(1+sources)/ln(6) + 0.35 x exp(-t/6h) + 0.30 x velocity`,
evaluated by Postgres. The log curve replaces `min(n/5, 1)`, which had scored
5 and 11 publishers identically; velocity counts articles arriving in the
last 6h, so size and speed are finally distinguished.

### Still open

**The 72h ingestion lag is the real product ceiling.** Everything above ranks
what the pipeline has; none of it makes the pipeline faster. Genuine breaking
coverage requires sub-hour discovery, which is a crawler/discovery-cadence
question, not a ranking one — and it is the single highest-value thing left
in this document.

The engagement term is still inert (213 views, 0 bookmarks, 0 shares) and was
dropped from the live formula rather than left as a dead 25% weight; it
should return when there is traffic to measure.
