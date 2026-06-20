/**
 * jsonld.ts — Typed JSON-LD schema factories for NewsIQ
 *
 * All structured data should be built through these factories.
 * Schemas are validated against schema.org standards.
 *
 * References:
 *   https://schema.org/NewsArticle
 *   https://schema.org/Organization
 *   https://schema.org/WebSite
 *   https://developers.google.com/search/docs/appearance/structured-data/
 */

import { SITE_URL, SITE_NAME, DEFAULT_OG_IMAGE } from "@/lib/metadata";

// ─────────────────────────────────────────────────────────────
// Organization (root-level identity)
// ─────────────────────────────────────────────────────────────

export function buildOrganizationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: SITE_NAME,
    url: SITE_URL,
    logo: {
      "@type": "ImageObject",
      url: `${SITE_URL}/logo.png`,
      width: 512,
      height: 512,
    },
    description:
      "NewsIQ is an AI-powered news intelligence platform that clusters stories from dozens of sources, providing neutral headlines, AI summaries, source comparisons, and timelines.",
    foundingDate: "2024",
    sameAs: [
      "https://twitter.com/newsiq_app",
      // Add LinkedIn, GitHub, etc. as available
    ],
    contactPoint: {
      "@type": "ContactPoint",
      contactType: "customer support",
      email: "support@newsiq.app",
    },
  };
}

// ─────────────────────────────────────────────────────────────
// WebSite + SearchAction (enables Google Sitelinks search box)
// ─────────────────────────────────────────────────────────────

export function buildWebSiteSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    name: SITE_NAME,
    url: SITE_URL,
    description:
      "AI-powered news intelligence. Understand any story in under 30 seconds.",
    publisher: {
      "@id": `${SITE_URL}/#organization`,
    },
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${SITE_URL}/search?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
    inLanguage: "en-US",
  };
}

// ─────────────────────────────────────────────────────────────
// SoftwareApplication (for AI features recognition)
// ─────────────────────────────────────────────────────────────

export function buildSoftwareApplicationSchema() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${SITE_URL}/#app`,
    name: SITE_NAME,
    applicationCategory: "NewsApplication",
    operatingSystem: "Web",
    url: SITE_URL,
    description:
      "AI-powered news intelligence platform with multi-source story clustering, neutral headlines, timelines, and source comparison.",
    offers: [
      {
        "@type": "Offer",
        price: "0",
        priceCurrency: "INR",
        name: "Free",
      },
      {
        "@type": "Offer",
        price: "399",
        priceCurrency: "INR",
        name: "Pro",
        billingDuration: "P1M",
      },
    ],
    publisher: {
      "@id": `${SITE_URL}/#organization`,
    },
  };
}

// ─────────────────────────────────────────────────────────────
// NewsArticle (story pages)
// ─────────────────────────────────────────────────────────────

