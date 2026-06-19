# NewsIQ E-E-A-T Strategy
## Experience, Expertise, Authoritativeness, & Trustworthiness in AI Aggregation

Google's Search Quality Rater Guidelines place a strong emphasis on **E-E-A-T**, especially for news and information portals classified under **YMYL** (Your Money or Your Life). Because NewsIQ uses artificial intelligence to summarize and compare news, establishing trust is our highest priority.

This document outlines how NewsIQ builds and maintains E-E-A-T credibility for both Google Quality Raters and search algorithms.

---

## 1. The E-E-A-T Framework for NewsIQ

* **Experience**: We highlight the direct, primary reporting of the journalists we index, linking users straight to the boots-on-the-ground coverage.
* **Expertise**: We demonstrate technical expertise in news analysis by documenting our AI pipeline, natural language processing models, and bias-containment benchmarks.
* **Authoritativeness**: We establish authority by functioning as a transparent directory that aggregates and links to the world's most reputable news organizations.
* **Trustworthiness**: The most critical pillar. We achieve trust through total disclosure of AI usage, strict source selection criteria, paywall respect, and clear publisher opt-out controls.

---

## 2. Our Transparency Pages Architecture

To satisfy quality rating criteria, we have built a dedicated public E-E-A-T directory. These pages are server-side rendered, publicly indexable, and dynamically linked in the site footer:

### A. About `/about`
* **Purpose**: Disclose who is behind NewsIQ, our mission, funding structure, and contact information.
* **Trust Signal**: Demonstrates that NewsIQ is a legitimate organization with accountable founders, not an anonymous, AI-generated spam farm.

### B. Editorial Principles `/editorial-principles`
* **Purpose**: Define how stories are prioritized, how headlines are rewritten for neutrality, and our strict corrections policy.
* **Trust Signal**: Establishes that we follow standard journalistic and editorial protocols, including manual review of errors and systematic corrections.

### C. Methodology `/methodology`
* **Purpose**: Detail the technical 6-step pipeline (Ingestion, Embedding, Clustering, Summarization, Comparison, and Timelines).
* **Trust Signal**: Demystifies our technology, showing that our summaries are grounded mathematically in retrieved article texts, eliminating random hallucinations.

### D. AI Transparency `/ai-transparency`
* **Purpose**: Direct disclosure of what AI does on NewsIQ, what AI is forbidden from doing (e.g., generating original news, fake images), known model limitations, and how readers can report errors.
* **Trust Signal**: Aligns with Google's guidelines on AI-generated content transparency, ensuring the platform is not labeled as misleading.

### E. Source Transparency `/source-transparency`
* **Purpose**: List our active news publisher registry, selection criteria, paywall policies, and opt-out/attributive update forms.
* **Trust Signal**: Protects copyright, respects intellectual property, and encourages readers to support the publishers whose work feeds our analysis.

---

## 3. Schema.org Trust Signals

Metadata is the primary language search engines use to verify E-E-A-T. We inject custom JSON-LD schemas into our server-side layout:

1. **`Organization` Schema**: Declares NewsIQ's name, official website, logo URL, customer support email, and verified social media accounts. This connects our website to Google's Knowledge Graph.
2. **`isBasedOn` Relationship**: Every story page includes a `NewsArticle` schema containing an `isBasedOn` property. This lists the exact URLs of the primary articles our AI summarized, giving programmatic credit to the original publishers.
3. **`author` and `publisher`**: The author and publisher are explicitly set to the NewsIQ Organization, clarifying that we are responsible for the summary outputs while linking to the base reporting.
4. **`FAQPage` Schema**: Implemented on all informational pages to answer structural questions directly in Google search results, raising click-through rates.
