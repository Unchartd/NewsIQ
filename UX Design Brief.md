# NewsIQ — UI/UX Design Brief
### Version 1.0 | For AI App Builder Use

---

## 1. Design Philosophy

NewsIQ is not a news app that delivers articles. It is a **comprehension engine** — the designer's job is to make understanding feel effortless. Every visual decision must serve clarity, trust, and speed. The user should feel like a well-briefed analyst after 30 seconds, not a reader who just consumed ten tabs.

**Three words that must define every screen:**
> **Clarity. Density. Trust.**

The UI should feel like a premium editorial tool — somewhere between a financial terminal and a beautifully typeset broadsheet — but with the speed of a modern web app. Not flashy. Not minimal to the point of being empty. **Information-rich but never cluttered.**

---

## 2. Design Style

### Primary Style: Editorial Intelligence Dashboard

This is a **data-dense editorial interface** with Swiss Grid foundations. Think Reuters Terminal meets The Economist's digital edition. Characteristics:

- Dense but breathable card-based layouts with clear visual hierarchy
- Strong typographic system that carries personality without decoration
- Restrained use of color — color signals meaning, not aesthetics
- Ink-on-paper contrast ratios for readability at all viewport sizes
- Zero decorative gradients or background noise; backgrounds serve as a canvas, not a statement

### Aesthetic Risk (Signature Element)
The single memorable design element across the product:

> **A living "Signal Bar"** — a thin, animated 3px horizontal bar below the navbar that pulses in the brand red (`#C41E3A`) as new stories are ingested in real-time. It acts like a heartbeat for the platform, reinforcing that this is live intelligence, not static content. On story pages, it transitions to show read-progress. This replaces the typical progress bar with something emotionally resonant for a news product.

---

## 3. Color Palette

### Light Mode (Default)

| Token | Hex | Usage |
|---|---|---|
| `--color-primary` | `#C41E3A` | Brand accent, breaking news badges, trending indicators |
| `--color-ink` | `#0D0D0D` | Primary headlines, key text |
| `--color-ink-secondary` | `#3D3D3D` | Body copy, secondary labels |
| `--color-ink-muted` | `#6B6B6B` | Timestamps, metadata, captions |
| `--color-surface` | `#F7F7F5` | Page background (warm off-white, not pure white) |
| `--color-card` | `#FFFFFF` | Card backgrounds |
| `--color-border` | `#E2E2DC` | Dividers, card borders |
| `--color-accent-blue` | `#1A56DB` | Links, CTA buttons, source URLs |
| `--color-accent-amber` | `#D97706` | Trending badge, high-signal indicators |
| `--color-success` | `#16A34A` | Saved confirmation toast |
| `--color-error` | `#DC2626` | Error states |

### Dark Mode (System-Triggered)

| Token | Hex | Usage |
|---|---|---|
| `--color-surface` | `#111110` | Page background |
| `--color-card` | `#1C1C1A` | Card backgrounds |
| `--color-border` | `#2E2E2A` | Dividers |
| `--color-ink` | `#F0EFE9` | Primary text |
| `--color-ink-secondary` | `#A8A89E` | Secondary text |
| `--color-ink-muted` | `#6B6B62` | Metadata |
| `--color-primary` | `#E8334A` | Brand accent (slightly brighter for dark bg) |
| `--color-accent-blue` | `#5B8DEF` | Links on dark |

**Dark mode is first-class, not an afterthought.** Both modes must be fully specified.

### Color Usage Rules
- `--color-primary` (red) is reserved **exclusively** for: brand logo, breaking badges, the signal bar, critical alerts, and active nav states. Nowhere else.
- Never use red as a background fill on content areas — red = urgency only.
- Categories get a consistent color mapping (Politics: `#6B21A8`, Tech: `#1D4ED8`, Business: `#065F46`, Sports: `#92400E`, Health: `#0369A1`, Science: `#7C3AED`, Weather: `#0E7490`).

---

## 4. Typography

### Type Scale

```
Font Pairing:
  Display / Headlines: "Newsreader" (Google Fonts) — serif, editorial authority
  Body / UI: "Inter" (Google Fonts) — neutral, highly legible at small sizes
  Data / Metadata: "Inter" Tabular variant — for numbers, timestamps, source names
```

