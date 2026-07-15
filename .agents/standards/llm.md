# llm.md — LLM Integration Standards for NewsIQ

This standard sets constraints on prompt styling, token budgets, routing, and cost optimization.

## 1. Prompt Templates & Caching
- **Structure**: Prompts must separate static instructions from user variable content. Add marker boundaries (e.g. `### Input Data ###`) to keep variable lengths clear.
- **Formatting**: Always request structured formatting (e.g. JSON matching a strict Pydantic schema) and add a fallback step to capture partial outputs.

## 2. Model Budgets & Routing
- **Routing Rules**:
  - `Entity extraction & simple summarization`: Route to fast, low-cost models (e.g. Gemini Flash, GPT-4o-mini).
  - `Story synthesis, Reflection, and Graph updates`: Route to reasoning or advanced models (e.g. Gemini Pro, GPT-4o).
- **Fallback Thresholds**: If an extraction return yields confidence scores `< 0.70`, rerun the item with an advanced model.
