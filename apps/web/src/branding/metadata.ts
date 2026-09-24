/**
 * metadata.ts — NewsIQ Brand Metadata Constants
 *
 * Centralized brand identity strings used across SEO, structured data,
 * legal pages, and marketing content.
 */

export const brand = {
  /** Brand name */
  name: "NewsIQ",

  /** Brand tagline (from branding reference) */
  tagline: "Intelligence · Insight · Impact",

  /** Marketing description */
  description:
    "Understand any major story in under 30 seconds. AI-powered news clustering, multi-source comparison, neutral headlines, and transparent summaries.",

  /** Primary domain */
  domain: "newsiq.online",

  /** Full site URL */
  url: "https://newsiq.online",

  /** Legal entity name */
  legalName: "NewsIQ (operated by Zakaur Rahman)",

  /** Founding year */
  foundingYear: "2026",

  /** Social handles */
  social: {
    // No verified social accounts yet; add real handles only.
    twitter: "",
    supportEmail: "hello.newsiq@gmail.com",
    sourcesEmail: "hello.newsiq@gmail.com",
    eduEmail: "hello.newsiq@gmail.com",
  },

  /** Asset paths (relative to public/) */
  assets: {
    logo: "/brand/logo.svg",
    logoDark: "/brand/logo-dark.svg",
    icon: "/brand/icon.svg",
    iconRed: "/brand/icon-red.svg",
    favicon: "/brand/favicon.svg",
    ogImage: "/og-image.png",
  },
} as const;
