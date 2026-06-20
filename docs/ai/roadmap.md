# NewsIQ AI Pipeline Roadmap

> Event-Centric Intelligence Platform Transformation

## Vision

Transform NewsIQ from an article summarizer into an event-centric news intelligence platform that understands events first, then summarizes.

```text
CURRENT:  Articles → Embeddings → Cluster → LLM Summary
TARGET:   Articles → Events → Entities → Knowledge Graph → Cluster → Analyze → Summarize
```

---

## Phase Overview

| Phase | Name | Priority | Dependencies | Est. Effort | Status |
|:--:|:--|:--:|:--|:--:|:--:|
| 1 | Pipeline Audit | 🔴 | — | ✅ Done | ✅ |
| 2 | Event Extraction Engine | 🔴 | Phase 1 | 2-3 days | ⬜ |
| 3 | Event Canonicalization | 🔴 | Phase 2 | 1 day | ⬜ |
| 4 | Event Time vs Reporting Time | 🔴 | Phase 2 | 1 day | ⬜ |
| 5 | Knowledge Graph | 🟠 | Phases 2-4, 6-7 | 2-3 days | ⬜ |
| 6 | Entity Extraction Redesign | 🔴 | Phase 1 | 2-3 days | ⬜ |
| 7 | Entity Linking | 🟠 | Phase 6 | 2 days | ⬜ |
| 8 | Story Clustering Redesign | 🔴 | Phases 2-7 | 3-4 days | ⬜ |
| 9 | Contradiction Engine | 🟠 | Phase 5 | 2 days | ⬜ |
| 10 | Source Coverage Engine | 🟠 | Phase 5 | 1-2 days | ⬜ |
| 11 | Timeline Engine Redesign | 🟡 | Phase 4 | 1 day | ⬜ |
| 12 | Summary Engine Redesign | 🔴 | Phases 5, 8-11 | 2-3 days | ⬜ |
| 13 | Difference Engine Redesign | 🟠 | Phases 9-10 | 1-2 days | ⬜ |
| 14 | Quality Gate | 🟠 | Phase 8 | 1 day | ⬜ |
| 15 | Test Dataset & Evaluation | 🟡 | All | 2-3 days | ⬜ |
| 16 | Documentation | 🟢 | All | 1-2 days | ⬜ |

---

## Recommended Execution Batches

### Batch 1: Foundation (Phases 2-4, 6)
**Goal**: Extract structured events and entities from every article.

- Event Extraction Engine (Phase 2)
- Event Canonicalization (Phase 3)
- Event Time Handling (Phase 4)
- Entity Extraction Redesign (Phase 6)

**Deliverable**: Every new article has extracted events and entities stored in `article_events` table. Old pipeline continues to function unchanged.

### Batch 2: Intelligence Layer (Phases 5, 7)
**Goal**: Build knowledge graph and link entities.

- Knowledge Graph Builder (Phase 5)
- Entity Linking (Phase 7)

**Deliverable**: Per-story knowledge graph built from events and entities. Entity canonicalization resolves duplicates.

### Batch 3: Clustering Revolution (Phases 8, 14)
**Goal**: Replace embedding-only clustering with multi-signal scoring.

- Story Clustering Redesign (Phase 8)
- Quality Gate (Phase 14)

**Deliverable**: New clustering uses event type, actors, location, time, and entities — not just embeddings. Bloomberg editor test applied.

### Batch 4: Analysis Engines (Phases 9-11, 13)
**Goal**: Structured analysis replaces LLM guessing.

- Contradiction Engine (Phase 9)
- Source Coverage (Phase 10)
- Timeline Engine (Phase 11)
- Difference Engine (Phase 13)

**Deliverable**: Contradictions, timelines, and source differences are based on extracted facts, not LLM hallucination.

### Batch 5: Synthesis & Validation (Phases 12, 15-16)
**Goal**: Summary becomes the last step. Validate everything.

- Summary Engine Redesign (Phase 12)
- Test Dataset & Evaluation (Phase 15)
- Documentation (Phase 16)

**Deliverable**: Summaries generated from knowledge graph, not raw text. Full test coverage. Complete documentation.

---

## Guiding Principles

1. **Events first, summaries last** — Understand what happened before writing about it.
2. **False positives are catastrophic** — Never merge unrelated events.
3. **False negatives are acceptable** — Better to split a story than to corrupt one.
4. **Every fact must be traceable** — No hallucinated contradictions or differences.
5. **Incremental deployment** — Each phase enhances without breaking existing functionality.
6. **Bloomberg standard** — "Would a Bloomberg editor agree these articles are about the same event?"
