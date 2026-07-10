# NewsIQ Prompt Versioning Protocol

All LLM prompts inside the NewsIQ AI processing pipeline are centralized, versioned, and structured to optimize prefix caching and ensure cache consistency.

---

## 1. Prompt Registry

The [PromptRegistry](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/prompt_registry.py) is the single source of truth for all templates. Direct inline prompt strings are strictly prohibited in pipeline services.

### System/User Message Split

To maximize provider-side prompt prefix caching (such as Gemini's context caching), every prompt template splits system instructions from dynamic user inputs:

```python
_EVENT_EXTRACTION = PromptTemplate(
    stage="event_extraction",
    version="v2",
    model="gemini-2.5-flash-lite",
    system=(
        "You are a Staff News Intelligence Extraction Engineer..."  # STATIC prefix
    ),
    template=(
        "Extract the primary event and entities from this article:\n\n"
        "Title: {title}\n..."  # DYNAMIC variables
    ),
)
```

Because the system instructions are static across all requests, LLM providers can reuse the compiled prefix context, reducing latency and input costs by up to 50% for high-throughput stages.

---

## 2. Invalidation Protocol

Bumping the version of a prompt template is the primary method for invalidating cached responses when the prompt's instructions or schemas are updated.

### Versioning Rules

We follow a semantic-like model for prompt versioning:

1. **Major Version Bump (`v1` → `v2`)**:
   - Trigger: Schema structure changes, output JSON format updates, or substantial instruction changes.
   - Effect: Forces a cache miss for all subsequent requests under this stage. Old cache entries will eventually be purged by the 30-day cleanup TTL.
2. **Minor Version Bump (`v2.1` → `v2.2`)**:
   - Trigger: Prompt refinement, clarification tweaks, or addition of few-shot examples.
3. **No Bump**:
   - Fixes to documentation or comments inside the template definitions.

### How to Bump a Version

1. Edit the prompt definition in `app/services/prompt_registry.py`.
2. Update the `version` field (e.g. from `"v2"` to `"v3"`).
3. Commit the change. The cache will immediately roll over on deployment.
