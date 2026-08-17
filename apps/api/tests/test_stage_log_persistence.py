"""Stage logging must be cheap, bounded, honest, and durable past 24 hours.

The structlog processor that writes stage logs ran inline on every log call,
including inside async worker code, and called redis.from_url() **per log line**
— a fresh connection, never pooled and never closed, followed by three separate
blocking round trips. At 8,412 stage runs a day this was the largest avoidable
cost in the telemetry path, and `except Exception: pass` meant a broken Redis
was invisible.

Separately, stage logs live only in Redis under a 24-hour TTL and there is no
durable store — `error_logs` exists as a table and holds zero rows. A run that
failed yesterday had no logs today, which is exactly when they are wanted.
"""

import inspect
from unittest.mock import MagicMock, patch

from app.core import structured_logging as sl
from app.core.trace import StageSpan, StageTrace

# conftest replaces the module-level processor with a no-op so the whole suite
# never touches Redis. These tests are about that processor, so they call the
# original, which conftest preserves.
_process = sl._real_store_and_publish_log


def _event(**kw):
    e = {"run_id": "run-1", "stage": "crawling", "event": "hello", "level": "info"}
    e.update(kw)
    return e


# ── cost ──────────────────────────────────────────────────────────────────────


def test_client_is_created_once_and_reused():
    """A connection per log line was the defect."""
    sl._redis_log_client = None
    with patch("redis.from_url", return_value=MagicMock()) as from_url:
        _process(None, "info", _event())
        _process(None, "info", _event())
        _process(None, "info", _event())
    assert from_url.call_count == 1, "the Redis client must be pooled, not rebuilt per log line"
    sl._redis_log_client = None


def test_writes_are_pipelined_into_one_round_trip():
    sl._redis_log_client = client = MagicMock()
    pipe = client.pipeline.return_value
    try:
        _process(None, "info", _event())
        assert pipe.execute.call_count == 1, "all commands must go in a single round trip"
        assert pipe.rpush.called and pipe.publish.called and pipe.expire.called
    finally:
        sl._redis_log_client = None


def test_log_list_is_bounded():
    """A stage logging in a loop would otherwise grow an unbounded Redis list."""
    sl._redis_log_client = client = MagicMock()
    pipe = client.pipeline.return_value
    try:
        _process(None, "info", _event())
        assert pipe.ltrim.called, "the list must be trimmed or it grows without limit"
    finally:
        sl._redis_log_client = None


# ── honesty ───────────────────────────────────────────────────────────────────


def test_a_broken_redis_is_reported_not_swallowed():
    sl._redis_log_client = client = MagicMock()
    client.pipeline.side_effect = RuntimeError("redis down")
    sl._redis_log_broken = False
    sl._redis_log_failures = 0
    try:
        with patch.object(sl.logging, "getLogger") as get_logger:
            _process(None, "info", _event())
            assert get_logger.return_value.warning.called, (
                "`except Exception: pass` is what made a broken Redis invisible"
            )
    finally:
        sl._redis_log_client = None
        sl._redis_log_broken = False


def test_logging_failure_never_breaks_the_caller():
    sl._redis_log_client = client = MagicMock()
    client.pipeline.side_effect = RuntimeError("redis down")
    try:
        out = _process(None, "info", _event())
        assert out["event"] == "hello", "the processor must still return the event dict"
    finally:
        sl._redis_log_client = None
        sl._redis_log_broken = False


def test_reporting_does_not_recurse_through_structlog():
    """Logging the failure via structlog would re-enter this same processor."""
    code = "\n".join(
        line
        for line in inspect.getsource(sl._report_log_failure).splitlines()
        if not line.strip().startswith("#")
    )
    assert "logging.getLogger" in code
    # The docstring names structlog to explain the risk; what matters is that it
    # is never called here.
    assert "structlog.get_logger" not in code


def test_logs_outside_a_stage_span_are_skipped():
    sl._redis_log_client = client = MagicMock()
    try:
        _process(None, "info", {"event": "no context"})
        assert not client.pipeline.called
    finally:
        sl._redis_log_client = None


# ── durability ────────────────────────────────────────────────────────────────


def test_snapshot_returns_decoded_tail():
    sl._redis_log_client = client = MagicMock()
    client.lrange.return_value = [b"line one", "line two"]
    try:
        assert sl.snapshot_stage_logs("run-1", "crawling") == ["line one", "line two"]
    finally:
        sl._redis_log_client = None


def test_snapshot_is_bounded():
    """This ends up in a JSONB column; a retry loop can produce a lot of output."""
    sig = inspect.signature(sl.snapshot_stage_logs)
    assert sig.parameters["limit"].default <= 1000


def test_both_collectors_snapshot_logs_when_a_stage_fails():
    """Redis drops them after 24h — the failure record must carry its own copy."""
    assert "_snapshot_logs" in inspect.getsource(StageSpan.__aexit__)
    assert "snapshot_stage_logs" in inspect.getsource(StageTrace.__aexit__)


def test_snapshot_only_happens_on_the_failure_path():
    """Every successful stage carrying a log tail would bloat stage_runs."""
    src = inspect.getsource(StageSpan.__aexit__)
    failure_branch = src[src.index("if exc_type:") : src.index("else:")]
    assert "_snapshot_logs" in failure_branch


def test_logs_endpoint_falls_back_to_the_persisted_tail():
    from app.api.v1.admin import get_stage_run_logs

    src = inspect.getsource(get_stage_run_logs)
    assert "logs_tail" in src, (
        "past the 24h TTL the endpoint returned an empty list, indistinguishable "
        "from a stage that logged nothing"
    )
