/**
 * icons.ts — NewsIQ Brand Icon SVG Data
 *
 * Raw SVG path data for the lightning bolt + embedded "N" brand icon.
 * Faithfully reproduced from the official branding reference.
 *
 * The icon is designed on a 64×64 viewBox for crisp rendering at all sizes.
 * Use these paths in:
 *   - <BrandLogo> component
 *   - Favicon generators (icon.tsx, apple-icon.tsx)
 *   - PWA icon routes
 *   - Static SVG exports
 */

/** ViewBox dimensions for the brand icon */
export const ICON_VIEWBOX = "0 0 64 64";
export const ICON_VIEWBOX_SIZE = 64;

/**
 * Lightning bolt outer shape path.
 * Red bolt silhouette — the primary visual element.
 */
export const BOLT_PATH =
  "M38 2L14 34h14l-6 28L46 30H32l6-28z";

/**
 * Embedded "N" letter path inside the bolt.
 * Positioned in the center-lower area of the bolt for visual balance.
 */
export const N_PATH =
  "M24 28h4l4 8V28h4v16h-4l-4-8v8h-4V28z";

/**
 * Combined icon as a complete SVG string.
 * Use for static file generation and inline rendering.
 */
export function getBrandIconSVG(options?: {
  /** Icon fill color. Defaults to brand red */
  color?: string;
  /** "N" letter color. Defaults to white */
  nColor?: string;
  /** Size in px. Defaults to 64 */
  size?: number;
}): string {
  const color = options?.color ?? "#EF4444";
  const nColor = options?.nColor ?? "#FFFFFF";
  const size = options?.size ?? 64;

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${ICON_VIEWBOX}" width="${size}" height="${size}" fill="none">
  <path d="${BOLT_PATH}" fill="${color}"/>
  <path d="${N_PATH}" fill="${nColor}"/>
</svg>`;
}

/**
 * App icon SVG — rounded square with brand icon centered.
 * Used for favicons, PWA icons, and app store icons.
 */
export function getBrandAppIconSVG(options?: {
  /** Background fill. Defaults to brand red */
  bgColor?: string;
  /** Icon fill. Defaults to white */
  iconColor?: string;
  /** "N" letter color. Defaults to brand red */
  nColor?: string;
  /** Size in px */
  size?: number;
  /** Corner radius ratio (0-1). Defaults to 0.22 */
  radiusRatio?: number;
}): string {
  const bg = options?.bgColor ?? "#EF4444";
  const icon = options?.iconColor ?? "#FFFFFF";
  const nCol = options?.nColor ?? "#EF4444";
  const size = options?.size ?? 512;
  const rr = options?.radiusRatio ?? 0.22;
  const r = Math.round(size * rr);
  // Scale the 64-unit icon into the center of the square with padding
  const padding = Math.round(size * 0.15);
  const innerSize = size - padding * 2;
  const scale = innerSize / ICON_VIEWBOX_SIZE;

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}">
  <rect width="${size}" height="${size}" rx="${r}" fill="${bg}"/>
  <g transform="translate(${padding}, ${padding}) scale(${scale})">
    <path d="${BOLT_PATH}" fill="${icon}"/>
    <path d="${N_PATH}" fill="${nCol}"/>
  </g>
</svg>`;
}