**Why Newsreader + Inter:** Newsreader brings editorial credibility and trust (newspapers, serious publications) while Inter handles dense UI text with precision. Together they signal: *this product takes information seriously.*

### Type Scale Definitions

| Role | Font | Size | Weight | Line Height |
|---|---|---|---|---|
| Story Headline (Large) | Newsreader | 28px / 1.75rem | 600 | 1.25 |
| Story Headline (Card) | Newsreader | 20px / 1.25rem | 500 | 1.3 |
| Section Header | Inter | 13px / 0.8125rem | 700 | 1.2 |
| Body Summary | Inter | 15px / 0.9375rem | 400 | 1.65 |
| Metadata (time, source) | Inter | 12px / 0.75rem | 400 | 1.4 |
| Category Label | Inter | 11px / 0.6875rem | 700 | 1.2 |
| CTA Button | Inter | 14px / 0.875rem | 600 | 1.0 |
| Data/Numbers | Inter | 13px / 0.8125rem | 600 | 1.3 |

**Section headers (e.g., "TRENDING", "POLITICS", "SOURCE COMPARISON") use ALL CAPS Inter at 11–13px, letter-spacing: 0.08em.** This is a structural device borrowed from broadsheets and financial data products — it encodes category meaning, not decoration.

### CSS Import

```css
@import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;0,700;1,400&family=Inter:wght@300;400;500;600;700&display=swap');
```

---

## 5. Layout System

### Grid

```
Desktop: 12-column grid, max-width 1280px, gutter 24px, side margin 32px
Tablet: 8-column grid, max-width 960px, gutter 20px, side margin 24px
Mobile: 4-column grid, full-width, gutter 16px, side margin 16px
```

### Breakpoints

```
xs:  375px   (small mobile)
sm:  640px   (large mobile)
md:  768px   (tablet portrait)
lg:  1024px  (tablet landscape / small laptop)
xl:  1280px  (desktop)
2xl: 1536px  (wide desktop)
```

### Spacing Scale (8px base unit)

```
4px   — micro (icon gaps, tight labels)
8px   — xs (inner padding, tag gaps)
12px  — sm (compact card padding)
16px  — md (standard element spacing)
24px  — lg (section gaps, card padding)
32px  — xl (between major sections)
48px  — 2xl (section headers, hero spacing)
64px  — 3xl (page-level breathing room)
```

### Layout Patterns by Screen

**Home Feed (Desktop):**
```
┌─────────────────────────────────────────────────────┐
│ NAVBAR [Logo] [Search] [Trending] [Categories] [Pro] │
│ SIGNAL BAR (3px animated)                            │
├───────────────────────────┬─────────────────────────┤
│   MAIN FEED (8 cols)      │   SIDEBAR (4 cols)      │
│                           │                         │
│  [Category Tabs]          │  [Trending Now]         │
│  [Story Card]             │  [Top Sources]          │
│  [Story Card]             │  [Location Filter]      │
│  [Story Card]             │  [Digest CTA]           │
│  ...infinite scroll       │                         │
└───────────────────────────┴─────────────────────────┘
```

**Story Detail Page (Desktop):**
```
┌──────────────────────────────────────────────────────┐
│ NAVBAR                                               │
│ SIGNAL BAR (read progress mode)                      │
├────────────────────────────┬─────────────────────────┤
│  STORY CONTENT (7 cols)    │  RIGHT PANEL (5 cols)   │
│                            │                         │
│  [Category + Time]         │  [Summary Switcher]     │
│  [Headline — Newsreader]   │  [Key Facts]            │
│  [Summary Block]           │  [Source Coverage]      │
│  [Timeline]                │  [Related Stories]      │
│  [Difference Engine Table] │  [Bookmark + Share]     │
│  [Source Cards]            │                         │
└────────────────────────────┴─────────────────────────┘
```

**Mobile Layout:**
```
┌────────────────────────┐
│ [Logo] [Search] [Menu] │  ← Sticky top navbar
├────────────────────────┤
│ SIGNAL BAR             │
│ [Category Tabs — H.Scroll] │
│ [Story Card]           │
│ [Story Card]           │
│ ...                    │
├────────────────────────┤
│ [Home][Trend][Search][Bkm][Profile] │  ← Bottom Nav
└────────────────────────┘
```

