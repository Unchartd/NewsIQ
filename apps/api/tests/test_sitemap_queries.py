"""Regression tests for the queries the sitemaps depend on.

Production carried an empty news sitemap and a story-less main sitemap for
months while stories flowed at 40-100/day, because both sitemap fetchers
swallow failures into an empty list:

* the main sitemap asked for ``limit=200`` against an endpoint capped at
  ``le=100`` — HTTP 422 on every request;
* the news sitemap sent ``after=...T00:00:00.000Z`` — the tz-aware datetime
  reached asyncpg, which refuses to compare it against the naive UTC
  timestamp columns, and the request 500'd.

The web side now requests 100 and logs failures; this file pins the API side:
the exact query shapes both sitemaps send must succeed.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.api.v1.stories import list_stories


class _CapturingSession:
    """Records the statement and returns an empty result set."""

    def __init__(self) -> None:
        self.stmt = None

    async def execute(self, stmt):  # noqa: ANN001 - test double
        self.stmt = stmt
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res


def _datetime_binds(stmt) -> list[datetime]:
    return [v for v in stmt.compile().params.values() if isinstance(v, datetime)]


async def _call(session, *, sort: str, after: datetime):
    """Invoke the endpoint directly, spelling out every FastAPI default.

    Calling the function outside FastAPI leaves unpassed params as Query
    sentinel objects, which the body would then treat as values.
    """
    return await list_stories(
        category=None,
        country=None,
        state=None,
        city=None,
        q=None,
        status="active",
        trending=False,
        sort=sort,
        after=after,
        limit=100,
        offset=0,
        db=session,
    )


@pytest.mark.asyncio
async def test_tz_aware_after_is_coerced_before_reaching_the_driver():
    """The news sitemap's `after` must never hit asyncpg tz-aware."""
    session = _CapturingSession()
    aware = datetime(2026, 8, 16, 0, 0, 0, tzinfo=UTC)

    await _call(session, sort="first_seen_at", after=aware)

    binds = _datetime_binds(session.stmt)
    assert binds, "the after filter must produce a datetime bind"
    for value in binds:
        assert value.tzinfo is None, (
            f"tz-aware datetime {value!r} would make asyncpg raise and the "
            "request 500 — the news sitemap rendered empty because of this"
        )
    # Coercion must preserve the instant, not just strip the marker.
    assert binds[0] == datetime(2026, 8, 16, 0, 0, 0)


@pytest.mark.asyncio
async def test_naive_after_passes_through_unchanged():
    session = _CapturingSession()
    naive = datetime(2026, 8, 16, 12, 30, 0)

    await _call(session, sort="updated_at", after=naive)

    assert naive in _datetime_binds(session.stmt)


def test_the_main_sitemap_request_respects_the_endpoint_cap():
    """sitemap.ts asks for `limit=100`; the endpoint caps at le=100.

    The old request said 200 and every response was a 422 the sitemap
    swallowed. If the cap is ever lowered below what the sitemap sends,
    this pins the contract from the API side.
    """
    import inspect

    from annotated_types import Le

    sig = inspect.signature(list_stories)
    limit_default = sig.parameters["limit"].default
    caps = [m.le for m in limit_default.metadata if isinstance(m, Le)]
    assert caps and caps[0] >= 100, (
        "the sitemap requests limit=100; lowering the cap below that "
        "silently empties the sitemap again"
    )
