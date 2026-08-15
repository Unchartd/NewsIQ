"""Runs whose worker died must not stay `running` forever.

Nothing reconciled a span whose worker was killed mid-stage. Measured in
production: 7 pipeline_runs and 3 stage_runs had been `running` for over an
hour, and the dashboard polls those as live work indefinitely while the run's
successful/failed stage counters never settle.
"""

import inspect

from app.workers import tasks
from app.workers.celery_app import celery_app


def test_reaper_task_exists_and_is_scheduled():
    assert hasattr(tasks, "reap_stuck_pipeline_runs_task")

    schedule = celery_app.conf.beat_schedule
    entries = [
        e
        for e in schedule.values()
        if e.get("task") == "app.workers.tasks.reap_stuck_pipeline_runs_task"
    ]
    assert entries, "the reaper is never scheduled, so nothing would run it"


def test_reaper_closes_both_runs_and_stages():
    """A stuck stage and a stuck run are separate rows; both hang."""
    src = inspect.getsource(tasks.reap_stuck_pipeline_runs_task)
    assert "StageRunModel" in src and "PipelineRunModel" in src


def test_abandoned_work_is_marked_failed_with_a_reason():
    """Marking it success would silently turn a lost run into a healthy one."""
    src = inspect.getsource(tasks.reap_stuck_pipeline_runs_task)
    assert 'status="failed"' in src, "an abandoned run is not a successful one"
    assert "AbandonedStage" in src, "the cause must be distinguishable from a real failure"
    assert "reason" in src


def test_reaper_only_touches_rows_older_than_the_threshold():
    """A stage legitimately running right now must not be reaped."""
    src = inspect.getsource(tasks.reap_stuck_pipeline_runs_task)
    assert "started_at < cutoff" in src
    assert "stale_after_minutes" in src


def test_reaper_sets_a_completion_time():
    """Without one, latency and duration stay unknown forever."""
    src = inspect.getsource(tasks.reap_stuck_pipeline_runs_task)
    assert "completed_at" in src