---

## 6. Component Specifications

### 6.1 Story Card

The most rendered component in the product. Must be pixel-perfect.

```
┌─────────────────────────────────────────────────────┐
│ [CATEGORY BADGE]  [LOCATION]              [TIME]    │
│                                                     │
│ Headline text in Newsreader, 20px, weight 500       │
│ Max 2 lines, ellipsis on overflow                   │
│                                                     │
│ Summary text in Inter, 14px, muted color            │
│ Max 3 lines — switches based on user preference     │
│                                                     │
│ ─────────────────────────────────────────────────   │
│ [●●● 8 Sources]  [↑ Trending]        [🔖 Bookmark] │
└─────────────────────────────────────────────────────┘
```

**Specifications:**
- Border: 1px solid `--color-border`, border-radius: 6px
- Padding: 20px
- Background: `--color-card`
- Hover: `box-shadow: 0 2px 12px rgba(0,0,0,0.08)`, border-color shifts to `--color-ink-muted`, `cursor: pointer`
- Transition: `150ms ease-out` on shadow and border
- Category badge: pill shape, 6px border-radius, colored per category system
- Sources count: small dot indicators (up to 5), then "+ N more"
- Bookmark: outline icon by default → filled on save, red accent, `transition: 150ms`
- No images in MVP (placeholder space reserved, image lazy-loaded when available)

### 6.2 Navbar

```
Desktop:
[NewsIQ Logo]  [Search Input — 320px wide]  [Trending] [Categories▾] [Location▾] [🔖] [Avatar] [☀/🌙]

Mobile:
[NewsIQ Logo]                                                                    [🔍] [☰]
```

- Position: `sticky top-0`, `z-index: 100`
- Background: `--color-card` with `backdrop-filter: blur(8px)` and `background: rgba(255,255,255,0.92)`
- Height: 56px desktop, 52px mobile
- Bottom border: 1px `--color-border`
- Logo: "NewsIQ" wordmark — "News" in Inter 700, "IQ" in Newsreader italic 700, primary red

### 6.3 Summary Switcher

A segmented control on the story page to switch between summary depths.

```
[1-line] [Short] [Detailed]
```

- Active segment: `--color-ink` background, white text
- Inactive: transparent, `--color-ink-muted` text
- Border: 1px `--color-border` around the group
- Border-radius: 6px for group, 4px for segments
- On click: content area animates in with `opacity: 0 → 1`, `translateY: 4px → 0`, `150ms ease`

### 6.4 Source Coverage Table

```
┌──────────────────┬────────────────────────┬──────────┬──────────┐
│ SOURCE           │ FOCUS                  │ TIME     │ LINK     │
├──────────────────┼────────────────────────┼──────────┼──────────┤
│ ● NDTV           │ School closures        │ 2h ago   │ →        │
│ ● The Hindu      │ Rainfall data          │ 3h ago   │ →        │
│ ● Times of India │ Traffic disruption     │ 4h ago   │ →        │
└──────────────────┴────────────────────────┴──────────┴──────────┘
```

- Source dot: colored circle, 8px, unique per source (auto-assigned from a 12-color pool)
- Table header: ALL CAPS Inter, 11px, letter-spacing: 0.08em, `--color-ink-muted`
- Row hover: `--color-surface` background
- Link column: `--color-accent-blue`, opens in new tab
- Mobile: horizontally scrollable, min-width per column enforced

### 6.5 Difference Engine

Displayed as a comparison grid — distinct from a regular table:

```
┌──────────────────────────┬─────────────────┬────────────────────┐
│ FACT                     │ SOURCE A        │ SOURCE B           │
├──────────────────────────┼─────────────────┼────────────────────┤
│ Death toll               │ 5               │ 7 ⚠                │
│ Schools closed           │ Yes             │ Not mentioned ◌    │
│ Rainfall amount          │ 120mm           │ 142mm ⚠            │
└──────────────────────────┴─────────────────┴────────────────────┘
```

- `⚠` icon: amber `--color-accent-amber`, indicates contradiction
- `◌` icon: gray, indicates missing data
- Contradictions row: subtle amber left-border (3px) on the row
- Missing cells: italic text in `--color-ink-muted`

