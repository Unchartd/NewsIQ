"""Every failed stage must reach the Failure Center.

There are two stage collectors. StageSpan.__aexit__ has always recorded a
pipeline_failures row on exception; StageTrace (PipelineTraceCollector.stage)
never did, and event_extraction is the only production stage that uses it.

Measured in production before this fix — the gap is entirely one stage:

    stage                   failed  matched  MISSING
    event_extraction           892      113      779
    clustering_incremental      28       28        0
    embedding                   25       25        0
    crawling                     5        5        0
    entity_linking               2        2        0

StageTrace also wrote a second terminal status, "COMPLETED", where StageSpan
writes "success" — 1,128 stage_runs the dashboard's STATUS_CONFIG cannot map,
rendered with no icon and no colour.
"""

import inspect

from app.core.trace import StageSpan, StageTrace


def test_stage_trace_records_a_failure_row():
    """The collector that owns event_extraction must not lose failures."""
    src = inspect.getsource(StageTrace.__aexit__)

    assert "record_pipeline_failure" in src, (
        "StageTrace marks a stage failed without recording it — 87% of "
        "event_extraction failures never reached the Failure Center"
    )

    failure_branch = src[src.index("if exc_type:") :]
    assert failure_branch.index("record_pipeline_failure") < failure_branch.index("_persist_db"), (
        "the failure must be recorded as part of closing the span"
    )


def test_both_collectors_record_failures():
    """Neither collector may silently drop a failure."""
    for collector in (StageSpan.__aexit__, StageTrace.__aexit__):
        assert "record_pipeline_failure" in inspect.getsource(collector), (
            f"{collector.__qualname__} does not record failures"
        )


def test_failure_recording_cannot_mask_the_original_exception():
    """A telemetry problem must not replace the error that caused it."""
    src = inspect.getsource(StageTrace.__aexit__)
    following = src[src.index("record_pipeline_failure") :]
    assert "except Exception" in following, "recording must be guarded"
    assert "logger.error" in following, "a recording failure must be logged, not swallowed"
    assert "return False" in src, "the span must never suppress the original exception"


def test_stage_trace_uses_its_own_ids_not_reset_contextvars():
    """The context tokens are reset earlier in __aexit__; reading them would yield ''."""
    src = inspect.getsource(StageTrace.__aexit__)
    idx = src.index("record_pipeline_failure")
    call = src[idx : idx + 700]
    assert "self.trace_id" in call and "self.run_id" in call, (
        "must use the ids captured at span entry"
    )
    assert "trace_id_ctx.get" not in call, "contextvars are already reset at this point"


def test_only_one_terminal_success_vocabulary_is_written():
    """`completed` was unmappable by the dashboard; `success` is the dominant value."""
    # Match the assignment, not any mention: the comment explaining the change
    # necessarily names the old value.
    code = "\n".join(
        line
        for line in inspect.getsource(StageTrace.__aexit__).splitlines()
        if not line.strip().startswith("#")
    )
    assert 'self.status = "COMPLETED"' not in code, (
        "StageTrace must not write a second terminal status — "
        "stage_runs held both 'success' (29,410) and 'completed' (1,128)"
    )
    assert 'self.status = "SUCCESS"' in code
