import type { Metadata } from "next";
import Link from "next/link";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildFAQSchema, serializeJsonLd } from "@/lib/jsonld";

export const metadata: Metadata = buildPageMetadata(
  "Editorial Principles",
  "How NewsIQ selects sources, generates summaries, ensures neutrality, and handles corrections. Our commitment to journalistic standards and AI-assisted editorial quality.",
  "/editorial-principles",
  {
    keywords: [
      "NewsIQ editorial principles",
      "AI news editorial policy",
      "news neutrality",
      "source selection",
      "media bias",
      "fact-checking policy",
    ],
  }
);

const webPageSchema = buildWebPageSchema(
  "Editorial Principles — NewsIQ",
  "How NewsIQ selects sources, generates summaries, and ensures neutrality in AI-powered news coverage.",
  "/editorial-principles"
);

const FAQ_ITEMS = [
  {
    question: "How does NewsIQ ensure headline neutrality?",
    answer:
      "NewsIQ uses general-purpose large language models, instructed to rewrite headlines without evaluative language, emotional framing or partisan terms. Generated text is checked against the source articles before a story is published.",
  },
  {
    question: "How does NewsIQ select which news sources to index?",
    answer:
      "The feeds NewsIQ reads directly come from established news organisations with editorial teams and correction policies. To show how a story is covered elsewhere, NewsIQ also finds articles through news search, which can include a wider range of publishers.",
  },
  {
    question: "What happens when sources contradict each other?",
    answer:
      "When the Difference Engine detects factual contradictions between sources, we flag them explicitly in the story view. We do not adjudicate truth ourselves — we surface the contradiction and link to the primary sources so readers can evaluate evidence directly.",
  },
  {
    question: "How does NewsIQ handle corrections?",
    answer:
      "Story summaries are regenerated automatically as new coverage of a story arrives, so they can change over time. If you find an error in a NewsIQ summary, email hello.newsiq@gmail.com and we will correct it.",
  },
];

const faqSchema = buildFAQSchema(FAQ_ITEMS);

export default function EditorialPrinciplesPage() {
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

      <main id="main-content" className="min-h-screen bg-background">
        <section className="border-b border-border/50 bg-card/30">
          <div className="max-w-3xl mx-auto px-6 py-16">
            <div className="flex items-center gap-2 mb-4">
              <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Home</Link>
              <span className="text-muted-foreground/50">/</span>
              <Link href="/about" className="text-sm text-muted-foreground hover:text-foreground transition-colors">About</Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-sm text-foreground font-medium">Editorial Principles</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4" style={{ fontFamily: "var(--font-newsreader)" }}>
              Editorial Principles
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed">
              How we select sources, generate summaries, enforce neutrality,
              and maintain accountability as an AI-assisted news platform.
            </p>
          </div>
        </section>

        <div className="max-w-3xl mx-auto px-6 py-12 space-y-12">
          <section>
            <h2 className="text-2xl font-bold mb-4">Source Selection</h2>
            <p className="text-muted-foreground leading-relaxed">
              NewsIQ indexes content only from publishers that meet our
              quality threshold:
            </p>
            <ul className="mt-4 space-y-2 text-muted-foreground">
              <li className="flex gap-2"><span className="text-primary">✓</span> Established editorial teams with named mastheads</li>
              <li className="flex gap-2"><span className="text-primary">✓</span> Transparent ownership and funding disclosure</li>
              <li className="flex gap-2"><span className="text-primary">✓</span> Published correction and editorial policies</li>
              <li className="flex gap-2"><span className="text-primary">✓</span> Verifiable journalistic track record</li>
              <li className="flex gap-2"><span className="text-destructive">✗</span> Satire, opinion-only, or hyperpartisan outlets are excluded</li>
              <li className="flex gap-2"><span className="text-destructive">✗</span> Sites without editorial accountability structures</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Headline Generation</h2>
            <p className="text-muted-foreground leading-relaxed">
              All headlines shown on NewsIQ are AI-generated. Our model is
              instructed to:
            </p>
            <ul className="mt-4 space-y-2 text-muted-foreground">
              <li className="flex gap-2"><span className="text-primary">→</span> Use factual, descriptive language only</li>
              <li className="flex gap-2"><span className="text-primary">→</span> Remove evaluative adjectives (&quot;shocking&quot;, &quot;explosive&quot;, &quot;landmark&quot;)</li>
              <li className="flex gap-2"><span className="text-primary">→</span> Remove partisan framing from political stories</li>
              <li className="flex gap-2"><span className="text-primary">→</span> Reflect the consensus of source reporting, not one outlet&apos;s angle</li>
              <li className="flex gap-2"><span className="text-primary">→</span> Include key entities (who, what, where) in ≤12 words</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Summary Generation</h2>
            <p className="text-muted-foreground leading-relaxed">
              Summaries are grounded entirely in source article content. Our AI
              does not speculate, interpolate, or editorialize. Every claim in a
              summary can be traced to a linked source article. We surface
              three depths:
            </p>
            <div className="mt-4 space-y-3">
              {[
                { label: "One-line", desc: "Core event in one sentence (~15 words)" },
                { label: "Short", desc: "Who, what, where, why in 2–3 sentences" },
                { label: "Detailed", desc: "Full context, key facts, entities, and implications" },
              ].map((d) => (
                <div key={d.label} className="p-3 rounded-lg border border-border/50 bg-card/30">
                  <span className="font-semibold text-sm">{d.label}:</span>
                  <span className="text-sm text-muted-foreground ml-2">{d.desc}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Corrections Policy</h2>
            <p className="text-muted-foreground leading-relaxed">
              Summaries are regenerated automatically when new coverage of a story
              arrives, so they can change over time. If you spot a factual error
              in a NewsIQ summary, email hello.newsiq@gmail.com and we will fix it.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Frequently Asked Questions</h2>
            <div className="space-y-6">
              {FAQ_ITEMS.map((faq) => (
                <div key={faq.question} className="border-b border-border/50 pb-6">
                  <h3 className="font-semibold mb-2">{faq.question}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{faq.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="flex gap-4 flex-wrap pt-4">
            <Link href="/methodology" className="text-sm font-medium text-primary hover:underline">Our Methodology →</Link>
            <Link href="/ai-transparency" className="text-sm font-medium text-primary hover:underline">AI Transparency →</Link>
            <Link href="/source-transparency" className="text-sm font-medium text-primary hover:underline">Source Transparency →</Link>
          </div>
        </div>
      </main>
    </>
  );
}
