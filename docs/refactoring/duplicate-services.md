# Duplicate Services & Implementations Report

We have audited the services layer in the `app/services` directory to find duplicate or overlapping implementations. The following areas exhibit technical debt or redundancy:

## 1. Named Entity Recognition (NER)
- **Legacy Service**: `app/services/ner_service.py`
  - *Details*: Uses a basic spaCy `en_core_web_sm` model and a simple regex fallback. Categorizes into only 4 generic types: `PERSON`, `ORG`, `LOCATION`, `EVENT`.
- **New Service**: `app/services/ner_service_v2.py`
  - *Details*: Implements a two-pass approach using LLM (Gemini/OpenAI) for context-aware extraction with 25+ entity types, and fallback to spaCy `en_core_web_lg`/`en_core_web_sm` + post-processing rules.
- **Consolidation Strategy**:
  - `ner_service.py` is completely unused in the main application logic. Only one unit test (`tests/test_clustering.py`) still references and patches it.
  - We will redirect `tests/test_clustering.py` to patch `ner_service_v2.ner_service_v2.extract_entities` and safely delete `ner_service.py`.

## 2. Story Summarization & Differences Engine
- **Legacy Pipeline**: `ai_service.analyze_story`
  - *Details*: A single one-pass method that sends raw article list text to the LLM to generate headlines, summaries, timelines, and source differences in one massive prompt. This is bypassed by the new architecture but still exists in the code and is referenced by tests.
- **New Pipeline**: Knowledge-Graph Grounded Summarization
  - *Details*: Runs modular event extraction, entity linking, knowledge graph compilation, contradiction detection, and source comparison *before* sending a structured summary prompt to `ai_service.summarize_story_from_kg`.
- **Consolidation Strategy**:
  - Remove `analyze_story` and its sub-helpers (`_analyze_with_gemini`, `_analyze_with_openai`, `_generate_mock_response`) from `ai_service.py`.
  - Update `tests/test_clustering.py`, `tests/test_multi_signal_clustering.py`, and `tests/test_analysis_engines.py` to test/mock the active `summarize_story_from_kg` flow.

## 3. Scattered LLM Client Providers
- **Current Issue**:
  - `ner_service_v2.py`, `event_service.py`, `entity_linker.py`, `source_comparison_service.py`, and `contradiction_service.py` all define their own `_gemini_client` and `_openai_client` initializations and invoke raw clients directly.
  - This bypasses the LLM Gateway, defeating the purpose of centralized key rotation, rate limiting, cooldown, and telemetry.
- **Consolidation Strategy**:
  - Replace all direct client calls and initializations in these services with `llm_gateway.execute_request` or `llm_gateway.execute_request_sync`.
  - Delete direct `openai` and `google-genai` client adaptations/retry decorators in the services.
