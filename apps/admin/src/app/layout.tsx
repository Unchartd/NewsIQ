import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import { BRANDING } from "@/branding/constants";

export const metadata: Metadata = {
  title: {
    default: `${BRANDING.NAME} Admin Console`,
    template: `%s | ${BRANDING.NAME} Admin`,
  },
  description:
    `AI Observability, Pipeline Tracing & Replay Engine — ${BRANDING.NAME} Admin Dashboard`,
  robots: "noindex, nofollow",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-background text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
