# cache.md — Caching Standards for NewsIQ

This standard defines cache design, key structures, TTL ranges, and semantic vector caching rules.

## 1. Cache Keys & TTL Policies
- **Key Prefixing**: Always namespace keys with colons (e.g. `newsiq:article:{id}`, `newsiq:cluster:{id}:metadata`).
- **TTL Budgets**:
  - `Raw feed items`: 2 hours (`7200` seconds).
  - `Generated summaries / synthesized stories`: 24 hours (`86400` seconds).
  - `User session contexts`: 12 hours (`43200` seconds).
- **Eviction Strategy**: Use `volatile-lru` (Least Recently Used with expiration set) to handle space recovery safely.

## 2. Semantic Caching (AI Pipeline)
- **Vector Search Cache**: Before executing expensive LLM extraction or reflection steps, check the Qdrant semantic cache.
- **Threshold**: Consider a cache hit valid only if the cosine similarity score is `0.90` or higher.
