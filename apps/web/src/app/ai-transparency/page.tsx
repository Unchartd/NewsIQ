import type { Metadata } from "next";
import Link from "next/link";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildFAQSchema, serializeJsonLd } from "@/lib/jsonld";

export const metadata: Metadata = buildPageMetadata(
  "AI Transparency — How NewsIQ Uses Artificial Intelligence",
  "Full disclosure of how NewsIQ uses AI: what models we use, what we do not allow AI to do, how we handle errors, and the limitations of our system.",
  "/ai-transparency",
  {
    keywords: [
      "AI transparency",
      "NewsIQ AI",
      "AI limitations",
      "AI disclosure",
      "responsible AI news",
      "AI in journalism",
    ],
  }
);

const webPageSchema = buildWebPageSchema(
  "AI Transparency — NewsIQ",
  "How NewsIQ uses AI responsibly: capabilities, limitations, and safeguards.",
  "/ai-transparency"
);

const AI_FAQS = [
  {
    question: "Does NewsIQ use AI to write news articles?",
    answer:
      "No. NewsIQ never generates original news content. Our AI summarises, clusters, and compares articles written by professional journalists. Every summary is grounded in retrieved source articles and publisher links are always visible.",
  },
  {
    question: "Can NewsIQ AI make mistakes?",
    answer:
      "Yes. Like all AI systems, NewsIQ can produce incorrect summaries, miss context, or miscluster unrelated stories. We display confidence signals and always link to primary sources so readers can verify independently. If you find an error, please report it via the feedback button on any story.",
  },
  {
    question: "Does NewsIQ's AI have political bias?",
    answer:
      "We actively work to minimize political bias. Our models are instructed to avoid partisan framing and are evaluated against neutrality benchmarks. However, bias can exist in our training data and source selection. We publish our source list and editorial principles openly so readers can assess this.",
  },
  {
    question: "Does NewsIQ use AI-generated images?",
    answer:
      "No. All images displayed on NewsIQ are sourced directly from the publisher articles we index. We do not generate, edit, or alter images.",
  },
];

const faqSchema = buildFAQSchema(AI_FAQS);

export default function AITransparencyPage() {
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

      <main className="min-h-screen bg-background">
        <section className="border-b border-border/50 bg-card/30">
          <div className="max-w-3xl mx-auto px-6 py-16">
            <div className="flex items-center gap-2 mb-4">
              <Link href="/" className="text-sm text-muted-foreground hover:text-foreground transition-colors">Home</Link>
              <span className="text-muted-foreground/50">/</span>
              <Link href="/about" className="text-sm text-muted-foreground hover:text-foreground transition-colors">About</Link>
              <span className="text-muted-foreground/50">/</span>
              <span className="text-sm font-medium">AI Transparency</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4" style={{ fontFamily: "var(--font-newsreader)" }}>
              AI Transparency
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed">
              We believe people deserve to know exactly how AI is being used in
              their news experience. This page discloses everything.
            </p>
          </div>
        </section>

        <div className="max-w-3xl mx-auto px-6 py-12 space-y-12">

          <section>
            <h2 className="text-2xl font-bold mb-4">What AI Does on NewsIQ</h2>
            <div className="space-y-3">
              {[
                "Groups related articles from different publishers into story clusters",
                "Rewrites headlines to remove bias and sensationalism",
                "Generates one-line, short, and detailed summaries of each story",
                "Extracts key facts and named entities (people, places, organizations)",
                "Builds chronological timelines from multiple source articles",
                "Identifies what information each source emphasized, omitted, or contradicted",
                "Ranks and scores story relevance and trending velocity",
              ].map((item) => (
                <div key={item} className="flex gap-3 text-muted-foreground">
                  <span className="text-green-500 mt-0.5 font-bold">✓</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">What AI Does NOT Do on NewsIQ</h2>
            <div className="space-y-3">
              {[
                "Write or fabricate original news articles",
                "Generate or alter photographs or images",
                "Speculate about events beyond what sources report",
                "Make editorial judgements about political positions",
                "Recommend specific news sources as more credible than others",
                "Personalize stories in ways that create filter bubbles",
              ].map((item) => (
                <div key={item} className="flex gap-3 text-muted-foreground">
                  <span className="text-destructive mt-0.5 font-bold">✗</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Known Limitations</h2>
            <div className="space-y-4 text-muted-foreground">
              <p>
                <strong className="text-foreground">Hallucination risk:</strong> Large language models can occasionally
                produce summaries that misrepresent source content. We ground all
                outputs in retrieved article text, but this risk is non-zero. Always
                verify critical information against source articles.
              </p>
              <p>
                <strong className="text-foreground">Clustering errors:</strong> Very similar stories (e.g., two
                different elections in the same week) can occasionally be merged
                incorrectly. We display source article links so you can check.
              </p>
              <p>
                <strong className="text-foreground">Context window limits:</strong> Very long-running stories
                may have summaries that omit older context as the cluster grows.
                Timelines help address this for developing events.
              </p>
              <p>
                <strong className="text-foreground">Language coverage:</strong> Currently, NewsIQ summarises
                content in English only. Non-English articles are indexed for
                clustering metadata but not summarised in other languages yet.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">How to Report Errors</h2>
            <p className="text-muted-foreground leading-relaxed">
              Every story page has a feedback button. If you find an incorrect
              summary, misclustered stories, or misleading headlines, please use
              the report function. We review all reports and update our models
              accordingly.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Frequently Asked Questions</h2>
            <div className="space-y-6">
              {AI_FAQS.map((faq) => (
                <div key={faq.question} className="border-b border-border/50 pb-6">
                  <h3 className="font-semibold mb-2">{faq.question}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{faq.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="flex gap-4 flex-wrap pt-4">
            <Link href="/methodology" className="text-sm font-medium text-primary hover:underline">Our Methodology →</Link>
            <Link href="/editorial-principles" className="text-sm font-medium text-primary hover:underline">Editorial Principles →</Link>
            <Link href="/source-transparency" className="text-sm font-medium text-primary hover:underline">Source Transparency →</Link>
          </div>
        </div>
      </main>
    </>
  );
}
