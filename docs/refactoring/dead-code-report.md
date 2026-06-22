# Dead Code Report

Fractions of the codebase that are unused, deprecated, or redundant.

## Safe to Delete
The following components are confirmed safe to delete because they are completely unused in the main codebase flow:
- **`apps/api/app/services/ner_service.py`**: Kept only for legacy tests. Safe to remove once tests are updated.
- **`ai_service.analyze_story`** (and its sub-methods `_analyze_with_gemini`, `_analyze_with_openai`, `_generate_mock_response`, `_normalize_gemini_response`): Kept only for legacy tests. Safe to remove once tests are updated.
- **Temporary check scripts**: `apps/api/check_db.py`, `apps/api/check_pipeline_errors.py`, `apps/api/check_stages.py`, `apps/api/check_traceback.py`, `apps/api/test_query.py`, `apps/api/extract_pdfs.py`, `extract_pdfs.py`, static HTML files, and css files at the workspace root.

## Needs Review
- **`app/services/replay_service.py`**: Used to replay story stages for debugging. We should keep this as it is valuable for debugging, but ensure it does not import legacy services.

## Referenced Dynamically
- **Agno Agent Routing (`app/agents/agent_router.py`)**: Resolves agent instances by string names (`cluster_verification_agent`, etc.) dynamically from the agent registry. This is active and must not be modified or deleted.

## Potential Risk
- **Database Migrations**: Removing old migrations from `alembic/versions` can break database state sync for existing deployments. Therefore, we should NOT delete existing migration files.
- **`.env` files**: Avoid deleting environment variables that are active in other parts of the system or contain secrets.
