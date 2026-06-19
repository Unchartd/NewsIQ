import type { Metadata } from "next";
import Link from "next/link";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildOrganizationSchema, serializeJsonLd } from "@/lib/jsonld";
import { SITE_URL } from "@/lib/metadata";

export const metadata: Metadata = buildPageMetadata(
  "About NewsIQ",
  "NewsIQ is an AI-powered news intelligence platform. Learn about our mission to make the news more understandable, transparent, and trustworthy.",
  "/about",
  {
    keywords: [
      "about NewsIQ",
      "NewsIQ mission",
      "AI news platform",
      "news intelligence",
      "transparent news",
    ],
  }
);

const webPageSchema = buildWebPageSchema(
  "About NewsIQ — AI News Intelligence Platform",
  "Our mission is to help people understand the world's most important stories through transparent, multi-source AI intelligence.",
  "/about"
);

const orgSchema = buildOrganizationSchema();

export default function AboutPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(webPageSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(orgSchema) }}
      />

      <main className="min-h-screen bg-background">
        {/* Hero */}
        <section className="border-b border-border/50 bg-card/30">
          <div className="max-w-3xl mx-auto px-6 py-16">
            <div className="flex items-center gap-2 mb-4">
              <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                Home
              </Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-sm text-foreground font-medium">About</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4" style={{ fontFamily: "var(--font-newsreader)" }}>
              About NewsIQ
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed">
              We built NewsIQ because the news is broken — not the journalists,
              but the delivery. Dozens of articles, thousands of words, and you
              still don&apos;t know what actually happened.
            </p>
          </div>
        </section>

        {/* Mission */}
        <section className="max-w-3xl mx-auto px-6 py-12 space-y-8">
          <div>
            <h2 className="text-2xl font-bold mb-4">Our Mission</h2>
            <p className="text-muted-foreground leading-relaxed text-lg">
              NewsIQ&apos;s mission is to help every person understand the world&apos;s
              most important stories clearly, quickly, and without bias.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-4">
              We believe that informed citizens make better decisions. We believe
              that understanding context matters more than consuming volume. And
              we believe that AI can make journalism more transparent, not less.
            </p>
          </div>

          <div>
            <h2 className="text-2xl font-bold mb-4">What NewsIQ Does</h2>
            <div className="grid gap-4">
              {[
                {
                  title: "Clusters stories from 200+ sources",
                  description:
                    "Our AI groups related articles from across the media landscape into a single, coherent story — so you see the full picture, not one outlet's framing.",
                },
                {
                  title: "Generates neutral headlines",
                  description:
                    "We rewrite headlines to remove partisan language, sensationalism, and emotional loading. You see what happened, not how one source wants you to feel about it.",
                },
                {
                  title: "Builds AI summaries at 3 depths",
                  description:
                    "One-line, short, and detailed summaries let you choose how deep you want to go — from a 10-second scan to a 2-minute comprehensive briefing.",
                },
                {
                  title: "Compares source coverage",
                  description:
                    "Our Difference Engine shows you what each source emphasized, omitted, or contradicted — giving you genuine media literacy at a glance.",
                },
                {
                  title: "Shows event timelines",
                  description:
                    "For developing stories, NewsIQ builds a chronological timeline of how events unfolded, sourced from published articles.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="p-4 rounded-xl border border-border/50 bg-card/50"
                >
                  <h3 className="font-semibold mb-1">{item.title}</h3>
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h2 className="text-2xl font-bold mb-4">Who We Are</h2>
            <p className="text-muted-foreground leading-relaxed">
              NewsIQ Technologies Private Limited is an Indian technology company
              building AI-native media tools. We are a team of engineers,
              journalists, and product designers who believe the next generation
              of news consumption should be smarter, not noisier.
            </p>
          </div>

          <div>
            <h2 className="text-2xl font-bold mb-4">Our Principles</h2>
            <ul className="space-y-3 text-muted-foreground">
              <li className="flex gap-3">
                <span className="text-primary font-bold mt-0.5">1.</span>
                <span><strong className="text-foreground">Transparency over opacity.</strong> We show our sources, our summaries, and our methodology. Nothing is hidden.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary font-bold mt-0.5">2.</span>
                <span><strong className="text-foreground">Accuracy over speed.</strong> We verify clustering quality and flag AI limitations prominently.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary font-bold mt-0.5">3.</span>
                <span><strong className="text-foreground">Neutrality as a practice.</strong> Our AI is trained to present facts, not frames. Political neutrality is non-negotiable.</span>
              </li>
              <li className="flex gap-3">
                <span className="text-primary font-bold mt-0.5">4.</span>
                <span><strong className="text-foreground">Publisher respect.</strong> We never reproduce full articles. We always link to originals. We support the journalism ecosystem.</span>
              </li>
            </ul>
          </div>

          <div className="flex gap-4 flex-wrap">
            <Link
              href="/editorial-principles"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              Editorial Principles →
            </Link>
            <Link
              href="/methodology"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              Our Methodology →
            </Link>
            <Link
              href="/ai-transparency"
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              AI Transparency →
            </Link>
          </div>
        </section>
      </main>
    </>
  );
}
