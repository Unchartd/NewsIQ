import type { Metadata } from "next";
import Link from "next/link";
import { buildPageMetadata } from "@/lib/metadata";
import {
  buildCollectionPageSchema,
  buildBreadcrumbSchema,
  serializeJsonLd,
} from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata(
  "News Topics & Categories",
  "Browse all news topics on NewsIQ: Technology, Politics, Business, Sports, Science, Health, Environment, India, World, Finance, Entertainment, and Education. AI-summarized from multiple sources.",
  "/topics",
  {
    keywords: [
      "news topics",
      "news categories",
      "technology news",
      "politics news",
      "business news",
      "sports news",
      "AI news categories",
      "NewsIQ topics",
    ],
  }
);

const TOPICS = [
  {
    slug: "technology",
    name: "Technology",
    icon: "💻",
    description:
      "AI, startups, gadgets, software, Big Tech, and the future of computing.",
    featured: ["OpenAI", "Google", "Apple", "Meta", "Startups", "Cybersecurity"],
  },
  {
    slug: "politics",
    name: "Politics",
    icon: "🏛️",
    description:
      "Government policy, elections, diplomacy, and political developments worldwide.",
    featured: ["India Politics", "US Politics", "UK Politics", "EU Policy", "Elections"],
  },
  {
    slug: "business",
    name: "Business",
    icon: "📈",
    description:
      "Corporate news, markets, mergers, earnings, and economic developments.",
    featured: ["Markets", "Corporate", "Mergers & Acquisitions", "Startups", "IPO"],
  },
  {
    slug: "sports",
    name: "Sports",
    icon: "⚽",
    description:
      "Cricket, football, tennis, Olympics, and all major sporting events.",
    featured: ["Cricket", "Football", "IPL", "Formula 1", "Tennis", "Olympics"],
  },
  {
    slug: "science",
    name: "Science",
    icon: "🔬",
    description:
      "Research, discoveries, space exploration, and scientific breakthroughs.",
    featured: ["Space", "Climate Science", "Medicine", "Physics", "Biology"],
  },
  {
    slug: "health",
    name: "Health",
    icon: "🏥",
    description:
      "Medicine, public health, nutrition, mental health, and medical research.",
    featured: ["Public Health", "Mental Health", "Medical Research", "Nutrition"],
  },
  {
    slug: "world",
    name: "World",
    icon: "🌍",
    description:
      "International news, conflicts, diplomacy, and global affairs.",
    featured: ["Middle East", "Ukraine", "Asia Pacific", "Africa", "Americas"],
  },
  {
    slug: "india",
    name: "India",
    icon: "🇮🇳",
    description:
      "Indian news: politics, economy, society, culture, and regional developments.",
    featured: ["Delhi", "Mumbai", "Bengaluru", "Economy", "Culture", "Regional"],
  },
  {
    slug: "business",
    name: "Finance",
    icon: "💰",
    description:
      "Stock markets, banking, cryptocurrency, RBI policy, and personal finance.",
    featured: ["Stock Market", "RBI", "Cryptocurrency", "Banking", "Mutual Funds"],
  },
  {
    slug: "environment",
    name: "Environment",
    icon: "🌿",
    description:
      "Climate change, conservation, pollution, renewable energy, and sustainability.",
    featured: ["Climate Change", "Renewable Energy", "Conservation", "Pollution"],
  },
  {
    slug: "entertainment",
    name: "Entertainment",
    icon: "🎬",
    description:
      "Bollywood, Hollywood, OTT, music, and celebrity news.",
    featured: ["Bollywood", "Hollywood", "OTT", "Music", "Awards"],
  },
  {
    slug: "education",
    name: "Education",
    icon: "📚",
    description:
      "Schools, universities, policy, exams, and education reform.",
    featured: ["CBSE", "JEE", "NEET", "Universities", "EdTech", "Policy"],
  },
];

const collectionSchema = buildCollectionPageSchema(
  "News Topics — NewsIQ",
  "Browse all AI-summarized news categories on NewsIQ.",
  `${SITE_URL}/topics`
);

const breadcrumbSchema = buildBreadcrumbSchema([
  { name: "Home", url: SITE_URL },
  { name: "Topics", url: `${SITE_URL}/topics` },
]);

export default function TopicsPage() {
  // Deduplicate slugs
  const uniqueTopics = TOPICS.filter(
    (t, i, arr) => arr.findIndex((x) => x.slug === t.slug) === i
  );

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(collectionSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(breadcrumbSchema) }}
      />

      <main className="min-h-screen bg-background">
        <section className="border-b border-border/50 bg-card/30">
          <div className="max-w-4xl mx-auto px-6 py-12">
            <div className="flex items-center gap-2 mb-4">
              <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Home
              </Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-sm font-medium">Topics</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight mb-2">
              Browse by Topic
            </h1>
            <p className="text-muted-foreground">
              AI-summarized news from 200+ publishers, organized by category.
            </p>
          </div>
        </section>

        <div className="max-w-4xl mx-auto px-6 py-10">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {TOPICS.map((topic) => (
              <Link
                key={`${topic.slug}-${topic.name}`}
                href={`/category/${topic.slug}`}
                className="group block p-5 rounded-xl border border-border/50 bg-card/30 hover:bg-card hover:border-primary/30 transition-all duration-200"
              >
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-2xl" role="img" aria-label={topic.name}>
                    {topic.icon}
                  </span>
                  <h2 className="font-semibold text-lg group-hover:text-primary transition-colors">
                    {topic.name}
                  </h2>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                  {topic.description}
                </p>
                <div className="flex flex-wrap gap-1">
                  {topic.featured.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-0.5 rounded-full bg-muted/60 text-muted-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </Link>
            ))}
          </div>

          {/* Internal links to E-E-A-T pages */}
          <div className="mt-12 pt-8 border-t border-border/50">
            <h2 className="text-lg font-semibold mb-4">About NewsIQ</h2>
            <div className="flex flex-wrap gap-4">
              <Link href="/about" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                About us
              </Link>
              <Link href="/editorial-principles" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                Editorial principles
              </Link>
              <Link href="/methodology" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                How it works
              </Link>
              <Link href="/ai-transparency" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                AI transparency
              </Link>
              <Link href="/trending" className="text-sm text-muted-foreground hover:text-primary transition-colors">
                Trending stories
              </Link>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
