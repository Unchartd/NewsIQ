/**
 * colors.ts — NewsIQ Brand Color Palette
 *
 * Single source of truth for all brand colors.
 * Do NOT use raw hex values elsewhere — always reference these tokens.
 */

export const brandColors = {
  /** Primary brand red — lightning bolt, accents, CTAs */
  primary: "#EF4444",

  /** Primary hover/active state */
  primaryDark: "#C41E3A",

  /** Secondary brand color */
  secondary: "#8B1429",

  /** Primary light (background tints) */
  primaryLight: "#FEE2E2",

  /** Primary ghost (very subtle background) */
  primaryGhost: "rgba(239, 68, 68, 0.08)",

  /** Primary border (subtle borders) */
  primaryBorder: "rgba(239, 68, 68, 0.20)",

  /** Dark background / text */
  dark: "#111827",

  /** White */
  white: "#FFFFFF",

  /** Neutral gray */
  gray: "#6B7280",

  /** Light gray (muted backgrounds) */
  grayLight: "#F3F4F6",
} as const;

/** CSS custom property names mapped to brand tokens */
export const brandCSSVars = {
  primary: "--brand-primary",
  primaryDark: "--brand-primary-dark",
  dark: "--brand-dark",
  white: "--brand-white",
  gray: "--brand-gray",
} as const;

export type BrandColor = keyof typeof brandColors;
