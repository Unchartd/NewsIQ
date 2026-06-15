import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: {
    default: "NewsIQ — AI News Intelligence Platform",
    template: "%s | NewsIQ",
  },
  description:
    "Understand any major story in under 30 seconds. AI-powered news clustering, multi-source comparison, and transparent summaries.",
  keywords: [
    "news",
    "AI",
    "intelligence",
    "aggregator",
    "summaries",
    "source comparison",
  ],
  authors: [{ name: "NewsIQ" }],
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "NewsIQ",
    title: "NewsIQ — AI News Intelligence Platform",
    description:
      "Understand any major story in under 30 seconds with AI-powered source transparency.",
  },
  twitter: {
    card: "summary_large_image",
    title: "NewsIQ — AI News Intelligence Platform",
    description:
      "Understand any major story in under 30 seconds with AI-powered source transparency.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
      suppressHydrationWarning
      data-scroll-behavior="smooth"
    >
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Newsreader:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500;1,600;1,700&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
