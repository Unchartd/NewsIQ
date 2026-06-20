import type { NextConfig } from "next";
import bundleAnalyzer from "@next/bundle-analyzer";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://newsiq.app";

const nextConfig: NextConfig = {
  // ── Performance ──────────────────────────────────────────────
  compress: true,
  poweredByHeader: false, // Remove X-Powered-By header (minor security + SEO)

  // ── Image Optimization ───────────────────────────────────────
  images: {
    formats: ["image/avif", "image/webp"],
    // Remote patterns for story images from news sources
    remotePatterns: [
      { protocol: "https", hostname: "**" }, // Allow all HTTPS image sources for news
    ],
    // Device sizes for responsive images
    deviceSizes: [640, 750, 828, 1080, 1200, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
    // Optimize images at edge
    minimumCacheTTL: 3600, // 1 hour
  },

  // ── HTTP Headers ─────────────────────────────────────────────
  async headers() {
    return [
      // Security + SEO headers for all routes
      {
        source: "/(.*)",
        headers: [
          // Prevent MIME sniffing
          { key: "X-Content-Type-Options", value: "nosniff" },
          // Prevent clickjacking
          { key: "X-Frame-Options", value: "DENY" },
          // Referrer policy (privacy + SEO)
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Permissions policy
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      // Cache static assets aggressively
      {
        source: "/(_next/static|favicon|og-image|logo|icon)(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
      // Allow all crawlers (no X-Robots-Tag restrictions on public pages)
      {
        source: "/(story|category|trending|search|about|methodology|editorial-principles|ai-transparency|source-transparency|topics)(.*)",
        headers: [
          {
            key: "X-Robots-Tag",
            value: "index, follow, max-image-preview:large, max-snippet:-1",
          },
        ],
      },
      // Prevent indexing of private/auth pages
      {
        source: "/(admin|auth|onboarding|settings|profile|notifications|bookmarks|digest|reset-password|verify-email)(.*)",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
  },

  // ── Redirects ────────────────────────────────────────────────
  async redirects() {
    return [
      // Ensure www → non-www canonical (if applicable)
      // Uncomment and update once DNS is confirmed:
      // {
      //   source: "/(.*)",
      //   has: [{ type: "host", value: "www.newsiq.app" }],
      //   destination: `https://newsiq.app/:path*`,
      //   permanent: true,
      // },
    ];
  },
};

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

export default withBundleAnalyzer(nextConfig);
