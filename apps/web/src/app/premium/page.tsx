import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildFAQSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL, SITE_NAME } from "@/lib/metadata";
import PremiumPage from "./premium-client";

export const metadata: Metadata = buildPageMetadata(
  "NewsIQ Pro — Upgrade Your News Intelligence",
  "Unlock unlimited stories, source comparison, Difference Engine, personalised feed, and AI-powered features. NewsIQ Pro from ₹399/month.",
  "/premium",
  {
    keywords: [
      "NewsIQ Pro",
      "NewsIQ subscription",
      "AI news subscription",
      "premium news app",
      "news intelligence subscription",
    ],
  }
);

const webPageSchema = buildWebPageSchema(
  `${SITE_NAME} Pro — Upgrade Plans`,
  "Unlock the full NewsIQ intelligence layer with Pro or Enterprise.",
  "/premium"
);

const PRICING_FAQS = [
  {
    question: "What is included in the NewsIQ Free plan?",
    answer:
      "The free plan includes up to 10 stories per day, 1-line AI summaries, and access to the trending feed. No credit card required.",
  },
  {
    question: "What does NewsIQ Pro include?",
    answer:
      "NewsIQ Pro (₹399/month) includes unlimited stories, all 3 summary depths (one-line, short, detailed), source comparison table, Difference Engine, personalised feed, daily digest, and ad-free reading.",
  },
  {
    question: "Is there a NewsIQ Enterprise plan?",
    answer:
      "Yes. Enterprise is custom-priced and includes everything in Pro plus REST API access, bulk story exports, advanced analytics, dedicated support, SLA guarantees, and custom integrations.",
  },
  {
    question: "Can I cancel my NewsIQ Pro subscription?",
    answer:
      "Yes. You can cancel anytime from your profile settings. Your Pro access continues until the end of your billing period.",
  },
];

const faqSchema = buildFAQSchema(PRICING_FAQS);

export default function PremiumServerPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(webPageSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(faqSchema) }}
      />
      <PremiumPage />
    </>
  );
}