export function buildNewsArticleSchema(story: {
  id: string;
  headline: string;
  one_line_summary?: string;
  short_summary?: string;
  detailed_summary?: string;
  first_seen_at?: string;
  updated_at?: string;
  category?: { name: string; slug?: string } | null;
  tags?: string[];
  key_facts?: string[];
  entities?: Array<{ entity_type: string; entity_value: string }>;
  articles?: Array<{ url?: string; image_url?: string | null; source?: { name: string } }>;
  timeline?: Array<{ event_time: string; description: string }>;
}) {
  const url = `${SITE_URL}/story/${story.id}`;
  const ogImage =
    story.articles?.find((a) => a.image_url)?.image_url || DEFAULT_OG_IMAGE;

  const keywords = [
    ...(story.tags || []),
    story.category?.name || "",
    "AI news",
    "multi-source",
  ]
    .filter(Boolean)
    .join(", ");

  const hasPartElements: object[] = [];

  if (story.one_line_summary) {
    hasPartElements.push({
      "@type": "WebPageElement",
      "name": "One-line Summary",
      "description": "Factual single-sentence summary of the story.",
      "text": story.one_line_summary
    });
  }

  if (story.short_summary) {
    hasPartElements.push({
      "@type": "WebPageElement",
      "name": "Short Summary",
      "description": "Concise multi-sentence overview of the event.",
      "text": story.short_summary
    });
  }

  if (story.detailed_summary) {
    hasPartElements.push({
      "@type": "WebPageElement",
      "name": "Detailed Summary",
      "description": "Comprehensive multi-perspective summary of the event.",
      "text": story.detailed_summary
    });
  }

  if (story.key_facts && story.key_facts.length > 0) {
    hasPartElements.push({
      "@type": "ItemList",
      "name": "Key Facts",
      "description": "Consensus bullet points and facts verified across publishers.",
      "itemListElement": story.key_facts.map((fact, index) => ({
        "@type": "ListItem",
        "position": index + 1,
        "item": {
          "@type": "CreativeWork",
          "text": fact
        }
      }))
    });
  }

  return {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "@id": `${url}#article`,
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": url,
    },
    headline: story.headline,
    description: story.one_line_summary || story.short_summary || "",
    articleBody: story.detailed_summary || story.short_summary || "",
    keywords,
    datePublished: story.first_seen_at
      ? new Date(story.first_seen_at).toISOString()
      : undefined,
    dateModified: story.updated_at
      ? new Date(story.updated_at).toISOString()
      : undefined,
    articleSection: story.category?.name || "General",
    image: {
      "@type": "ImageObject",
      url: ogImage,
      width: 1200,
      height: 630,
      caption: story.headline,
    },
    author: {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: SITE_NAME,
      url: SITE_URL,
    },
    publisher: {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: SITE_NAME,
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}/logo.png`,
      },
    },
    isAccessibleForFree: true,
    isBasedOn: (story.articles || [])
      .filter((a) => a.url)
      .map((a) => ({
        "@type": "NewsArticle",
        url: a.url,
        publisher: a.source
          ? { "@type": "Organization", name: a.source.name }
          : undefined,
      })),
    // Speakable — helps voice assistants read the key content
    speakable: {
      "@type": "SpeakableSpecification",
      cssSelector: [".sd-head", ".sumblock", ".kf-list"],
    },
    // Mentions — entities for knowledge graph
    mentions: (story.entities || [])
      .slice(0, 10)
      .map((e) => ({
        "@type":
          e.entity_type === "PERSON"
            ? "Person"
            : e.entity_type === "ORG"
            ? "Organization"
            : e.entity_type === "LOCATION" || e.entity_type === "COUNTRY"
            ? "Place"
            : "Thing",
        name: e.entity_value,
      })),
    // hasPart structure
    ...(hasPartElements.length > 0 ? { hasPart: hasPartElements } : {})
  };
}

// ─────────────────────────────────────────────────────────────
// BreadcrumbList
// ─────────────────────────────────────────────────────────────

export function buildBreadcrumbSchema(
  items: Array<{ name: string; url: string }>
) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

// ─────────────────────────────────────────────────────────────
// FAQPage (landing page, methodology, etc.)
// ─────────────────────────────────────────────────────────────

export function buildFAQSchema(
  faqs: Array<{ question: string; answer: string }>
) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };
}

// ─────────────────────────────────────────────────────────────
// CollectionPage (category/topic pages)
// ─────────────────────────────────────────────────────────────

export function buildCollectionPageSchema(
  name: string,
  description: string,
  url: string
) {
  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "@id": `${url}#collection`,
    name,
    description,
    url,
    publisher: {
      "@id": `${SITE_URL}/#organization`,
    },
    inLanguage: "en-US",
  };
}

// ─────────────────────────────────────────────────────────────
// WebPage (generic pages: about, methodology, etc.)
// ─────────────────────────────────────────────────────────────

export function buildWebPageSchema(
  name: string,
  description: string,
  path: string
) {
  const url = `${SITE_URL}${path}`;
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": `${url}#webpage`,
    name,
    description,
    url,
    isPartOf: {
      "@id": `${SITE_URL}/#website`,
    },
    publisher: {
      "@id": `${SITE_URL}/#organization`,
    },
    inLanguage: "en-US",
  };
}

