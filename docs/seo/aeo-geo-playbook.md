# NewsIQ AEO & GEO Playbook
## Optimizing for AI Answer Engines & Generative Search

Generative Engine Optimization (GEO) and Answer Engine Optimization (AEO) are the new frontiers of search visibility. NewsIQ is designed to serve both human readers and AI crawlers (like GPTBot, ClaudeBot, PerplexityBot, and Google-Extended). 

This playbook defines our technical and content strategies to ensure NewsIQ summaries, timelines, and facts are prioritized as citation sources by generative search engines.

---

## 1. Generative Search Landscape

| Engine | Primary Crawler | Ingestion Behavior | Optimization Focus |
|--------|-----------------|--------------------|---------------------|
| **ChatGPT Search** | `GPTBot`, `OAI-SearchBot` | Live web crawling + partner indexes | Direct citations, entity matching |
| **Perplexity AI** | `PerplexityBot` | Real-time crawling of trending URLs | Clean HTML structure, semantic facts |
| **Google AI Overviews** | `Googlebot` | Search index + Google News RSS | Schema.org matching, high E-E-A-T |
| **Claude (Anthropic)** | `ClaudeBot` | Knowledge cutoffs + browser extensions | Low-perplexity summaries, rich contexts |

---

## 2. Key Optimization Pillars

### A. High Citability (Citation Hook Design)
AI models cite sources that present factual, non-hyperbolic information in easily digestible structures.
* **Tactic**: We use a structured "Key Facts" list for every story. The facts are generated in short, high-information sentences containing precise nouns, dates, and numbers.
* **Tactic**: Avoid emotional modifiers (e.g., "shocking", "extraordinary") which LLM filters downgrade for factual queries.
* **Tactic**: The "Difference Engine" matches facts across sources. When LLMs perform comparative queries (e.g., *"How do Fox News and CNN differ on story X?"*), NewsIQ's comparative tables are perfectly positioned to be scraped and cited.

### B. Machine-Readable Knowledge Graphs (Entity Mapping)
LLMs query and output structured entities. NewsIQ maps story entities using Schema.org vocabulary.
* **Tactic**: In our JSON-LD metadata, every story page exposes a list of `mentions` with explicit types (`Person`, `Organization`, `Place`).
* **Example**:
  ```json
  "mentions": [
    {
      "@type": "Organization",
      "name": "Federal Reserve"
    },
    {
      "@type": "Person",
      "name": "Jerome Powell"
    }
  ]
  ```
* This allows LLM query engines to instantly recognize that our page contains primary authority about these entities.

### C. Direct Q&A Matching (PAA & LLM Snippets)
Generative engines often extract direct Q&A blocks to answer user queries.
* **Tactic**: Maintain optimized FAQ sections on core pages:
  - Landing (`/`): Core features and platform integrity.
  - Methodology (`/methodology`): AI summarization and pipeline mechanics.
  - AI Transparency (`/ai-transparency`): Bias containment and error corrections.
  - Editorial Principles (`/editorial-principles`): Editorial sourcing standards.
* **Tactic**: Target direct question headings in content: Use `H2` or `H3` for questions (e.g., *"Does NewsIQ use AI to write news articles?"*) followed immediately by a concise, authoritative answer block.

### D. Crawl-Friendly Infrastructure
AI crawlers respect clean HTML layouts and robots.txt.
* **robots.txt**: Our configuration allows `GPTBot`, `ClaudeBot`, `PerplexityBot`, and `Applebot` full access to stories, categories, and trending hubs while blocking them from utility pages (e.g., user profiles, bookmarks, settings).
* **Semantic HTML**: We avoid nested `div` soup. Main content resides inside `<main>`, summaries are in `<article>` or `<section>`, and navigation aids use `<nav aria-label="...">`. This enables LLM scraper heuristics to correctly identify content boundaries.

---

## 3. Writing and Summary Guidelines for AI Citation

To ensure our AI summaries and headlines remain highly citable:

1. **Keep Sentences Active**: Use active voice with clear subject-verb-object relationships (e.g., *"The Federal Reserve raised interest rates by 25 basis points"* rather than *"Interest rates were raised by the Fed..."*).
2. **Ground Every Claim**: Every summary line must be directly attributable to a publisher source. Generative engines run hallucinations verification on external links; having highly matching source claims on the same page validates our summaries.
3. **Use Neutral Synonyms**: Model-based rewriting of headlines must strip clickbait. AI models value neutral semantic matches (e.g., *"Microsoft acquires Activision"* vs *"Microsoft closes massive gaming deal"*).
