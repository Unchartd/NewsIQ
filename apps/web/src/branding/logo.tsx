/**
 * logo.tsx — NewsIQ Brand Logo Component
 *
 * Centralized logo component rendering the official branding:
 *   - Red lightning bolt icon with embedded "N"
 *   - "News" in bold sans-serif + "IQ" in italic serif (brand red)
 *
 * Usage:
 *   <BrandLogo />                          // Full logo, auto theme, md size
 *   <BrandLogo variant="icon" size="sm" /> // Icon only
 *   <BrandLogo variant="wordmark" />       // Text only
 */

import React from "react";
import { brandColors } from "./colors";
import { brandFonts, brandWeights, logoSizes, type LogoSize } from "./typography";
import { BOLT_PATH, N_PATH, ICON_VIEWBOX } from "./icons";

export type BrandLogoVariant = "full" | "icon" | "wordmark";
export type BrandLogoTheme = "light" | "dark" | "auto";

export interface BrandLogoProps {
  /** Which parts to render */
  variant?: BrandLogoVariant;
  /** Color scheme */
  theme?: BrandLogoTheme;
  /** Preset size */
  size?: LogoSize;
  /** Additional CSS class */
  className?: string;
  /** Override styles */
  style?: React.CSSProperties;
}

/**
 * The lightning bolt + "N" icon as an inline SVG.
 */
function BoltIcon({ size, color }: { size: number; color: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={ICON_VIEWBOX}
      width={size}
      height={size}
      fill="none"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <path d={BOLT_PATH} fill={color} />
      <path d={N_PATH} fill="#FFFFFF" />
    </svg>
  );
}

/**
 * "News" + "IQ" wordmark text.
 */
function Wordmark({
  fontSize,
  newsColor,
}: {
  fontSize: number;
  newsColor: string;
}) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "baseline",
        lineHeight: 1,
        letterSpacing: "-0.02em",
        userSelect: "none",
      }}
    >
      <span
        style={{
          fontFamily: brandFonts.wordmarkPrimary,
          fontWeight: brandWeights.wordmarkPrimary,
          fontSize,
          color: newsColor,
        }}
      >
        News
      </span>
      <span
        style={{
          fontFamily: brandFonts.wordmarkAccent,
          fontWeight: brandWeights.wordmarkAccent,
          fontStyle: "italic",
          fontSize,
          color: brandColors.primary,
        }}
      >
        IQ
      </span>
    </span>
  );
}

export function BrandLogo({
  variant = "full",
  theme = "auto",
  size = "md",
  className,
  style,
}: BrandLogoProps) {
  const sizeTokens = logoSizes[size];
  const newsColor =
    theme === "dark"
      ? brandColors.white
      : theme === "light"
        ? brandColors.dark
        : "var(--ink, #111827)";

  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: sizeTokens.gap,
        textDecoration: "none",
        ...style,
      }}
      aria-label="NewsIQ"
    >
      {variant !== "wordmark" && (
        <BoltIcon size={sizeTokens.iconSize} color={brandColors.primary} />
      )}
      {variant !== "icon" && (
        <Wordmark fontSize={sizeTokens.fontSize} newsColor={newsColor} />
      )}
    </span>
  );
}
