/**
 * branding/index.ts — NewsIQ Centralized Brand Design System
 *
 * All brand assets, tokens, and components exported from one module.
 * Import from "@/branding" — never reference brand files directly.
 *
 * Usage:
 *   import { BrandLogo, brandColors, brand } from "@/branding";
 */

// Design tokens
export { brandColors, brandCSSVars, type BrandColor } from "./colors";
export { brandFonts, brandWeights, logoSizes, type LogoSize } from "./typography";

// Brand metadata
export { brand } from "./metadata";

// Icon SVG data
export {
  ICON_VIEWBOX,
  ICON_VIEWBOX_SIZE,
  BOLT_PATH,
  N_PATH,
  getBrandIconSVG,
  getBrandAppIconSVG,
} from "./icons";

// React components
export {
  BrandLogo,
  type BrandLogoProps,
  type BrandLogoVariant,
  type BrandLogoTheme,
} from "./logo";
