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
  legalName: "NewsIQ Technologies Private Limited",

  /** Founding year */
  foundingYear: "2024",

  /** Social handles */
  social: {
    twitter: "@newsiq_online",
    supportEmail: "support@newsiq.online",
    sourcesEmail: "sources@newsiq.in",
    eduEmail: "edu@newsiq.in",
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
