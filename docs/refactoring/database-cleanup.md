# Database Cleanup Report

An audit of the database models in [models.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/models/models.py) and [observability_models.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/models/observability_models.py).

## Safe to Remove
None. All tables defined in `models.py` are active parts of the event-centric architecture:
- `users`, `user_preferences`, `sessions`, `oauth_accounts`, `user_categories`, `user_locations`: Auth and user settings.
- `categories`, `sources`, `articles`: Ingested data.
- `article_events`, `article_entities`: Event/Entity extraction results.
- `stories`, `story_articles`, `story_timeline_events`, `story_entities`, `story_tags`, `story_source_coverage`, `story_differences`, `story_contradictions`: Story synthesis results.
- `pipeline_runs`, `stage_spans`, `llm_calls`: Observability logging.

## Requires Migration
None. All tables have active Alembic migration states and are currently matched.

## Requires Backup
Before executing any direct cleanup on tables or databases, the production database should be fully backed up using `pg_dump`.
- Command: `pg_dump -U postgres -d newsiq_db > backup.sql`
