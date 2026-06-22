# Refactoring & Cleanup Roadmap

We categorize the cleanup work by priority to structure execution safely.

## Critical Priority (Perform immediately)
- **Centralize LLM Gateway Routing**: Update `ner_service_v2.py`, `event_service.py`, `entity_linker.py`, `source_comparison_service.py`, and `contradiction_service.py` to route through the LLM Gateway.
- **Delete `ner_service.py`**: Completely remove this file and update references in `tests/test_clustering.py`.
- **Remove Old Single-Pass Pipeline**: Remove `analyze_story` and its corresponding sub-methods from `ai_service.py`, and update related tests.

## High Priority (Perform during file structure cleanup)
- **Delete Temporary Helper Scripts**: Remove the debug/check scripts (`check_db.py`, `check_stages.py`, etc.) from `apps/api/` and the workspace root.
- **Observability Sweep**: Search the workspace for direct `print()` statements and console logging and replace them with standard logger calls.

## Medium Priority (Maintainability)
- **API Cleanups**: Generate documentation on any deprecated endpoints.
- **Celery Tasks Audit**: Validate that no legacy Celery tasks are scheduled or listened to.
- **Dependencies Audit**: Prune unused packages from `pyproject.toml`.

## Low Priority (Long-term)
- **Database Model & Index Optimizations**: Review table layouts and indexes.
