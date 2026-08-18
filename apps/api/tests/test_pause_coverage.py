"""Which Celery tasks "Pause Pipeline" must actually stop.

Verified against production before this was fixed: pausing the pipeline set
the Redis flag, `is_pipeline_paused()` returned True, and ingestion and event
extraction logged "Skipping" — while `poll_discovery_retries_task` and
`poll_story_candidate_timeouts_task` kept executing. Only 6 of 23 tasks
consulted the flag, and the uncovered set was the billed path: `crawling` was
6,803 of one 24h window's ~11,500 stage runs and `discovery_search` another
1,848. An operator hitting Pause to protect a monthly Firecrawl/Tavily
allowance kept spending it.

The split is a policy decision, so both halves are pinned. Work that costs
money or advances the pipeline must be gated; observability, recovery,
cleanup and explicit admin actions must NOT be — pausing those would blind
the system exactly when someone has stopped it to investigate.
"""

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "app" / "workers" / "tasks.py"


def _task_bodies() -> dict[str, str]:
    """Map celery task name -> source body, read from disk.

    Read as text rather than via inspect: the guard's placement inside the
    inner `_run` closure is what matters, and importing gives no cheaper way
    to see it.
    """
    src = _SRC.read_text(encoding="utf-8")
    marks = [
        (m.start(), m.group(1).replace("app.workers.tasks.", ""))
        for m in re.finditer(r'@celery_app\.task\(name="([^"]+)"', src)
    ]
    marks.append((len(src), "__end__"))
    return {name: src[start : marks[i + 1][0]] for i, (start, name) in enumerate(marks[:-1])}


# Spends provider credits or advances pipeline state.
MUST_PAUSE = [
    "ingest_news_task",
    "ingest_gnews_task",
    "process_pending_embeddings_task",
    "extract_events_task",
    "cluster_news_task",
    "reconcile_duplicate_stories_task",
    "dispatch_story_candidate_task",
    "discovery_search_task",
    "discovery_crawl_task",
    "poll_discovery_retries_task",
    "poll_story_candidate_timeouts_task",
    "discovery_grouping_task",
]

# Observability, recovery, cleanup, and operator-initiated actions.
MUST_NOT_PAUSE = [
    "collect_queue_metrics_task",
    "aggregate_pipeline_metrics_task",
    "export_run_to_otel_task",
    "purge_observability_data_task",
    "reap_stuck_pipeline_runs_task",
    "recover_stuck_embeddings_task",
    "retire_stale_unprocessed_articles_task",
    "cleanup_discovery_tasks_task",
    # Time-based housekeeping that costs nothing to run and does not
    # depend on the pipeline being live.
    "evaluate_story_lifecycles_task",
    "replay_story_task",
    "replay_story_stage_task",
]


@pytest.mark.parametrize("task", MUST_PAUSE)
def test_billed_and_advancing_tasks_honour_pause(task):
    body = _task_bodies().get(task)
    assert body is not None, f"{task} is no longer a registered celery task"
    assert "is_pipeline_paused()" in body, (
        f"{task} ignores the pause flag — 'Pause Pipeline' would not stop it"
    )


@pytest.mark.parametrize("task", MUST_NOT_PAUSE)
def test_observability_and_recovery_keep_running_while_paused(task):
    body = _task_bodies().get(task)
    assert body is not None, f"{task} is no longer a registered celery task"
    assert "is_pipeline_paused()" not in body, (
        f"{task} now stops when paused; observability, recovery and cleanup "
        "must keep working while an operator inspects a paused pipeline"
    )


def test_the_guard_precedes_any_database_write():
    """A skipped task must leave its row re-dispatchable.

    poll_discovery_retries_task re-dispatches PENDING tasks whose
    next_retry_at has passed, so guarding before any mutation means paused
    work resumes by itself. Guarding *after* a status write would strand it.
    """
    bodies = _task_bodies()
    for task in ("discovery_search_task", "discovery_crawl_task"):
        body = bodies[task]
        guard_at = body.index("is_pipeline_paused()")
        for write in ("session.add(", "session.commit()", "session.flush()"):
            if write in body:
                assert guard_at < body.index(write), (
                    f"{task} writes to the session before checking pause; "
                    "a paused run would strand the row"
                )


def test_every_registered_task_has_a_declared_policy():
    """New tasks must be classified deliberately, not silently left ungated."""
    known = set(MUST_PAUSE) | set(MUST_NOT_PAUSE)
    registered = set(_task_bodies())
    unclassified = registered - known
    assert not unclassified, (
        f"tasks with no declared pause policy: {sorted(unclassified)} — add each "
        "to MUST_PAUSE or MUST_NOT_PAUSE in this file"
    )
