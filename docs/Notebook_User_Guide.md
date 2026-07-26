# NewsIQ Pipeline X-Ray — Notebook User Guide

> How to use `Pipeline_XRay.ipynb` as a production debugger, learning tool, and cost profiler.

---

## The Core Philosophy

Every cell in this notebook answers four questions:

| Question | What to look for |
|----------|-----------------|
| **Input** | Variables from the previous cell |
| **Function** | The exact production function called (no wrappers) |
| **Output** | Named variables produced, ready for inspection |
| **Timing** | `⏱ label: X ms  |  Δmem +Y MB` printed by `_Timer` |

**Nothing is hidden.** If a function calls another function, you can set a breakpoint, add a `print()`, or re-run the production source directly.

---

## The Variable State Chain

Every pipeline stage produces one or more named variables. These persist across cells:

```
rss_sources
    ↓  Section 1
selected_source, selected_feed_url
    ↓  Section 2
raw_feed, feed_entries
    ↓  Section 3
selected_entry, article_url, article_title_raw
    ↓  Section 4
canonical_url, raw_crawl_result, article_content
    ↓  Section 5
normalized_headline, discovery_score, score_breakdown
    ↓  Section 6
fingerprints, is_duplicate
    ↓  Section 7
article, article_id, article_from_db
    ↓  Section 8
embedding_text, embedding_vector
    ↓  Section 9
qdrant_upsert_result, qdrant_search_result
    ↓  Section 10
entity_manifest, entities
    ↓  Section 11
event_manifest, events, raw_event_response
    ↓  Section 12
stage_a_result, validated_events
    ↓  Section 13
qdrant_candidates, candidate_clusters, candidate_articles
    ↓  Section 14
raw_reflection_response, reflection_result
    ↓  Section 15
judge_result
    ↓  Section 16
timeline
    ↓  Section 17
knowledge_graph, kg_dict
    ↓  Section 18
synthesis_manifest, raw_synthesis_response, story_summary
    ↓  Section 19
saved_story
    ↓  Section 20
meili_document, meili_result
    ↓  Section 21
redis_key, redis_cached, cache_read_back
    ↓  Section 22-23
story_for_api, api_response, api_response_json
```

---

## Inspecting LLM Calls

Every AI call uses one of these transparent patterns:

### Pattern A — Direct gateway call

```python
# Section 14 — reflection
raw_reflection_response = await ai_gateway.generate_stage(
    stage="cluster_verification",
    prompt_variables=cluster_prompt_vars)

show_gateway_response(raw_reflection_response)
```

`show_gateway_response()` prints:
- provider, model, latency_ms, cost_usd
- input_tokens, output_tokens, total_tokens
- raw content (full LLM output string)
- parsed structured object type

### Pattern B — Interceptor (to capture responses from service calls)

```python
# Wrap the gateway to capture responses emitted inside service calls
_orig = ai_gateway.generate_stage

async def _capture(stage, variables, schema=None, story_id="", article_id=""):
    global raw_event_response
    resp = await _orig(stage, variables, schema, story_id, article_id)
    if stage == "event_extraction":
        raw_event_response = resp
    return resp

ai_gateway.generate_stage = _capture
# ... call service ...
ai_gateway.generate_stage = _orig  # always restore
```

### Pattern C — Inspect prompt manifest before calling

```python
event_manifest = prompt_repository.get("event_extraction")
show_manifest(event_manifest)
# Prints: model, temperature, max_tokens, system prompt, user template
```

---

## Inspecting Database Operations

SQL capture is installed in key persistence cells:

```python
sql_statements = []

@_sa_event.listens_for(engine.sync_engine, "before_cursor_execute")
def _cap_sql(conn, cursor, stmt, params, ctx, em):
    sql_statements.append({"sql": stmt[:400], "params": str(params)[:200]})
```

After the INSERT, inspect:
```python
for i, stmt in enumerate(sql_statements):
    box(stmt["sql"], title=f"SQL [{i}]")
```

---

## Debugging Production Issues

### Scenario 1: Why was this article rejected?

```python
# Run Section 5 and inspect:
print(f"discovery_score : {discovery_score:.4f}")
for k, v in score_breakdown.items():
    print(f"  {k}: {v}")
```

### Scenario 2: Why are two unrelated articles being merged?

