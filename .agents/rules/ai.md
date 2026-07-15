---
trigger: always_on
---

# ai.md — AI & NLP Pipeline Coding Rules for NewsIQ

These rules govern LLM logic, parsing, embedding, clustering, and story synthesis pipelines.

## 1. Prompt Design & Versioning
- **Externalized Prompts**: Never hardcode LLM prompts inside execution functions. Keep all prompts in a centralized directory or configuration store.
- **Versioning**: Version all prompt templates. Document modifications to inputs and outputs to prevent parsing failures.
- **Prompt Caching**: Structure prompts to maximize the efficiency of LLM provider prompt caches (e.g. static system instructions first, variable context last).

## 2. Token Budgeting & Model Routing
- **Adaptive Context**: Adjust target context windows dynamically based on document input sizes to minimize token consumption.
- **Routing**: Route simple verification tasks to fast, low-cost models, reserving complex synthesis and reflection operations for premium models.
- **Semantic Caching**: Before dispatching an LLM call, query the vector cache to identify matching historical results, reducing operational costs.
