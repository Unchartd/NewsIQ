import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://newsiq.app";

/**
 * robots.ts — Crawler policy for NewsIQ
 *
 * Strategy:
 * - Allow all major search engines full access to public content
 * - Explicitly allow AI crawlers (GPTBot, ClaudeBot, PerplexityBot, etc.)
 *   so NewsIQ appears in AI-powered search results
 * - Block auth, admin, and personal pages from indexing
 * - Reference both sitemaps (general + Google News)
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      // ── Default: allow all crawlers access to public content ──
      {
        userAgent: "*",
        allow: ["/", "/story/", "/category/", "/trending/", "/search/", "/premium/", "/about/", "/editorial-principles/", "/methodology/", "/ai-transparency/", "/source-transparency/", "/topics/"],
        disallow: [
          "/admin/",
          "/api/",
          "/auth/",
          "/onboarding/",
          "/reset-password/",
          "/verify-email/",
          "/settings/",
          "/notifications/",
          "/bookmarks/",
          "/digest/",
          "/profile/",
          "/_next/",
        ],
      },

      // ── Google Search ──
      {
        userAgent: "Googlebot",
        allow: ["/"],
        disallow: ["/admin/", "/api/", "/auth/", "/onboarding/", "/reset-password/", "/verify-email/", "/settings/", "/notifications/", "/bookmarks/", "/digest/", "/profile/"],
      },

      // ── Google News crawler — focus on story content ──
      {
        userAgent: "Googlebot-News",
        allow: ["/story/", "/category/", "/trending/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Bing ──
      {
        userAgent: "Bingbot",
        allow: ["/"],
        disallow: ["/admin/", "/api/", "/auth/", "/onboarding/", "/reset-password/", "/verify-email/", "/settings/", "/notifications/", "/bookmarks/", "/digest/", "/profile/"],
      },

      // ── DuckDuckGo ──
      {
        userAgent: "DuckDuckBot",
        allow: ["/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Perplexity AI ──
      {
        userAgent: "PerplexityBot",
        allow: ["/", "/story/", "/category/", "/trending/", "/about/", "/methodology/", "/ai-transparency/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── OpenAI / ChatGPT ──
      {
        userAgent: "GPTBot",
        allow: ["/", "/story/", "/category/", "/trending/", "/about/", "/methodology/", "/ai-transparency/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Anthropic Claude ──
      {
        userAgent: "ClaudeBot",
        allow: ["/", "/story/", "/category/", "/trending/", "/about/", "/methodology/", "/ai-transparency/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Apple (Siri, Spotlight) ──
      {
        userAgent: "Applebot",
        allow: ["/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Amazon Alexa ──
      {
        userAgent: "Amazonbot",
        allow: ["/", "/story/", "/category/", "/about/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Common Crawl (used by many AI training datasets) ──
      {
        userAgent: "CCBot",
        allow: ["/", "/story/", "/category/", "/trending/", "/about/", "/methodology/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Meta AI ──
      {
        userAgent: "FacebookBot",
        allow: ["/", "/story/", "/category/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },

      // ── Microsoft Copilot / Bing Chat ──
      {
        userAgent: "OAI-SearchBot",
        allow: ["/", "/story/", "/category/", "/trending/"],
        disallow: ["/admin/", "/api/", "/auth/"],
      },
    ],

    sitemap: [
      `${SITE_URL}/sitemap.xml`,
      `${SITE_URL}/news-sitemap.xml`,
    ],

    host: SITE_URL,
  };
}
