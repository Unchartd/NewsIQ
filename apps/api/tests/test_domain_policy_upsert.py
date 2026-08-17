"""The per-domain policy update must be one atomic statement.

_update_domain_policy runs once per provider attempt — up to three times for
every crawled URL, and there were 23,216 crawls in the measured window. It opened
a fresh session and did SELECT, then INSERT or UPDATE, then COMMIT: three round
trips plus a connection checkout each time.

It was also a read-modify-write against a uniquely-indexed column, so two workers
reaching a new domain together could both miss the SELECT and both insert. The
exception was caught and merely logged, so the losing update was silently
dropped. (No such failure appears in 48h of production logs — the per-domain
pacer makes it rare — but an upsert removes the possibility rather than relying
on timing.)

Verified against real Postgres before this was committed: the insert path
populates the primary key and updated_at from their Python-side defaults, a
failure lowers the moving average (1.0 -> 0.9) without moving
average_content_length or last_success_provider, and one provider's attempt does
not disturb another's rate.
"""

import inspect

from app.services.extraction_manager import ExtractionManager

# conftest replaces this method with an AsyncMock so the suite never opens a
# database session. These tests are about the statement it builds, so they call
# the original, which conftest preserves.
_real_update = ExtractionManager._real_update_domain_policy


def _compile(provider: str, success: bool, latency: float = 100.0, length: int = 1000) -> str:
    """Compile the statement the method builds, without executing it."""
    import asyncio
    from unittest.mock import patch

    captured: dict[str, str] = {}

    class _Session:
        async def execute(self, stmt):
            captured["sql"] = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        async def commit(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    with patch("app.core.database.async_session_factory", lambda: _Session()):
        asyncio.run(
            _real_update(
                ExtractionManager(),
                domain="bbc.com",
                provider=provider,
                success=success,
                latency_ms=latency,
                content_length=length,
            )
        )
    return captured["sql"]


def test_it_is_a_single_upsert_not_a_read_modify_write():
    src = inspect.getsource(_real_update)
    assert "on_conflict_do_update" in src, (
        "a SELECT-then-write cannot be atomic against a unique column"
    )
    assert "scalar_one_or_none" not in src, "the read-modify-write must be gone"


def test_only_one_statement_is_executed():
    sql = _compile("local", True)
    assert sql.count("INSERT INTO") == 1
    assert "ON CONFLICT (domain) DO UPDATE" in sql


def test_moving_average_is_computed_in_sql_against_the_existing_row():
    sql = _compile("local", True)
    assert "domain_extraction_policies.local_success_rate * 0.9" in sql, (
        "the EMA must fold into the stored value, not overwrite it"
    )


def test_only_the_attempted_provider_moves():
    """A local attempt must not touch the Tavily or Firecrawl statistics."""
    sql = _compile("local", True)
    assert "local_attempts = (domain_extraction_policies.local_attempts + 1)" in sql
    assert "tavily_attempts" not in sql.split("DO UPDATE")[1], (
        "an untouched provider's attempt count must not be written"
    )
    assert "tavily_success_rate = domain_extraction_policies.tavily_success_rate" in sql, (
        "an untouched provider's rate must be carried through unchanged"
    )


def test_confidence_reflects_the_new_rates_not_the_old_ones():
    """Postgres cannot see another column's new value, so it must be inlined."""
    sql = _compile("local", True)
    update = sql.split("DO UPDATE")[1]
    confidence = update.split("confidence_score =")[1]
    assert "local_success_rate * 0.9" in confidence, (
        "confidence was computed from the pre-update rate"
    )


def test_a_failure_does_not_move_content_length_or_last_success():
    """Neither means anything for an extraction that returned nothing."""
    update = _compile("local", False).split("DO UPDATE")[1]
    assert "average_content_length" not in update
    assert "last_success_provider" not in update


def test_a_success_records_the_provider_and_content_length():
    update = _compile("local", True).split("DO UPDATE")[1]
    assert "average_content_length" in update
    assert "last_success_provider = 'local'" in update


def test_latency_always_updates():
    """Latency is meaningful whether or not the extraction produced content."""
    for success in (True, False):
        update = _compile("local", success).split("DO UPDATE")[1]
        assert "average_latency = (domain_extraction_policies.average_latency * 0.9" in update


def test_an_unknown_provider_does_not_corrupt_counters():
    """Defensive: a new provider name must not write a bogus attempts column."""
    update = _compile("some_new_provider", True).split("DO UPDATE")[1]
    for column in ("local_attempts", "tavily_attempts", "firecrawl_attempts"):
        assert f"{column} =" not in update
