# Story Inspector Specification

The **Story Inspector** (accessible at `/admin/stories/[id]`) provides deep-dive explainability for how every individual story cluster was formed, synthesized, and published.

---

## 1. Visual Interface Layout (Bloomberg Terminal Grid)

The interface is structured as a dense dashboard layout to show multiple dimensions of data without nested pagination:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ STORY: "UK Election 2026: Prime Minister Declares Early Parliament Dissolution"       │
├──────────────────────────────┬──────────────────────────────┬──────────────────────────┤
│ 📊 AGGREGATE METRICS         │ 📈 CLUSTER SIMILARITY        │ 🧬 KNOWLEDGE GRAPH       │
│ • Story ID: st_7781b2        │ • Outlier Score: 0.12        │ • Total Nodes: 18        │
│ • Total Cost: $0.142         │ • Primary Centroid Sim: 0.88 │ • Total Edges: 24        │
│ • Total Tokens: 24,500       │ • Min Sim In-Cluster: 0.82   │ [Interactive SVG Canvas] │
│ • Providers: Gemini, Groq    │ • Articles In-Cluster: 8     │                          │
├──────────────────────────────┴──────────────────────────────┴──────────────────────────┤
│ 📰 SOURCE ARTICLES LINEAGE                                                             │
│ 1. BBC News: "PM announces July election date" (Sim: 0.94) [Inspect Embeddings]        │
│ 2. Reuters: "UK Prime Minister calls election" (Sim: 0.91) [Inspect Embeddings]        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚖️ CONTRADICTIONS & DIFFERENCES DETECTED                                                │
│ • Contradiction #1: Event timing discrepancy between Guardian (10 AM) and BBC (8 AM)     │
│ • Source Bias/Coverage: Fox News focuses on market impact; Al Jazeera on international   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 🕒 TIMELINE INTEGRITY                                                                  │
│ • [08:00 AM UTC] PM speaks from Downing Street (Extracted from BBC, Reuters)           │
│ • [08:30 AM UTC] Opposition leader responds (Extracted from Guardian)                  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Telemetry and Lineage Data Structure

For any selected Story ID, the inspector calls `/api/v1/admin/stories/{story_id}/telemetry` which aggregates:

### 2.1 Cluster Similarity Scores
Exposes the HDBSCAN density metrics and distance arrays:
```json
{
  "cluster_density": {
    "outlier_score": 0.1249,
    "distance_to_centroid": 0.081,
    "similarity_distribution": {
      "min": 0.821,
      "max": 0.984,
      "mean": 0.887
    }
  }
}
```

### 2.2 Wikidata Mappings & Entity Resolution
Shows the raw text strings extracted by spaCy, the normalized entities, and their Wikidata URI mappings:
```json
{
  "entities": [
    {
      "raw_text": "Keir Starmer",
      "canonical_name": "Keir Starmer",
      "entity_type": "PERSON",
      "wikidata_id": "Q390160",
      "wikidata_url": "https://www.wikidata.org/wiki/Q390160",
      "confidence": 0.98
    }
  ]
}
```

---

## 3. Explaining AI Decisions

Each story details **why** decisions were made:

### Why did these articles cluster together?
The story inspector lists the similarity matrix for all articles inside the cluster, showing the cosine distance in the Qdrant vector space.

### Why was this summary generated?
Shows the exact inputs passed to the summarizer LLM:
*   The raw knowledge graph JSON structure.
*   The system prompt template and user prompt version used.
*   The raw text response from Gemini before it was parsed into JSON.

### Why did a stage fail/retry?
If the story's summarization stage retried or failed, the inspector lists the associated `error_logs` and `retry_history` entries:
```json
{
  "failures": [
    {
      "stage": "summary_generation",
      "attempt": 1,
      "error_type": "RateLimitError",
      "message": "429: Resource has been exhausted (e.g. queries per minute limit).",
      "fallback_triggered": "openai/gpt-4o-mini",
      "status": "resolved"
    }
  ]
}
```
