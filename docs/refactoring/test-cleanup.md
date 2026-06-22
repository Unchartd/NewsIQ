# Test Cleanup Report

An audit of unit and integration tests.

## Dead/Legacy Mocks & Fixtures
The following unit tests contain legacy mocks and patch points:
- **`tests/test_clustering.py`**:
  - Patches `app.services.ner_service.ner_service.extract_entities` (obsolete).
  - Patches `app.services.ai_service.ai_service.analyze_story` (obsolete).
- **`tests/test_multi_signal_clustering.py`**:
  - Patches `app.services.ai_service.ai_service.analyze_story` (obsolete).
- **`tests/test_analysis_engines.py`**:
  - Patches `app.services.ai_service.ai_service.analyze_story` (obsolete).

## Cleanup Strategy
- Update all occurrences of `ner_service.ner_service` to patch `ner_service_v2.ner_service_v2` instead.
- Replace patches for `ai_service.analyze_story` with patches/mocks for `ai_service.summarize_story_from_kg` where appropriate, reflecting the new graph-grounded synthesis pipeline.
