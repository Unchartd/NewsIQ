/**
 * typography.ts — NewsIQ Brand Typography Tokens
 *
 * Font families, weights, and sizes for brand elements.
 */

export const brandFonts = {
  /** Wordmark "News" — clean sans-serif */
  wordmarkPrimary: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",

  /** Wordmark "IQ" — editorial serif italic */
  wordmarkAccent: "'Newsreader', Georgia, 'Times New Roman', serif",

  /** Body text */
  body: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",

  /** Monospace / code */
  mono: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace",
} as const;

export const brandWeights = {
  wordmarkPrimary: 700,
  wordmarkAccent: 700,
  tagline: 500,
} as const;

/** Logo size presets (font-size in px for the wordmark text) */
export const logoSizes = {
  xs: { fontSize: 16, iconSize: 20, gap: 6 },
  sm: { fontSize: 20, iconSize: 24, gap: 7 },
  md: { fontSize: 28, iconSize: 32, gap: 8 },
  lg: { fontSize: 36, iconSize: 44, gap: 10 },
  xl: { fontSize: 48, iconSize: 56, gap: 12 },
} as const;

export type LogoSize = keyof typeof logoSizes;
