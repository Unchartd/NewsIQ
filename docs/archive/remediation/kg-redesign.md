# 🕸️ NewsIQ Knowledge Graph Execution Pipeline Redesign

This document outlines the architectural changes required to correct the execution order of the Knowledge Graph (KG) serialization and summarization stages within the story-generation pipeline.

---

## 1. Problem Statement

In the original pipeline design, Knowledge Graph construction occurred immediately after entity extraction:

```
[Entity Extraction] ──► [Build KG] ──► [Contradiction / Differences] ──► [Summarization]
```

This sequence introduced two critical flaws:
1. **Incomplete Context**: The contradiction and source-difference detection stages ran *after* the KG was built. As a result, contradiction findings (e.g., source A claiming 10 causalities while source B claims 100) were completely missing from the KG payload.
2. **Database Cascade Vulnerabilities**: Story timeline and entity records were written to the database after the KG was built. If these later database commits failed, the KG was either not serialized or left mismatched with the relational database state.

---

## 2. Redesigned Pipeline Flow

We restructure the pipeline to guarantee that all analytical metadata is saved to the database *before* compiling and serializing the Knowledge Graph:

```
[Timeline / Entities] ──► [Contradiction / Differences] ──► [Build & Serialize KG] ──► [Summarization]
```

### Execution Sequencing in `generate_story_content`:

1. **Purge Sub-tables**: Perform explicit SQL `DELETE` queries to clear old timeline events, source coverages, differences, contradictions, and entities associated with the target story.
2. **Ingest Relational Data**: Fetch all active articles and source profiles.
3. **Commit Timeline Events**: Build and save the chronologically sorted timeline.
4. **Commit Named Entities**: Load and save disambiguated article-level entities.
5. **Run Analysis Engines**: Execute contradiction and difference engines, writing results to `StoryContradiction` and `StoryDifference` tables.
6. **Compile & Serialize Knowledge Graph**: Build the KG using the newly committed entity relationships, timeline events, and contradiction reports. Set `story.knowledge_graph = kg_dict`.
7. **Trigger Summarization**: Fetch Gemini or Claude models to generate summaries grounded directly by the compiled Knowledge Graph dictionary and contradiction list.