### 6.6 Timeline Component

Vertical timeline, left-aligned rail:

```
8:30 AM  ──●── Heavy rain begins in outer regions
10:00 AM ──●── Roads flooded on Outer Ring Road
11:15 AM ──●── BBMP issues flood warning
1:00 PM  ──●── All schools ordered closed
```

- Rail: 1px solid `--color-border`, centered on the dot
- Dot: 8px circle, `--color-primary` red for most recent, `--color-border` for older
- Time: Inter 12px, tabular-nums, `--color-ink-muted`, min-width: 64px
- Event text: Inter 14px, `--color-ink-secondary`
- Spacing between events: 20px

### 6.7 Category Tabs (Horizontal Scroll)

```
[All] [Politics] [Technology] [Business] [Sports] [Health] [Science] [Weather]
```

- Desktop: full tab bar, no scroll
- Mobile: horizontally scrollable, no scrollbar visible (`scrollbar-width: none`)
- Active tab: bottom-border 2px `--color-primary`, text `--color-ink`, Inter 13px 600
- Inactive: `--color-ink-muted`, hover: `--color-ink-secondary`

### 6.8 Toast Notifications

- Position: bottom-right, 16px from edge
- Max width: 320px
- Border-radius: 8px
- Left-border: 4px colored (green/amber/red by type)
- Auto-dismiss: 4000ms
- Stack: up to 3 visible, oldest fades first
- Enter animation: `translateY(8px) → 0`, `opacity 0 → 1`, `200ms ease`

### 6.9 Loading States

**Skeleton Cards (Story Feed):**
- Match exact card dimensions
- Shimmer animation: `background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)`, `background-size: 400%`, `animation: shimmer 1.5s infinite`
- Show minimum 3 skeleton cards on initial load

**Inline Spinners:**
- Only for buttons (e.g., "Loading more...")
- 16px, `--color-ink-muted`, spin animation

---

## 7. Navigation Architecture

### Desktop Top Navbar
- Logo (left)
- Global search (center-left, expands on focus)
- Trending | Categories dropdown | Location dropdown (center)
- Bookmarks icon | Profile avatar | Theme toggle (right)

### Mobile Bottom Navigation

| Icon | Label | Route |
|---|---|---|
| Home | Home | `/home` |
| TrendingUp | Trending | `/trending` |
| Search | Search | `/search` |
| Bookmark | Saved | `/bookmarks` |
| User | Profile | `/profile` |

- Active state: icon filled, label in `--color-primary`, indicator dot above icon
- Background: `--color-card`, top border: 1px `--color-border`
- Height: 64px (safe area inset-bottom support for iOS)

### Breadcrumb (Location Pages)
```
World > India > Karnataka > Bengaluru
```
- Inter 12px, `--color-ink-muted`, separator: `>` with 8px horizontal margin
- Current page: `--color-ink`, non-linked

---

## 8. Page-Specific UX Directions

### Home Feed
- Default summary level: 1-line (can be changed in preferences)
- Category tabs sticky below navbar when scrolling
- Infinite scroll trigger: 70% scroll depth, loads 10 items
- Skeleton cards appear instantly on scroll trigger
- Empty state: full-card illustration with "Adjusting your feed…" and Refresh button
- No autoplay, no popups on load

### Story Detail Page
- First paint must show: headline, category, time, 1-line summary, source count
- Summary switcher stays visible in sticky position on desktop right panel
- Timeline expands/collapses with smooth 200ms ease transition
- Source Coverage table above the Difference Engine — leads with "who covered it" before "how they differ"
- Related stories: horizontal scroll carousel, max 5 items, card width 280px

### Search Page
- Search input: full-width on mobile, 560px on desktop
- Debounce: 300ms before API call
- Recent searches: shown as dismissible chips below input when focused
- Filters: collapsible panel (mobile: drawer from bottom; desktop: inline above results)
- No results: centered illustration + "No stories match '[query]'" + "Clear filters" link

### Onboarding Flow
- Progress indicator: 4 numbered steps at top (Step 1 of 4)
- Category selection: 2-column grid of pill checkboxes on mobile, 3-column on desktop
- Selected state: filled background in category color, white checkmark
- "Continue" button disabled until validation passes — clear visual state difference
- No skip option on category selection; all others are skippable

