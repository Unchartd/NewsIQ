# ADR-004: Database-Driven Personalized Feed

## Status
Approved

## Context
Users require a personalized news feed filtering stories by their preferred categories, regions (locations), and bookmark histories. The feed must also account for trending scores.

## Decision
We implement a database-driven personalized query structure at the PostgreSQL layer:
- **Filters**: Joins the user's category preferences (`user_categories`) and location preferences (`user_locations`) to filter active stories.
- **Sorting**: Order by story trending scores (combining source diversity, exponential recency decay, and user engagement).
- **Caching**: The first page of personalized queries is cached in Redis under `user_feed:<user_id>` for 5 minutes. Subsequent pages bypass the cache to guarantee accurate pagination.

## Alternatives Considered
- **Client-Side Filtering**: Fetching all stories and filtering them in React. This consumes massive network bandwidth and breaks server-side pagination.
- **Vector Search Recommendation (Qdrant)**: Querying Qdrant using the user's read history vector. This is ideal for long-term profiling but doesn't respect explicit user-configured category and location filters.

## Trade-offs
- **Pros**:
  - **Accurate Filtering**: Explicit category and location preferences are enforced.
  - **Dynamic Ranking**: Stories rise and fall naturally based on trending scores.
- **Cons**:
  - **Complex DB Joins**: Joining users, preferences, categories, and stories can slow down under high loads.
  - **Cache Invalidation**: Writes to stories (like real-time merges) must eventually trigger cache updates.

## Consequences
- Composite database indexes are required on `stories(category_id, trend_score)` and join tables to keep query execution times under 50ms.
