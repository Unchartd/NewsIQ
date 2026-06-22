# Environment Cleanup Report

An audit of env variables configured in `.env` and `apps/api/.env`.

## Active Env Variables
- `DATABASE_URL`: Active PostgreSQL connection.
- `REDIS_URL`: Active cache/queue connection.
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`: Active Celery settings.
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`: Active Qdrant settings.
- `MEILISEARCH_HOST`, `MEILISEARCH_API_KEY`: Active Meilisearch settings.
- `GEMINI_API_KEY`, `GEMINI_API_KEY_SYNTH`, `GEMINI_API_KEY_EMBEDDING`: Active Gemini API keys.
- `OPENAI_API_KEY`: Active OpenAI API key.
- `SUMMARIZATION_MODEL`: Active model name.
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`: Active tracing configurations.

## Unused Env Variables
- **`GEMINI_API_KEY_EMBEDDING`**: Can be cleaned up if `GEMINI_API_KEY` is always used, but kept for fine-grained credentials.
- **`OPENAI_API_KEY`**: Used only for fallbacks. Must be kept active.

> [!WARNING]
> Never delete credentials/secrets from `.env` files without explicit confirmation.