```python
# Run Section 13 and inspect similarity scores:
for cid, d in sorted(candidate_clusters.items(), key=lambda x: -x[1]["score"]):
    print(f"score={d['score']:.4f}  {d['title'][:60]}")

# Lower SIMILARITY_THRESHOLD to see why they're hitting the threshold:
SIMILARITY_THRESHOLD = 0.85  # raise it
```

### Scenario 3: Why is the AI summary wrong?

```python
# In Section 18, inspect the raw LLM input and output:
box(filled_synthesis_prompt[:5000], title="What the LLM received")
show_gateway_response(raw_synthesis_response)
```

### Scenario 4: Why is entity extraction missing an entity?

```python
# In Section 10, check the filled prompt:
_f = entity_manifest.template.format(text=ner_input_text[:2000])
box(_f[:3000], title="Exact prompt sent to model")

# And the model config:
print(entity_manifest.model_config)
```

### Scenario 5: Is this article already in the DB?

```python
# Section 6 cell [6.3] checks by url_hash:
async with async_session_factory() as _s:
    _r = await _s.execute(
        select(Article).where(Article.url_hash == fingerprints["url_hash"]).limit(1))
    result = _r.scalar_one_or_none()
print(result)
```

---

## Replaying a Stage with Modified Inputs

Because all variables persist, you can replay any stage freely:

```python
# Replay event extraction with a custom text
ner_input_text = "Custom text to test NER on..."
entities = await ner_service_v2.extract_entities(ner_input_text)
print(entities)
```

```python
# Replay synthesis with a modified knowledge graph
kg_dict["nodes"].append({"id": "custom-1", "type": "entity", "label": "New Entity"})
story_summary = await ai_service.summarize_story_from_kg(
    kg=kg_dict, contradictions=[], timeline=timeline, source_comparisons=[])
print(story_summary.headline)
```

---

## Cost Profiling

After running the full pipeline, collect costs from gateway responses:

```python
total_cost = sum(filter(None, [
    raw_event_response.cost_usd if raw_event_response else None,
    raw_reflection_response.cost_usd if raw_reflection_response else None,
    raw_synthesis_response.cost_usd if raw_synthesis_response else None,
]))
print(f"Total LLM cost this run: ${total_cost:.6f}")
```

---

## Understanding `show_gateway_response()` Output

```
── raw_event_response ─────────────────────────────────────
  provider     : google
  model        : gemini-2.0-flash
  latency_ms   : 823.4           ← wall-clock including network
  cost_usd     : $0.000142       ← computed from token counts × pricing table
  input_tokens : 412
  output_tokens: 286
  total_tokens : 698
  parsed type  : ArticleEventResponse   ← None if parsing failed
  error        : None                   ← non-None if LLM call failed
┌──────────────────────────────── raw content ────────────┐
│ {"primary_event": {"event_type": "POLITICAL", ...}}    │
└────────────────────────────────────────────────────────┘
```

---

## Understanding `show_manifest()` Output

```
── event_extraction (event_extraction @ 1.3.0) ──
  model         : gemini-2.0-flash
  temperature   : 0.1
  max_tokens    : 2048
  timeout_sec   : 30
  cacheable     : True
  lifecycle     : production
┌──── system prompt ───────────────────────────────────────┐
│ You are an expert event extraction system...            │
└──────────────────────────────────────────────────────────┘
┌──── user template ───────────────────────────────────────┐
│ Article title: {title}                                  │
│ Source: {source_name}                                   │
│ ...                                                     │
└──────────────────────────────────────────────────────────┘
```

---

## Tips

1. **Run `Section 0` every session** — it validates all infra before you do expensive AI calls.
2. **Don't skip SETUP** — missing `sys.path` breaks all imports silently.
3. **`SELECTED_ENTRY_INDEX`** lets you quickly test different article types (opinion, breaking news, sports) without changing any other code.
4. **Re-run individual cells** to re-inspect any stage — all prior variables remain valid.
5. **The notebook does not modify production data** unless you explicitly run Section 7 (Article INSERT) and Section 19 (Story INSERT). Skip those cells for a fully read-only inspection run.
6. **Vector search results** depend on what is already in Qdrant. An empty Qdrant will show zero candidates — that is expected.
