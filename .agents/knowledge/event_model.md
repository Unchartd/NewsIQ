# event_model.md — Event & Story Definitions

This document defines core terminology and representations for stories, clusters, and entities within NewsIQ.

## 1. Core Definitions
- **Article**: A single ingested news item containing text, author, feed source, and date.
- **Event**: A specific, structured occurrence extracted from one or more articles (e.g. who did what, where, and when).
- **Story Candidate**: A dynamic cluster of closely related articles grouped in vector space before synthesis.
- **Canonical Story**: The final, synthesized object representing a news topic. Includes titles, timelines, entity connections, and summaries.

## 2. Relationships
- Multiple **Articles** map to a single **Story Candidate**.
- A **Canonical Story** contains a collection of **Events** and maintains linkages to the original **Articles**.
