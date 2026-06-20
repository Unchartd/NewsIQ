# NewsIQ SEO Audit
**Date:** 2026-06-20  
**Auditor:** Principal SEO Engineering System  
**Scope:** Full technical SEO, AEO, GEO, LLMO, E-E-A-T audit

---

## Executive Summary

NewsIQ had critical SEO infrastructure gaps that rendered the platform largely invisible to search engines and AI systems. The audit identified 10 critical issues, 10 medium issues, and 5 minor issues. All critical and most high-priority issues have been resolved in this implementation cycle.

---

## 🔴 Critical Issues (All Resolved ✅)

| # | Issue | Page | Status |
|---|-------|------|--------|
| 1 | Landing page (`/`) was `"use client"` — zero server-side metadata | `/` | ✅ Fixed: Server wrapper + full metadata |
| 2 | No `robots.txt` — crawlers had no guidance | All | ✅ Fixed: `robots.ts` with 12 crawler rules |
| 3 | No `sitemap.xml` — pages not submitted to search engines | All | ✅ Fixed: Dynamic `sitemap.ts` + Google News sitemap |
| 4 | Category page was 100% CSR — no metadata, no schema | `/category/[slug]` | ✅ Fixed: Server wrapper + CollectionPage JSON-LD |
| 5 | Trending page was 100% CSR — no metadata | `/trending` | ✅ Fixed: Server wrapper + metadata |
| 6 | Search page was 100% CSR — no metadata | `/search` | ✅ Fixed: Server wrapper + metadata |
| 7 | Premium page was 100% CSR — no metadata | `/premium` | ✅ Fixed: Server wrapper + FAQ JSON-LD |
| 8 | Story JSON-LD was incomplete (missing author, image, keywords, BreadcrumbList, speakable) | `/story/[id]` | ✅ Fixed: Full `buildNewsArticleSchema()` |
| 9 | Root layout missing `metadataBase` — OG images broken | All | ✅ Fixed: `metadataBase: new URL(SITE_URL)` |
| 10 | No OG images on any page except stories | All | ✅ Fixed: Default `og-image.jpg` across all pages |

---

## 🟡 Medium Issues

| # | Issue | Status |
|---|-------|--------|
| 11 | Home feed title "Home Feed" — not keyword-rich | ✅ Fixed |
| 12 | No E-E-A-T pages (`/about`, `/methodology`, `/ai-transparency`, `/editorial-principles`) | ✅ Fixed |
| 13 | No `BreadcrumbList` on any page | ✅ Fixed: Story + Category + Trending + Topics |
| 14 | No `SearchAction` schema for Sitelinks search box | ✅ Fixed: `buildWebSiteSchema()` in root layout |
| 15 | Google Fonts render-blocking | ✅ Fixed: Migrated to `next/font/google` |
| 16 | No `manifest.json` / PWA metadata | ✅ Fixed: `/public/manifest.json` |
| 17 | Legal pages had no SEO metadata | ⚠️ Partially: X-Robots-Tag via headers (legal pages should be indexed selectively) |
| 18 | Auth/utility pages had no `noindex` | ✅ Fixed: `X-Robots-Tag: noindex` via `next.config.ts` |
| 19 | `next.config.ts` missing image optimization | ✅ Fixed: AVIF/WebP, remote patterns, device sizes |
| 20 | No `Organization` or `WebSite` schema at root | ✅ Fixed: Root layout global JSON-LD |

---

## 🟢 Minor Issues

| # | Issue | Status |
|---|-------|--------|
| 21 | `<h2>` inside trending cards (heading hierarchy) | ⚠️ Noted — should be reviewed per page |
| 22 | No `aria-label` on icon-only buttons | ⚠️ Ongoing — component-level accessibility pass needed |
| 23 | Story URLs use UUIDs (not human-readable slugs) | ⚠️ Deferred — requires backend URL migration |
| 24 | Missing ISO 8601 date validation | ✅ Fixed: `new Date(date).toISOString()` in JSON-LD factory |
| 25 | Missing `lang` attributes on multilingual content | ⚠️ Deferred |

---

## New Files Created