### Premium Page
- Three-column pricing table on desktop, stacked on mobile
- Pro plan visually elevated: `box-shadow: 0 0 0 2px --color-primary`, "Most Popular" badge
- Feature list: green checkmark (✓) for included, dash (—) for excluded — no red Xs

---

## 9. Mobile Responsiveness Rules

1. **Touch targets minimum 44×44px** — all buttons, links, interactive elements
2. **Bottom navigation replaces sidebar** entirely on mobile
3. **Horizontal scroll for category tabs** — never wrap to two rows
4. **Story cards full-width** on mobile (`margin: 0 16px`)
5. **Source Coverage Table** — horizontally scrollable on mobile, not collapsed
6. **Modals** become bottom sheets on mobile (border-radius: 16px top corners, drag handle)
7. **Navbar** collapses to logo + search icon + hamburger on mobile
8. **Timeline** left-margin reduced to 0, timestamps above event text on very small screens
9. **No hover-only interactions** — all hover states must have a tap equivalent
10. **Font sizes never below 12px** on any component at any breakpoint

---

## 10. Accessibility Requirements

- WCAG 2.1 AA minimum, target AAA for text contrast
- All interactive elements must have visible focus ring: `outline: 2px solid --color-primary`, `outline-offset: 2px`
- `prefers-reduced-motion`: disable all transition animations, keep instant state changes
- `prefers-color-scheme`: auto-switch dark/light mode; allow manual override persisted in localStorage
- All images: descriptive `alt` text
- Category color alone is never the only indicator — always paired with text label
- Error states: never red-only — always include an icon and text message
- Skip navigation link at top of page (visually hidden, shown on focus)

---

## 11. Motion & Animation Principles

**Use motion to confirm actions and reveal structure — never for decoration.**

| Interaction | Animation | Duration | Easing |
|---|---|---|---|
| Card hover | shadow + border transition | 150ms | ease-out |
| Page route change | fade `0→1` | 200ms | ease |
| Summary switch | `opacity 0→1` + `translateY 4px→0` | 150ms | ease |
| Bookmark toggle | icon fill scale `0.8→1` | 120ms | ease-out |
| Toast appear | `translateY 8px→0` + `opacity 0→1` | 200ms | ease |
| Skeleton shimmer | gradient sweep | 1500ms | linear, infinite |
| Signal bar pulse | opacity `0.6→1→0.6` | 2000ms | ease-in-out, infinite |
| Modal/sheet open | `translateY 100%→0` | 250ms | ease-out |
| Infinite scroll load | skeleton → content fade | 200ms | ease |

---

## 12. Iconography

**Icon Library: Lucide React** (consistent, line-weight uniform, MIT license)

Key icon assignments:

| Action/Concept | Lucide Icon |
|---|---|
| Bookmark | `Bookmark` / `BookmarkCheck` |
| Share | `Share2` |
| Trending | `TrendingUp` |
| Breaking news | `Zap` |
| Search | `Search` |
| Location | `MapPin` |
| Timeline | `Clock` |
| Source comparison | `GitCompare` |
| Settings | `Settings` |
| Notification | `Bell` |
| Premium | `Crown` |
| Categories | `LayoutGrid` |
| Difference/Contradiction | `AlertTriangle` |
| Missing data | `MinusCircle` |

Icon size: 16px for inline/compact, 20px for nav/actions, 24px for empty states

**Never use emoji as UI icons.**

---

## 13. Content & Copy Tone

- **Headlines**: Title Case, Newsreader, neutral and factual — never clickbait
- **Section labels**: ALL CAPS Inter, small, letter-spaced — structural, not decorative
- **Error messages**: Direct, actionable. "Stories couldn't load. Retry." Not "Oops!"
- **Empty states**: Actionable invitation. "No saved stories yet. Bookmark stories to read later."
- **Toast messages**: Past tense for confirmations. "Story saved." "Preferences updated."
- **Onboarding copy**: Present tense, outcome-focused. "Pick topics you care about."
- **AI-generated summaries**: Subtle `✦ AI Summary` label, Inter 11px, `--color-ink-muted`, never prominent

