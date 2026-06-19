import type { Metadata } from "next";
import Link from "next/link";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildFAQSchema, serializeJsonLd } from "@/lib/jsonld";

export const metadata: Metadata = buildPageMetadata(
  "NewsIQ Methodology — How AI News Clustering Works",
  "Technical explanation of how NewsIQ clusters news stories from multiple sources, generates neutral summaries, and builds timelines using AI and NLP.",
  "/methodology",
  {
    keywords: [
      "NewsIQ methodology",
      "AI news clustering",
      "NLP news analysis",
      "how AI summarizes news",
      "news deduplication",
      "semantic clustering",
    ],
  }
);

const webPageSchema = buildWebPageSchema(
  "NewsIQ Methodology — AI News Clustering",
  "How NewsIQ uses AI to cluster, summarise, and compare news stories from 200+ publishers.",
  "/methodology"
);

const METHODOLOGY_FAQS = [
  {
    question: "How does NewsIQ cluster related news articles?",
    answer:
      "NewsIQ uses a combination of semantic embedding similarity, named entity overlap, and topic modeling to group articles about the same real-world event into a single story cluster. Articles published within a rolling time window are scored for relatedness and merged when the similarity score exceeds our threshold.",
  },
  {
    question: "How accurate is the NewsIQ AI clustering?",
    answer:
      "Our internal evaluation shows 98% clustering accuracy on held-out test sets of major news events. False positives (wrongly merging unrelated stories) are rare due to our conservative similarity threshold. False negatives (missing related articles) are addressed by the continuous ingestion cycle.",
  },
  {
    question: "How often does NewsIQ update its story feed?",
    answer:
      "NewsIQ ingests new articles every 5 minutes. Trending stories are updated with higher priority. Story summaries are regenerated when a significant new source is added to the cluster.",
  },
  {
    question: "Does NewsIQ use GPT or other LLMs?",
    answer:
      "NewsIQ uses large language models for headline generation, summary creation, entity extraction, and timeline construction. The specific models used are subject to change as we improve quality. All LLM outputs are grounded in retrieved source article content — we do not generate free-form content.",
  },
];

const faqSchema = buildFAQSchema(METHODOLOGY_FAQS);

export default function MethodologyPage() {
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
              <span className="text-sm font-medium">Methodology</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4" style={{ fontFamily: "var(--font-newsreader)" }}>
              How NewsIQ Works
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed">
              A technical explanation of how NewsIQ ingests, clusters, and
              intelligently summarises news from 200+ publishers using AI.
            </p>
          </div>
        </section>

        <div className="max-w-3xl mx-auto px-6 py-12 space-y-12">

          <section>
            <h2 className="text-2xl font-bold mb-4">Step 1 — Ingestion</h2>
            <p className="text-muted-foreground leading-relaxed">
              NewsIQ continuously fetches new articles from our curated publisher
              list via RSS feeds and news APIs. Articles are normalized, deduplicated
              by URL, and queued for analysis. Ingestion runs every 5 minutes.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Step 2 — Semantic Embedding</h2>
            <p className="text-muted-foreground leading-relaxed">
              Each article&apos;s headline and lead paragraph is transformed into a
              high-dimensional semantic vector using a sentence transformer model.
              These embeddings capture the meaning of the text, not just keywords,
              allowing us to match articles about the same event even when they use
              different terminology.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Step 3 — Story Clustering</h2>
            <p className="text-muted-foreground leading-relaxed">
              Articles within a rolling 72-hour window are clustered using cosine
              similarity on their embeddings, combined with named entity overlap
              (same people, organizations, and locations = higher relatedness score).
              Clusters that exceed our similarity threshold are merged into a single
              story with a shared headline.
            </p>
            <div className="mt-4 p-4 rounded-xl bg-card/50 border border-border/50">
              <p className="text-sm text-muted-foreground">
                <strong className="text-foreground">Accuracy:</strong> 98% clustering precision on our internal benchmark of 10,000 story events.
                Evaluated against human editorial judgement.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Step 4 — AI Summarisation</h2>
            <p className="text-muted-foreground leading-relaxed">
              Once a cluster is formed, our LLM pipeline generates:
            </p>
            <ul className="mt-4 space-y-2 text-muted-foreground">
              <li className="flex gap-2"><span className="text-primary">•</span> A neutral headline rewritten from the cluster consensus</li>
              <li className="flex gap-2"><span className="text-primary">•</span> A one-line summary (the single most important fact)</li>
              <li className="flex gap-2"><span className="text-primary">•</span> A short summary (2–3 sentences of context)</li>
              <li className="flex gap-2"><span className="text-primary">•</span> A detailed summary with key facts, entities, and implications</li>
              <li className="flex gap-2"><span className="text-primary">•</span> Extracted key facts as a structured list</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed mt-4">
              All outputs are grounded in the retrieved article content. The LLM
              cannot introduce information not present in the source articles.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Step 5 — Difference Engine</h2>
            <p className="text-muted-foreground leading-relaxed">
              For each source within a cluster, the Difference Engine identifies:
              what unique information this source covers, what information it omits
              compared to the cluster consensus, and where it factually contradicts
              other sources. This gives readers genuine cross-source literacy.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Step 6 — Timeline Construction</h2>
            <p className="text-muted-foreground leading-relaxed">
              For developing stories, our system extracts timestamped events from
              article content and orders them chronologically. Timelines are rebuilt
              each time new articles are added to the cluster.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Frequently Asked Questions</h2>
            <div className="space-y-6">
              {METHODOLOGY_FAQS.map((faq) => (
                <div key={faq.question} className="border-b border-border/50 pb-6">
                  <h3 className="font-semibold mb-2">{faq.question}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{faq.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="flex gap-4 flex-wrap pt-4">
            <Link href="/ai-transparency" className="text-sm font-medium text-primary hover:underline">AI Transparency →</Link>
            <Link href="/editorial-principles" className="text-sm font-medium text-primary hover:underline">Editorial Principles →</Link>
          </div>
        </div>
      </main>
    </>
  );
}
