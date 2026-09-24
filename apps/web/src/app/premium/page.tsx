import type { Metadata } from "next";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildFAQSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL, SITE_NAME } from "@/lib/metadata";
import PremiumPage from "./premium-client";

export const metadata: Metadata = buildPageMetadata(
  "NewsIQ Pro — Upgrade Your News Intelligence",
  "Unlock unlimited stories, source comparison, Difference Engine, personalised feed, and AI-powered features. NewsIQ Pro is coming soon; everything is free during early access.",
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
      "During early access, every NewsIQ feature is free with no daily limits and no credit card. When paid plans launch, a free plan will remain.",
  },
  {
    question: "What does NewsIQ Pro include?",
    answer:
      "NewsIQ Pro (coming soon, planned at ₹399/month) will include unlimited stories, all 3 summary depths (one-line, short, detailed), source comparison table, Difference Engine, personalised feed, daily digest, and ad-free reading.",
  },
  {
    question: "Is there a NewsIQ Enterprise plan?",
    answer:
      "An Enterprise plan for newsrooms and organisations is planned. If you are interested, use Get in touch on this page and we will reply by email.",
  },
  {
    question: "Can I cancel my NewsIQ Pro subscription?",
    answer:
      "Paid plans are not live yet, so there is nothing to cancel. When they launch, you will be able to cancel at any time, and the full terms will be published before anyone can subscribe.",
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
