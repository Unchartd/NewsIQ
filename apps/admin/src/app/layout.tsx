import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Providers from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "NewsIQ Admin Console",
    template: "%s | NewsIQ Admin",
  },
  description:
    "AI Observability, Pipeline Tracing & Replay Engine — NewsIQ Admin Dashboard",
  robots: "noindex, nofollow",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased min-h-screen bg-[#0a0a0f] text-slate-200">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
