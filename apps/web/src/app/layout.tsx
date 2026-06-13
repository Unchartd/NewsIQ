import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Newsreader } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  display: "swap",
  style: ["normal", "italic"],
  weight: ["400", "500", "600", "700"],
});

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
      className={`${inter.variable} ${jetbrainsMono.variable} ${newsreader.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-background text-foreground font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
