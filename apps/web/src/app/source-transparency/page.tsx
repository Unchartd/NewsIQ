import type { Metadata } from "next";
import Link from "next/link";
import { buildPageMetadata } from "@/lib/metadata";
import { buildWebPageSchema, buildFAQSchema, serializeJsonLd } from "@/lib/jsonld";

export const metadata: Metadata = buildPageMetadata(
  "Source Transparency — NewsIQ Publishers & Attribution",
  "Understand how NewsIQ indexes news sources, our publisher attribution principles, how we respect paywalls, and how publishers can manage their presence.",
  "/source-transparency",
  {
    keywords: [
      "NewsIQ news sources",
      "publisher attribution",
      "news index transparency",
      "paywall policy",
      "publisher opt-out",
      "media monitoring sources",
    ],
  }
);

const webPageSchema = buildWebPageSchema(
  "Source Transparency — NewsIQ",
  "Our principles of fair attribution, paywall respect, source selection criteria, and indexed publishers list.",
  "/source-transparency"
);

const SOURCE_FAQS = [
  {
    question: "Does NewsIQ bypass publisher paywalls?",
    answer:
      "No. NewsIQ respects all publisher paywalls. Our crawler only indexes content that is publicly accessible or made available to search crawlers. We never scrape or bypass subscription-only content, and we actively encourage our readers to subscribe to primary sources to read their full reporting.",
  },
  {
    question: "How can publishers opt out of being indexed?",
    answer:
      "We respect publisher autonomy. If you are a publisher and wish to opt out of our news index, or if you want to update your name, logo, or RSS feed URL in our registry, please email us at support@newsiq.online. We also honor standard web crawling protocols and robots.txt directives.",
  },
  {
    question: "Does NewsIQ reproduce entire articles?",
    answer:
      "Never. NewsIQ is an analytical directory, not a publisher or content scraper. We use original articles solely to perform automated story clustering, extract timelines, compare reports, and write short summaries. Every analysis includes a prominent name, logo, and hyperlink directing users to the publisher's website for the full story.",
  },
  {
    question: "What criteria must a news source meet to be indexed?",
    answer:
      "To maintain high standards, we require sources to have: (1) a transparent editorial board and masthead, (2) clear disclosures of funding and ownership, (3) a verifiable history of factual reporting, and (4) an active, published corrections policy. Self-published blogs, satirical sites, and hyperpartisan outlets are excluded.",
  },
];

const faqSchema = buildFAQSchema(SOURCE_FAQS);

const PUBLISHER_GROUPS = [
  {
    category: "Global & International Agencies",
    description: "Primary global newswires and international reporting networks.",
    publishers: [
      { name: "Reuters", url: "https://www.reuters.com", country: "Global" },
      { name: "BBC News", url: "https://www.bbc.com/news", country: "United Kingdom" },
      { name: "Al Jazeera", url: "https://www.aljazeera.com", country: "Qatar" },
      { name: "Associated Press (AP)", url: "https://apnews.com", country: "Global" },
      { name: "France 24", url: "https://www.france24.com", country: "France" },
      { name: "Deutsche Welle (DW)", url: "https://www.dw.com", country: "Germany" },
      { name: "Euro News", url: "https://www.euronews.com", country: "Europe" },
      { name: "Voice of America (VOA)", url: "https://www.voanews.com", country: "United States" },
    ],
  },
  {
    category: "National & General News",
    description: "Leading national newspapers and broadcast networks.",
    publishers: [
      { name: "CNN", url: "https://www.cnn.com", country: "United States" },
      { name: "The Guardian", url: "https://www.theguardian.com", country: "United Kingdom" },
      { name: "The Times of India", url: "https://timesofindia.indiatimes.com", country: "India" },
      { name: "The Hindu", url: "https://www.thehindu.com", country: "India" },
      { name: "Hindustan Times", url: "https://www.hindustantimes.com", country: "India" },
      { name: "The Indian Express", url: "https://indianexpress.com", country: "India" },
      { name: "NDTV", url: "https://www.ndtv.com", country: "India" },
      { name: "Sky News", url: "https://news.sky.com", country: "United Kingdom" },
      { name: "NHK World", url: "https://www3.nhk.or.jp/nhkworld/", country: "Japan" },
      { name: "Fox News", url: "https://www.foxnews.com", country: "United States" },
    ],
  },
  {
    category: "Business, Tech & Science",
    description: "Specialized coverage for economy, market news, and innovation.",
    publishers: [
      { name: "Bloomberg", url: "https://www.bloomberg.com", country: "United States" },
      { name: "CNBC", url: "https://www.cnbc.com", country: "United States" },
      { name: "TechCrunch", url: "https://techcrunch.com", country: "United States" },
      { name: "The Verge", url: "https://www.theverge.com", country: "United States" },
      { name: "Ars Technica", url: "https://arstechnica.com", country: "United States" },
    ],
  },
];

