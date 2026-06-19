# ADR-002: AI Synthesis Pipeline

## Status
Approved

## Context
NewsIQ requires ingesting hundreds of articles daily, checking for semantic duplication, grouping related articles into cohesive "stories," and synthesizing neutral summaries, timelines, and publisher differences.

## Decision
We implement a multi-stage pipeline combining vector search with density-based clustering and generative AI models:
1. **Deduplication & Embeddings**: Incoming articles are vectorized to a 768-dimension space using Gemini `text-embedding-004` (falling back to OpenAI).
2. **Real-time Incremental Merge**: On vector ingest, we search Qdrant for similar vectors (Cosine similarity $\ge 0.80$). If found, the article merges into that story immediately.
3. **Batch Clustering**: Unclustered articles are grouped every 10 minutes using **HDBSCAN** (`min_cluster_size=2`, `min_samples=1`, `epsilon=0.35`).
4. **LLM Synthesis**: Grouped clusters are sent to Gemini `gemini-2.5-flash-lite` (with OpenAI fallback) to generate objective summaries, timelines, and source differences in a single structured JSON response.

## Alternatives Considered
- **Traditional NLP (TF-IDF/BM25)**: Relies on exact keyword matches and fails to capture semantic similarity (e.g. "iPhone launch" and "Apple's new smartphone").
- **K-Means Clustering**: Requires predefining the number of clusters ($K$), which is impossible for dynamic news cycles.

## Trade-offs
- **Pros**:
  - **Dynamic Story Count**: HDBSCAN automatically determines the correct number of stories based on data density without hardcoding $K$.
  - **Incremental Updates**: Incremental merges keep feeds fresh without running heavy batch clustering runs on every write.
- **Cons**:
  - **LLM Cost & Speed**: Calling Gemini for every merge or new cluster is computationally expensive and introduces latency.
  - **Epsilon Sensitivity**: Changes in embedding models require tuning the HDBSCAN epsilon parameters.

## Consequences
- Requires a robust Redis caching layer to shield the database and LLM endpoints from redundant queries.
- Mandatory distributed rate limiting (via Redis) to prevent concurrent workers from exceeding Gemini's free-tier RPM limits.
