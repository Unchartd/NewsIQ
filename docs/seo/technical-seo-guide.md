# NewsIQ Technical SEO Guide
## Next.js 15 Engine Optimization & Crawling Systems

This guide documents the technical implementation of NewsIQ's search engine optimizations. It details how the Next.js 15 application is structured to ensure maximum indexability, crawl budget optimization, and instant schema validation.

---

## 1. The Server Wrapper Pattern

Next.js App Router requires metadata to be exported from Server Components. However, many interactive pages on NewsIQ require React state, query stores, and hooks (`"use client"`). To solve this, we implement the **Server Wrapper Pattern**:

1. **Client UI Component**: We extract the interactive UI code into a separate file (e.g., `trending-client.tsx`), marked with `"use client"`.
2. **Server Page Wrapper**: The main `page.tsx` remains a Server Component. It:
   - Fetches initial data server-side (for fast first paint and crawler readability).
   - Generates and exports dynamic metadata (`export const metadata` or `generateMetadata()`).
   - Injects page-specific JSON-LD schemas.
   - Invokes the client component, passing down the initial data as props.

* **Result**: Crawlers see fully-populated HTML, metadata, and JSON-LD on the first paint, while users enjoy seamless client-side reactivity.

---

## 2. Crawl & Indexing Infrastructure

We maintain three files in our App Router root that govern crawlers:

### A. robots.ts (`/src/app/robots.ts`)
Generates a dynamic `robots.txt` file containing 12 distinct crawler directives:
* **Allow**: Allows full access to public feeds, articles, category structures, and topics hubs.
* **Disallow**: Blocks crawlers from administrative, authentication, onboarding, settings, notifications, bookmarks, and private user feeds (digest) to conserve crawl budget.
* **Bot-Specific Overrides**: Configures custom access rules for `Googlebot`, `Googlebot-News`, `Bingbot`, `PerplexityBot`, `GPTBot` (OpenAI), `ClaudeBot` (Anthropic), and `CCBot` (Common Crawl).

### B. sitemap.ts (`/src/app/sitemap.ts`)
Generates a standard dynamic `sitemap.xml`:
* Feeds static pages (`/`, `/about`, `/trending`, `/premium`, etc.) with daily/weekly change frequencies.
* Pulls category listings from the database registry.
* Fetches the 100 most recent story IDs dynamically from the API to guarantee discovery of fresh content.

### C. News Sitemap (`/src/app/news-sitemap.xml/route.ts`)
A dedicated XML endpoint for Google News indexing:
* Google News requires articles to be published within the last 48 hours.
* The endpoint fetches stories from the last 2 days.
* Outputs raw XML with appropriate namespaces:
  ```xml
  <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
    <url>
      <loc>https://newsiq.app/story/uuid</loc>
      <news:news>
        <news:publication>
          <news:name>NewsIQ</news:name>
          <news:language>en</news:language>
        </news:publication>
        <news:publication_date>ISO-TIMESTAMP</news:publication_date>
        <news:title>Story Headline</news:title>
      </news:news>
    </url>
  </urlset>
  ```

---

## 3. Headers and Security Config (`next.config.ts`)

Our Next.js configuration is hardened for technical performance and search compliance:

1. **X-Robots-Tag: noindex**: We inject HTTP headers on utility and auth pages (like `/login`, `/settings`, `/admin`) to force search engines to ignore them, even if they bypass robots.txt.
2. **Content Security Policy (CSP)**: Injects robust security headers that block script injection attacks while allowing verified scripts (like analytics and UI utilities).
3. **HTTP Strict Transport Security (HSTS)**: Forces all traffic over HTTPS, an essential Core Web Vital and Google ranking signal.
4. **Powered-By Header**: Removed (`poweredByHeader: false`) to avoid disclosing server signatures for security.

---

## 4. Performance & Core Web Vitals Optimization

* **Image Optimization**: `next.config.ts` is configured to output `avif` and `webp` formats. It defines strict remote patterns for news sources, allowing our Next.js Image component to resize and optimize third-party media on-the-fly, reducing Largest Contentful Paint (LCP).
* **Font Loading**: Standard Google Fonts `<link>` tags block rendering, causing Cumulative Layout Shift (CLS). We replaced them with Next.js integrated font loader (`next/font/google`), utilizing:
  - `Inter` for general branding and UI.
  - `Newsreader` for serif headlines.
  - Both load with `display: 'swap'` to guarantee instant text display using system fallbacks during font fetching.
