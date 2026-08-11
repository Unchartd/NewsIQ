"""Regression tests for the shared article age window.

Clustering bounded eligibility at 72h while embedding and event extraction had
no bound at all. The stages therefore disagreed about what was worth
processing: after the 2026-08 outage, 11,343 stale articles were queued to
consume embedding quota and one LLM call each for event extraction, only to be
rejected by clustering as too old. Enough to hit Gemini rate limits, for zero
downstream benefit.

The invariant these tests protect: every stage that spends money on an article
uses the same age bound as the stage that ultimately consumes the result.
"""

import inspect
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.services.clustering_service import clustering_service
from app.workers import tasks


def test_all_processing_stages_share_one_age_setting():
    """Embedding, extraction and clustering must read the same setting.

    If these ever diverge, an earlier stage pays to process articles a later
    stage will discard — the exact failure this suite exists to prevent.
    """
    embed_src = inspect.getsource(tasks.process_pending_embeddings_task)
    extract_src = inspect.getsource(tasks.extract_events_task)
    cluster_src = inspect.getsource(clustering_service._run_batch_clustering_locked)

    assert "_article_age_cutoff()" in embed_src, "embedding is not age-bounded"
    assert "_article_age_cutoff()" in extract_src, "event extraction is not age-bounded"
    assert "PIPELINE_MAX_ARTICLE_AGE_HOURS" in cluster_src, (
        "clustering no longer reads the shared age setting"
    )

    cutoff_src = inspect.getsource(tasks._article_age_cutoff)
    assert "PIPELINE_MAX_ARTICLE_AGE_HOURS" in cutoff_src


def test_age_cutoff_matches_the_configured_window():
    cutoff = tasks._article_age_cutoff()
    expected = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        hours=settings.PIPELINE_MAX_ARTICLE_AGE_HOURS
    )
    assert cutoff.tzinfo is None, "article timestamps are stored naive UTC"
    assert abs((cutoff - expected).total_seconds()) < 5


def test_backfill_can_override_the_window_without_changing_config():
    """A one-off backfill must not require mutating a global setting.

    ~4,151 articles were fully processed before the bound existed and would
    otherwise be stranded. Overriding per call keeps steady-state behaviour
    correct while letting that sunk cost be recovered once.
    """
    sig = inspect.signature(clustering_service.run_batch_clustering)
    assert "max_age_hours" in sig.parameters
    assert sig.parameters["max_age_hours"].default is None, (
        "the override must default to the shared setting, not a hardcoded value"
    )

    locked_sig = inspect.signature(clustering_service._run_batch_clustering_locked)
    assert "max_age_hours" in locked_sig.parameters, "override is not threaded through the lock"


def test_stale_articles_are_retired_not_left_pending():
    """Aged-out articles get a terminal 'skipped' state, distinct from 'failed'.

    Leaving them 'pending' makes queue depth permanently overstate real
    backlog — 11,343 rows no dashboard could tell apart from genuine work.
    """
    src = inspect.getsource(tasks.retire_stale_unprocessed_articles_task)
    assert 'embedding_status="skipped"' in src
    assert 'event_extraction_status="skipped"' in src
    assert "_article_age_cutoff()" in src, "retirement must use the same window"
    # Aging out is not a failure and must not be recorded as one — "failed" is
    # already terminal and would conflate a dead pipeline with a bad article.
    assert 'embedding_status="failed"' not in src
    assert 'event_extraction_status="failed"' not in src


def test_retire_task_is_scheduled():
    """An unscheduled maintenance task is the same as one that does not exist.

    recover_stuck_embeddings_task existed but was never added to the beat
    schedule, which is why 53 production articles sat in 'processing' forever.
    """
    from app.workers.celery_app import celery_app

    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "app.workers.tasks.retire_stale_unprocessed_articles_task" in scheduled
    assert "app.workers.tasks.recover_stuck_embeddings_task" in scheduled
