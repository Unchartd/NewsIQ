"""Stage detail must aggregate, because a stage is not unique within a run.

crawl_url_task opens its own span per URL, so one production run held 2,079
`crawling` rows. The endpoint used scalar_one_or_none(), which raises
MultipleResultsFound — reproduced against production:

    RAISED MultipleResultsFound: Multiple rows were found when one or none was required

That returned HTTP 500 for the two highest-volume stages, 89% of all stage runs.

Returning a single row instead would be worse than the crash: the drawer would
look authoritative while hiding 2,078 attempts. These tests pin the aggregate
behaviour and the backward-compatible single-attempt shape.
"""

import datetime
import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.admin import get_stage_run_details


def _stage_run(status="success", latency=100.0, error=None):
    sr = MagicMock()
    sr.id = uuid.uuid4()
    sr.run_id = uuid.uuid4()
    sr.trace_id = uuid.uuid4()
    sr.stage = "crawling"
    sr.status = status
    sr.started_at = datetime.datetime(2026, 8, 12, 13, 26, 5)
    sr.completed_at = datetime.datetime(2026, 8, 12, 13, 26, 9)
    sr.latency_ms = latency
    sr.retry_count = 0
    sr.error = error
    sr.error_type = None
    sr.story_id = None
    sr.article_id = None
    sr.metadata_payload = {"input": {}, "output": {}}
    return sr


def _session(*, count, status_counts, representative, attempts, traces=()):
    """Drive the endpoint's five queries in order."""
    agg = MagicMock()
    agg.one.return_value = (
        count,
        7_583_631.99,  # sum latency
        3647.73,  # avg
        9000.0,  # max
        datetime.datetime(2026, 8, 12, 13, 26, 5),
        datetime.datetime(2026, 8, 12, 14, 7, 49),
        0,  # retries
    )

    counts = MagicMock()
    counts.all.return_value = list(status_counts.items())

    rep = MagicMock()
    rep.scalars.return_value.first.return_value = representative

    att = MagicMock()
    att.scalars.return_value.all.return_value = attempts

    llm = MagicMock()
    llm.scalars.return_value.all.return_value = list(traces)

    session = AsyncMock()
    session.execute.side_effect = [agg, counts, rep, att, llm]
    return session


@pytest.mark.asyncio
async def test_thousands_of_attempts_do_not_raise():
    """The exact production shape: 2,079 crawling rows under one run."""
    rep = _stage_run()
    res = await get_stage_run_details(
        run_id=uuid.uuid4(),
        stage="crawling",
        limit=5,
        offset=0,
        _admin=None,
        db=_session(
            count=2079,
            status_counts={"success": 2079},
            representative=rep,
            attempts=[rep] * 5,
        ),
    )

    assert res["attempt_count"] == 2079
    assert res["is_aggregated"] is True
    assert res["status_counts"] == {"success": 2079}
    assert res["attempts_page"]["total"] == 2079
    assert len(res["attempts"]) == 5, "attempts must be paged, not truncated to one"


@pytest.mark.asyncio
async def test_a_single_failure_among_successes_is_not_hidden():
    """Worst status wins — otherwise a stage with a failure reports as healthy."""
    res = await get_stage_run_details(
        run_id=uuid.uuid4(),
        stage="crawling",
        limit=50,
        offset=0,
        _admin=None,
        db=_session(
            count=1000,
            status_counts={"success": 999, "failed": 1},
            representative=_stage_run(status="failed", error="boom"),
            attempts=[],
        ),
    )

    assert res["status"] == "failed", "a stage with any failed attempt must not report success"
    assert res["status_counts"]["failed"] == 1


@pytest.mark.asyncio
async def test_single_attempt_keeps_the_original_response_shape():
    """Stages that ran once must be unchanged for existing consumers."""
    rep = _stage_run(latency=250.0)
    res = await get_stage_run_details(
        run_id=uuid.uuid4(),
        stage="embedding",
        limit=50,
        offset=0,
        _admin=None,
        db=_session(
            count=1,
            status_counts={"success": 1},
            representative=rep,
            attempts=[rep],
        ),
    )

    assert res["is_aggregated"] is False
    assert res["attempt_count"] == 1
    assert res["latency_ms"] == 250.0, "a single attempt reports its own latency, not the sum"
    assert res["status"] == "success"


@pytest.mark.asyncio
async def test_aggregated_latency_is_the_sum_not_one_attempt():
    rep = _stage_run(latency=100.0)
    res = await get_stage_run_details(
        run_id=uuid.uuid4(),
        stage="crawling",
        limit=50,
        offset=0,
        _admin=None,
        db=_session(
            count=2079, status_counts={"success": 2079}, representative=rep, attempts=[rep]
        ),
    )
    assert res["latency_ms"] == pytest.approx(7_583_631.99)
    assert res["aggregate"]["avg_latency_ms"] == pytest.approx(3647.73)


@pytest.mark.asyncio
async def test_stage_that_never_ran_still_returns_404():
    """Absent must stay 404 — it is how the UI distinguishes 'no data' from 'broken'."""
    agg = MagicMock()
    agg.one.return_value = (0, None, None, None, None, None, None)
    session = AsyncMock()
    session.execute.side_effect = [agg]

    with pytest.raises(HTTPException) as exc:
        await get_stage_run_details(
            run_id=uuid.uuid4(),
            stage="summary_generation",
            limit=50,
            offset=0,
            _admin=None,
            db=session,
        )
    assert exc.value.status_code == 404


def test_endpoint_never_assumes_a_unique_stage_row():
    """Regression guard on the exact call that produced the 500."""
    src = inspect.getsource(get_stage_run_details)
    assert "scalar_one_or_none" not in src, (
        "(run_id, stage) is not unique — scalar_one_or_none raises MultipleResultsFound"
    )


def test_llm_traces_are_capped():
    """A run with thousands of spans would otherwise serialise unbounded prompt text."""
    src = inspect.getsource(get_stage_run_details)
    assert "_LLM_TRACE_MAX" in src and "llm_traces_truncated" in src, (
        "trace list must be bounded and the truncation surfaced"
    )