// ─────────────────────────────────────────────────────────────
// JsonLdScript component helper (returns serialized JSON string)
// ─────────────────────────────────────────────────────────────

export function serializeJsonLd(schema: object): string {
  return JSON.stringify(schema);
}

// ─────────────────────────────────────────────────────────────
// Story FAQ Schema (AEO/GEO/LLM Voice Search)
// ─────────────────────────────────────────────────────────────

export function buildStoryFAQSchema(story: {
  headline: string;
  short_summary?: string;
  key_facts?: string[];
  articles?: Array<{ source?: { name: string } }>;
  differences?: Array<{ source?: { name: string }; contradictions?: string | null }>;
}) {
  const sourcesText = (story.articles || [])
    .map((a) => a.source?.name)
    .filter((v, i, a) => v && a.indexOf(v) === i)
    .join(", ");

  const contradictionsList = (story.differences || [])
    .filter((d) => d.contradictions)
    .map((d) => `${d.source?.name}: ${d.contradictions}`)
    .join(" ");

  const faqs = [
    {
      question: `What is the story '${story.headline}' about?`,
      answer: story.short_summary || "An AI-summarized intelligence report on developing news.",
    },
  ];

  if (story.key_facts && story.key_facts.length > 0) {
    faqs.push({
      question: "What are the key facts of this event?",
      answer: `Key developments include: ${story.key_facts.join(" ")}`,
    });
  }

  if (sourcesText) {
    faqs.push({
      question: "Which publications covered this news story?",
      answer: `This story was covered and cross-referenced across multiple sources including ${sourcesText}.`,
    });
  }

  if (contradictionsList) {
    faqs.push({
      question: "Are there any conflicts or contradictions between reporting sources?",
      answer: `Yes, differences were noted in reporting: ${contradictionsList}`,
    });
  } else {
    faqs.push({
      question: "Do the sources agree on the details of this story?",
      answer: "The indexed news sources show a high level of factual alignment with no significant conflicts or contradictions reported.",
    });
  }

  return buildFAQSchema(faqs);
}

// ─────────────────────────────────────────────────────────────
// Source Coverage Schema (ItemList representation)
// ─────────────────────────────────────────────────────────────

export function buildSourceCoverageSchema(story: {
  headline: string;
  articles?: Array<{ url?: string; title?: string; source?: { name: string } }>;
}) {
  const articlesList = story.articles || [];

  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": `Source coverage for: ${story.headline}`,
    "description": "List of original publisher articles compiled for this intelligence report.",
    "numberOfItems": articlesList.length,
    "itemListElement": articlesList.map((art, index) => ({
      "@type": "ListItem",
      "position": index + 1,
      "item": {
        "@type": "NewsArticle",
        "url": art.url || "",
        "headline": art.title || "Original Reporting",
        "publisher": {
          "@type": "Organization",
          "name": art.source?.name || "News Publisher"
        }
      }
    }))
  };
}

// ─────────────────────────────────────────────────────────────
// Timeline Schema (Chronological ItemList of events)
// ─────────────────────────────────────────────────────────────

export function buildTimelineSchema(story: {
  headline: string;
  timeline?: Array<{ event_time: string; description: string }>;
}) {
  const timelineEvents = story.timeline || [];

  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": `Chronological timeline for: ${story.headline}`,
    "description": "Verified events structured sequentially as they unfolded over time.",
    "numberOfItems": timelineEvents.length,
    "itemListElement": timelineEvents.map((ev, index) => {
      const dateStr = ev.event_time ? new Date(ev.event_time).toISOString() : new Date().toISOString();
      return {
        "@type": "ListItem",
        "position": index + 1,
        "item": {
          "@type": "Event",
          "name": ev.description,
          "startDate": dateStr,
          "endDate": dateStr,
          "description": ev.description,
          "location": {
            "@type": "Place",
            "name": "Global / Virtual"
          }
        }
      };
    })
  };
}
