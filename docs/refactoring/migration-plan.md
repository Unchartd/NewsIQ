# Migration & Consolidation Plan

This document outlines the step-by-step technical plan to execute the codebase cleanup while preserving correctness and backward compatibility.

## Step 1: Update Test Mocks & Delete `ner_service.py`
1. Modify [test_clustering.py](file:///c:/Users/zakau/NewsIQ/apps/api/tests/test_clustering.py) to patch `app.services.ner_service_v2.ner_service_v2.extract_entities` instead of the old `ner_service.extract_entities`.
2. Delete the legacy named entity recognition file [ner_service.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/ner_service.py).
3. Confirm that tests compile and pass.

## Step 2: Route Services through LLM Gateway
We will refactor the four core services to make calls through the LLM Gateway:
1. **`ner_service_v2.py`**:
   - Remove direct `_gemini_client` and `_openai_client` initializations.
   - Refactor `_extract_with_gemini` and `_extract_with_openai` to use `llm_gateway.execute_request`.
2. **`event_service.py`**:
   - Remove direct client setups.
   - Refactor `_extract_with_gemini` and `_extract_with_openai` to call `llm_gateway.execute_request`.
3. **`entity_linker.py`**:
   - Refactor `_disambiguate_with_llm` to call `llm_gateway.execute_request` using `EntityResolution` response format.
4. **`source_comparison_service.py`**:
   - Refactor `_analyze_with_llm` to call `llm_gateway.execute_request` using `SourceComparisonResolution` response format.
5. **`contradiction_service.py`**:
   - Refactor `_validate_with_llm` to call `llm_gateway.execute_request` using `ContradictionResolution` response format.

## Step 3: Remove Old Pipeline from `ai_service.py`
1. Delete `StoryAIResponse`, `TimelineEventSchema`, `SourceDifferenceSchema` from [ai_service.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/services/ai_service.py).
2. Delete `analyze_story`, `_analyze_with_gemini`, `_analyze_with_openai`, `_generate_mock_response`, `_normalize_gemini_response` from `ai_service.py`.
3. Update [test_clustering.py](file:///c:/Users/zakau/NewsIQ/apps/api/tests/test_clustering.py) and [test_multi_signal_clustering.py](file:///c:/Users/zakau/NewsIQ/apps/api/tests/test_multi_signal_clustering.py) to patch/mock `ai_service.summarize_story_from_kg` instead of `ai_service.analyze_story`.

## Step 4: Remove Unused Temporary Scripts
1. Delete helper/debug files: `check_db.py`, `check_pipeline_errors.py`, `check_stages.py`, `check_traceback.py`, `test_query.py`, `extract_pdfs.py` from `apps/api/` and `extract_pdfs.py` from workspace root.
2. Clean up static HTML dumps/unused styles from the workspace root.

## Step 5: Test Execution & Verification
1. Run `pytest` within the backend API context.
2. Verify that all mocks align with the new gateway-based calls and the tests pass successfully.