---

## 14. AI-Specific UI Patterns

Since AI summaries are a core feature, they need distinct but unobtrusive treatment:

- **AI content indicator**: A small `✦` symbol (not a robot icon) + "AI Summary" text in `--color-ink-muted`, positioned above the summary block
- **Source count inline**: "Summarized from 8 sources" as sub-label under summary
- **Confidence/freshness**: "Updated 4 min ago" badge on story card using `--color-ink-muted`
- **Contradiction alerts**: The Difference Engine uses amber `AlertTriangle` icon + amber left-border on rows — never hidden or collapsed by default
- **AI Chat (Phase 2)**: Distinct surface — dark background within a drawer panel, message bubbles with clear AI vs User distinction

---

## 15. Design Token Reference (CSS Variables)

```css
:root {
  /* Colors */
  --color-primary: #C41E3A;
  --color-ink: #0D0D0D;
  --color-ink-secondary: #3D3D3D;
  --color-ink-muted: #6B6B6B;
  --color-surface: #F7F7F5;
  --color-card: #FFFFFF;
  --color-border: #E2E2DC;
  --color-accent-blue: #1A56DB;
  --color-accent-amber: #D97706;
  --color-success: #16A34A;
  --color-error: #DC2626;

  /* Typography */
  --font-display: 'Newsreader', Georgia, serif;
  --font-body: 'Inter', -apple-system, sans-serif;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  --space-2xl: 48px;

  /* Borders */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-card-hover: 0 2px 12px rgba(0,0,0,0.08);
  --shadow-modal: 0 16px 48px rgba(0,0,0,0.18);

  /* Animation */
  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 300ms;
  --ease-default: ease-out;

  /* Layout */
  --navbar-height: 56px;
  --sidebar-width: 320px;
  --content-max-width: 1280px;
}

[data-theme="dark"] {
  --color-surface: #111110;
  --color-card: #1C1C1A;
  --color-border: #2E2E2A;
  --color-ink: #F0EFE9;
  --color-ink-secondary: #A8A89E;
  --color-ink-muted: #6B6B62;
  --color-primary: #E8334A;
  --color-accent-blue: #5B8DEF;
}
```

---

## 16. Visual References (Style Analogs)

When making design decisions, reference these products for specific elements:

| Element | Reference Product | Why |
|---|---|---|
| Overall density + editorial feel | Financial Times (ft.com) | Dense, trusted, typographic hierarchy |
| Card grid + trending feed | The Economist digital | Restrained color, strong headlines |
| Dark mode + data tables | Bloomberg Terminal lite | Information density without clutter |
| Category + location filters | Ground News | Transparent, comparative structure |
| Skeleton loading + feed | Artifact app | Fast, modern, AI-first news UX |
| Signal bar concept | The Verge | Live energy without visual noise |
| Source comparison tables | Politico, AllSides | Side-by-side editorial comparison |

**Avoid referencing:**
- BuzzFeed, HuffPost — high-clickbait visual energy
- Twitter/X — real-time chaos aesthetic
- Any app with auto-playing videos in feed

---

## 17. Pre-Delivery Checklist for Builder

Before marking any screen complete:

- [ ] Newsreader used for all headlines, Inter for all UI/body text
- [ ] `--color-primary` red used ONLY for: logo, breaking badge, signal bar, active nav, critical alerts
- [ ] Light mode text contrast ≥ 4.5:1 (check `--color-ink-muted` on `--color-surface`)
- [ ] Dark mode fully specified (not just `filter: invert`)
- [ ] All clickable elements: `cursor: pointer`, visible focus ring
- [ ] Hover transitions: 150–200ms, `ease-out`
- [ ] Touch targets: minimum 44×44px on mobile
- [ ] No horizontal scroll on any mobile viewport ≥ 375px
- [ ] Skeleton loading on every async data fetch
- [ ] `prefers-reduced-motion` removes animations
- [ ] Category label always paired with color (not color alone)
- [ ] Signal bar present on every page, behavior correct per page type
- [ ] AI summary label `✦ AI Summary` on all AI-generated content
- [ ] Source URLs always visible and open in new tab
- [ ] Bookmarks work offline (optimistic UI update before API response)