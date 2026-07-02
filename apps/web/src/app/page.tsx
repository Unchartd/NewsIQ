/**
 * Landing page — server component wrapper.
 *
 * This file MUST remain a server component (no "use client") so that
 * Next.js can export `metadata` for SSR and crawler visibility.
 *
 * The actual interactive UI is in landing-client.tsx.
 */

import type { Metadata } from "next";
import { LandingClientPage } from "./landing-client";
import { buildFAQSchema, buildWebPageSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL, SITE_NAME } from "@/lib/metadata";

export const metadata: Metadata = {
  title: "Understand the Story, Not Just the Headlines",
  description:
    "NewsIQ transforms dozens of articles into one clear story — AI summaries, source comparisons, timelines, and transparent publisher links. Free to use.",
  alternates: {
    canonical: SITE_URL,
  },
  openGraph: {
    type: "website",
    url: SITE_URL,
    title: `${SITE_NAME} — Understand the Story, Not Just the Headlines`,
    description:
      "AI-powered news intelligence. Neutral headlines, multi-source comparison, timelines, and fact extraction. Updated every 5 minutes.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "NewsIQ — AI News Intelligence Platform",
      },
    ],
  },
  keywords: [
    "AI news platform",
    "news intelligence",
    "multi-source news",
    "neutral headlines",
    "AI news summary",
    "fact-checked news",
    "Google News alternative",
    "Perplexity for news",
    "news aggregator India",
  ],
};

// FAQ data — matches the FAQ accordion on the landing page
const LANDING_FAQS = [
  {
    question: "What is NewsIQ?",
    answer:
      "NewsIQ is an AI-powered news intelligence platform that clusters stories from dozens of sources into a single, clear summary. It provides neutral headlines, AI summaries, source comparisons, timelines, and transparent publisher attribution.",
  },
  {
    question: "How does NewsIQ work?",
    answer:
      "NewsIQ continuously ingests articles from trusted news publishers worldwide. Our AI clusters related articles into a single story, generates neutral headlines, extracts key facts, builds timelines, and shows how each source covered the story differently.",
  },
  {
    question: "Is NewsIQ free to use?",
    answer:
      "Yes. NewsIQ is free for casual readers with access to 10 stories per day. The Pro plan (₹399/month) unlocks unlimited stories, source comparison, personalised feed, Difference Engine, and daily digest.",
  },
  {
    question: "How does NewsIQ ensure neutrality?",
    answer:
      "NewsIQ uses AI to rewrite headlines removing loaded language. We show you how multiple sources covered the same event, highlight where sources agree, conflict, or omit information. Our editorial principles are documented openly.",
  },
  {
    question: "Which news sources does NewsIQ use?",
    answer:
      "NewsIQ indexes articles from trusted publishers including Reuters, Associated Press, BBC, CNN, Bloomberg, The Guardian, NDTV, Times of India, Indian Express, Hindustan Times, Al Jazeera, Financial Times, and more.",
  },
  {
    question: "Does NewsIQ use AI to write articles?",
    answer:
      "No. NewsIQ does not generate or fabricate news. Our AI summarises, clusters, and compares articles written by professional journalists. All summaries are grounded in original source articles, and publisher links are always visible.",
  },
];

const faqSchema = buildFAQSchema(LANDING_FAQS);
const webPageSchema = buildWebPageSchema(
  `${SITE_NAME} — AI News Intelligence Platform`,
  "Understand any major story in under 30 seconds with AI-powered source transparency.",
  "/"
);

export default function LandingPage() {
  return (
    <>
      {/* FAQ structured data for People Also Ask and voice assistants */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(faqSchema) }}
      />
      {/* WebPage schema for knowledge graph */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(webPageSchema) }}
      />
      <LandingClientPage />
    </>
  );
}
