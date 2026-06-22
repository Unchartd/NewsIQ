# Celery Cleanup Report

An audit of the Celery tasks and schedules.

## Tasks and Queues
All tasks in [tasks.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/tasks.py) and [digest_tasks.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/workers/digest_tasks.py) are active:
- `ingest_news_task`: RSS Ingestion (Every 5 minutes)
- `ingest_gnews_task`: GNews API Ingestion (Every 30 minutes)
- `process_pending_embeddings_task`: Embeds articles in Qdrant (Chained/Triggered)
- `extract_events_task`: Event Extraction (Every 10 minutes or Chained)
- `cluster_news_task`: Batch Clustering (Every 10 minutes or Chained)
- `collect_queue_metrics_task`: Monitoring metrics (Every 1 minute)
- `cleanup_expired_sessions_task`: Session purging (Daily at midnight)
- `process_hourly_digests_task`: Digest compilation & delivery (Hourly)

## Deprecated Tasks
- There are no deprecated/unused Celery task definitions or schedulers.