export default function SourceTransparencyPage() {
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
              <span className="text-sm text-foreground font-medium">Source Transparency</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4" style={{ fontFamily: "var(--font-newsreader)" }}>
              Source Transparency & Attribution
            </h1>
            <p className="text-xl text-muted-foreground leading-relaxed">
              We do not replace original journalism. We organize, summarize, and credit the publishers who make it possible.
            </p>
          </div>
        </section>

        <div className="max-w-3xl mx-auto px-6 py-12 space-y-12">
          
          <section className="prose dark:prose-invert max-w-none">
            <h2 className="text-2xl font-bold mb-4">Our Attribution Principles</h2>
            <p className="text-muted-foreground leading-relaxed">
              Original reporting is essential to an informed society. NewsIQ acts as a directory to make sense of developing events, guiding users to primary sources. Our integration policies are governed by the following core commitments:
            </p>
            <div className="grid gap-4 mt-6 sm:grid-cols-2">
              <div className="p-4 rounded-lg border border-border/50 bg-card/50">
                <h3 className="font-semibold mb-1 text-foreground">Fair Credit</h3>
                <p className="text-sm text-muted-foreground">Every source article is prominently labeled with the publisher&apos;s name, logo, and a direct hyperlink to the original source text.</p>
              </div>
              <div className="p-4 rounded-lg border border-border/50 bg-card/50">
                <h3 className="font-semibold mb-1 text-foreground">Diversity of Opinion</h3>
                <p className="text-sm text-muted-foreground">We deliberately cluster articles from diverse editorial stances so readers can compare framing and identify differences.</p>
              </div>
              <div className="p-4 rounded-lg border border-border/50 bg-card/50">
                <h3 className="font-semibold mb-1 text-foreground">Transformative Use</h3>
                <p className="text-sm text-muted-foreground">We compile multi-source data to show timelines, factual comparisons, and omissions, adding analytical value rather than copying text.</p>
              </div>
              <div className="p-4 rounded-lg border border-border/50 bg-card/50">
                <h3 className="font-semibold mb-1 text-foreground">Crawler Integrity</h3>
                <p className="text-sm text-muted-foreground">We crawl under standard web protocols and respect publisher controls, paywalls, and exclusion rules in robots.txt.</p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Indexed Publishers Registry</h2>
            <p className="text-muted-foreground leading-relaxed mb-6">
              Our automated ingestion system references a growing registry of authorized publications. Below are some of the key outlets indexed across categories:
            </p>
            <div className="space-y-8">
              {PUBLISHER_GROUPS.map((group) => (
                <div key={group.category} className="border border-border/50 rounded-lg p-5 bg-card/25">
                  <h3 className="font-bold text-lg mb-1">{group.category}</h3>
                  <p className="text-xs text-muted-foreground mb-4">{group.description}</p>
                  <div className="grid gap-2 sm:grid-cols-2 text-sm">
                    {group.publishers.map((pub) => (
                      <div key={pub.name} className="flex justify-between items-center py-1.5 border-b border-border/10">
                        <a href={pub.url} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">
                          {pub.name}
                        </a>
                        <span className="text-xs text-muted-foreground">{pub.country}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Publisher Opt-Out & Customization</h2>
            <p className="text-muted-foreground leading-relaxed mb-4">
              NewsIQ is committed to collaborating with original creators. If you represent an indexed publication, you can manage your integration at any time:
            </p>
            <ul className="space-y-2 text-muted-foreground mb-6">
              <li className="flex gap-2">
                <span className="text-primary font-bold">1.</span>
                <span><strong>Attribution Update:</strong> Request changes to your brand name, logo, or canonical site URLs.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary font-bold">2.</span>
                <span><strong>Index Exclusion:</strong> Request complete removal of your domain from our clustering and indexing engines.</span>
              </li>
              <li className="flex gap-2">
                <span className="text-primary font-bold">3.</span>
                <span><strong>Feed Corrections:</strong> Submit direct RSS/Atom feeds for faster, more accurate crawling of your headlines.</span>
              </li>
            </ul>
            <p className="text-muted-foreground leading-relaxed">
              For any request or inquiry, please contact our source integrity team at{" "}
              <a href="mailto:support@newsiq.online" className="text-primary hover:underline font-semibold">
                support@newsiq.online
              </a>
              . We respond to all publisher communications within 2 business days.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold mb-4">Frequently Asked Questions</h2>
            <div className="space-y-6">
              {SOURCE_FAQS.map((faq) => (
                <div key={faq.question} className="border-b border-border/50 pb-6">
                  <h3 className="font-semibold mb-2">{faq.question}</h3>
                  <p className="text-muted-foreground text-sm leading-relaxed">{faq.answer}</p>
                </div>
              ))}
            </div>
          </section>

          <div className="flex gap-4 flex-wrap pt-4">
            <Link href="/about" className="text-sm font-medium text-primary hover:underline">About NewsIQ →</Link>
            <Link href="/methodology" className="text-sm font-medium text-primary hover:underline">Our Methodology →</Link>
            <Link href="/editorial-principles" className="text-sm font-medium text-primary hover:underline">Editorial Principles →</Link>
            <Link href="/ai-transparency" className="text-sm font-medium text-primary hover:underline">AI Transparency →</Link>
          </div>
        </div>
      </main>
    </>
  );
}
