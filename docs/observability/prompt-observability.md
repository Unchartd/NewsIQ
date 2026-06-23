# Prompt Versioning & Playground Spec

This specification details the prompt observability registry used to audit, trace, test, and replay LLM interactions within the news intelligence system.

---

## 1. Prompt Registry Schema (`prompt_versions`)

Every prompt sent to the LLMs is backed by a row in the `prompt_versions` table:

```sql
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    prompt_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA-256 hash of system_prompt + user_prompt_template
    stage VARCHAR(100) NOT NULL,            -- e.g., 'summary_generation', 'contradiction_detection'
    system_prompt TEXT,
    user_prompt_template TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now())
);
```

### Deduplication Strategy
Before executing any LLM task, the system computes the SHA-256 hash of the compiled system prompt and user template. 
1. If the hash exists in the database, the system pulls the existing `prompt_version_id` to link with the `llm_traces` record.
2. If the hash does not exist, a new version is inserted (incrementing the version number relative to the target `stage`) and set as `is_active`.

---

## 2. Telemetry Trace Schema (`llm_traces`)

Every prompt invocation is linked to a trace record containing metrics:

*   `prompt_version_id`: Link to the source template.
*   `input_tokens` / `output_tokens`: Exact counts from the provider's response metadata.
*   `cost_usd`: Calculated using standardized cost maps per 1M tokens.
*   `latency_ms`: Response duration.
*   `raw_response`: Captured raw JSON string.

---

## 3. Visual Dashboard (/admin/prompts)

The UI panel includes three components:

### 3.1 Version History & Diff View
Developers can compare version `v2` and `v3` of a prompt side-by-side with colored diffs:
*   `Red` for deletions
*   `Green` for insertions

```diff
- Generate a summary that is strictly under 150 words.
+ Generate a concise summary that is strictly under 200 words, highlighting key facts.
```

### 3.2 Prompt Playground & Execution Replay
Allows developers to select a historical trace, modify the prompts in an interactive editor, select an LLM provider (e.g. Gemini, Groq, OpenAI), and execute a replay test on the original inputs.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PLAYGROUND REPLAY                                                                      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ INPUTS (Original run_id: run_8892):                                                   │
│ { "knowledge_graph": { "nodes": [...], "edges": [...] } }                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ✏️ EDIT SYSTEM PROMPT (v3):                                                            │
│ You are an expert editor. Summarize the following news story:                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [ Select Model: Gemini 2.5 Flash ▼ ]                       [ Run Test Execution ]      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 📊 OUTPUT COMPARISON                                                                   │
│ Latency: 420ms | Cost: $0.00012 | Tokens: 450                                          │
│ Response: "The Prime Minister announced an early election..."                          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
