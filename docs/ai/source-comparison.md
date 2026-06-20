# Source Comparison Engine

The **Source Comparison Engine** analyzes stories to understand how different publishers cover the same event, identifying unique information, missing coverage, and contradictions.

## Architecture

The comparison engine operates per-source on each event cluster:
1. **Fact Extraction**: Aggregates actors, targets, locations, and key numbers reported by a specific source.
2. **Global Comparison**: Intersects this publisher's facts against the aggregated facts of all other publishers in the same story.
3. **Difference Calculation**:
   - **Unique Information**: Facts (actors, targets, locations, numbers) reported ONLY by this publisher.
   - **Missing Information**: Facts reported by other publishers but omitted by this publisher.
4. **LLM Synthesis**: Uses an LLM to generate professional, fluent, and objective sentences describing:
   - The publisher's `focus_area`.
   - The publisher's `unique_information`.
   - The publisher's `missing_information`.
5. **Deterministic Fallback**: If the LLM is disabled or fails, the engine formats the raw heuristic diffs (e.g. unique/missing actors) into structured lists.

---

## Database Schemas

Source comparisons map to two tables:

### 1. `story_source_coverage`
Stores a brief summary of a publisher's angle/focus.
```sql
CREATE TABLE story_source_coverage (
    id UUID PRIMARY KEY,
    story_id UUID REFERENCES stories(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id),
    focus_area TEXT,                  -- Max 100 characters summary
    published_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
```

### 2. `story_differences`
Stores detailed lists of unique, missing, and contradictory details per publisher.
```sql
CREATE TABLE story_differences (
    id UUID PRIMARY KEY,
    story_id UUID REFERENCES stories(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id),
    unique_information TEXT,          -- Details mentioned ONLY by this source
    missing_information TEXT,         -- Details omitted by this source
    contradictions TEXT               -- Contradictions involving this source
);
```