| File | Purpose |
|------|---------|
| `src/app/robots.ts` | Crawler policy: 12 user-agents with explicit allow/disallow |
| `src/app/sitemap.ts` | Dynamic sitemap: static routes + categories + recent stories |
| `src/app/news-sitemap.xml/route.ts` | Google News sitemap (last 2 days, `<news:news>` elements) |
| `src/lib/metadata.ts` | Centralized metadata factory |
| `src/lib/jsonld.ts` | JSON-LD schema factories (8 schema types) |
| `src/app/landing-client.tsx` | Landing page client component (extracted from page.tsx) |
| `src/app/category/[slug]/category-client.tsx` | Category UI client component |
| `src/app/trending/trending-client.tsx` | Trending UI client component |
| `src/app/search/search-client.tsx` | Search UI client component |
| `src/app/premium/premium-client.tsx` | Premium UI client component |
| `src/app/about/page.tsx` | E-E-A-T: About page |
| `src/app/editorial-principles/page.tsx` | E-E-A-T: Editorial principles |
| `src/app/methodology/page.tsx` | E-E-A-T: How AI works |
| `src/app/ai-transparency/page.tsx` | E-E-A-T: AI disclosure |
| `src/app/topics/page.tsx` | Content hub: All topic categories |
| `public/manifest.json` | PWA manifest (Google Discover eligibility) |
| `public/og-image.jpg` | Default OG image (1200×630) |

---

## Modified Files

| File | Changes |
|------|---------|
| `src/app/layout.tsx` | `next/font`, `metadataBase`, rich metadata, global JSON-LD, PWA support |
| `src/app/page.tsx` | Server wrapper with metadata + FAQ JSON-LD |
| `src/app/home/page.tsx` | Rich keyword metadata |
| `src/app/story/[storyId]/page.tsx` | `buildStoryMetadata()` + full `buildNewsArticleSchema()` + BreadcrumbList |
| `src/app/category/[slug]/page.tsx` | Server wrapper + `generateMetadata` + CollectionPage + BreadcrumbList |
| `src/app/trending/page.tsx` | Server wrapper + metadata + CollectionPage |
| `src/app/search/page.tsx` | Server wrapper + metadata + WebPage schema |
| `src/app/premium/page.tsx` | Server wrapper + metadata + FAQ JSON-LD |
| `next.config.ts` | Image optimization, security headers, X-Robots-Tag |

---

## Structured Data Inventory (Post-Implementation)

| Schema Type | Pages |
|------------|-------|
| `Organization` | Root layout (all pages), About |
| `WebSite` + `SearchAction` | Root layout (all pages) |
| `SoftwareApplication` | Root layout (all pages) |
| `NewsArticle` | `/story/[id]` |
| `BreadcrumbList` | `/story/[id]`, `/category/[slug]`, `/trending`, `/topics` |
| `CollectionPage` | `/category/[slug]`, `/trending`, `/topics` |
| `FAQPage` | `/` (landing), `/editorial-principles`, `/methodology`, `/ai-transparency`, `/premium` |
| `WebPage` | `/search`, `/about`, `/methodology`, `/ai-transparency` |

---

## Remaining Recommendations

### High Priority
1. **Add `/source-transparency` page** — list all indexed publishers with editorial ratings
2. **Story URL slugs** — migrate from UUID to `slug-title` format (backend change required)
3. **Google Search Console** — add verification token to `layout.tsx` once account is created
4. **Bing Webmaster Tools** — add verification token

### Medium Priority
5. **Image optimization** — ensure story images use `<Image>` component from next/image
6. **Sitemap submission** — manually submit both sitemaps to GSC and Bing after deployment
7. **Core Web Vitals** — measure LCP, CLS, INP after production deployment
8. **Font variable usage** — ensure CSS uses `--font-inter`, `--font-newsreader`, `--font-mono` variables

### Future Phases
9. **Knowledge graph pages** — `/entities/[name]` for people, orgs, events mentioned in stories
10. **Plausible/PostHog analytics** — add to layout for search console supplementary data
11. **Google Discover** — monitor once E-E-A-T pages are indexed
12. **Video sitemap** — if video content is added in future

---

## Verification Checklist

After deployment, verify:

```bash
# Robots.txt
curl https://newsiq.app/robots.txt

# Sitemap
curl https://newsiq.app/sitemap.xml

# News Sitemap  
curl https://newsiq.app/news-sitemap.xml

# OG Image
curl -I https://newsiq.app/og-image.jpg

# Manifest
curl https://newsiq.app/manifest.json
```

**Rich Results Test:**
- https://search.google.com/test/rich-results?url=https://newsiq.app/
- https://search.google.com/test/rich-results?url=https://newsiq.app/story/[any-story-id]

**OG Debugger:**
- https://www.opengraph.xyz/url/https%3A%2F%2Fnewsiq.app

**Schema Validator:**
- https://validator.schema.org/
