"""RSS ingestion must survive session rollbacks mid-feed.

Production 2026-08-18: every source failed with `MissingGreenlet:
greenlet_spawn has not been called` and RSS ingestion produced 0 successes
all day (66 the day before). Mechanism: session.rollback() expires every
instance regardless of expire_on_commit, and _upsert_story_candidate's
idempotency branches roll back as a matter of course — after which the
calling loop's next `source.name` read is a lazy refresh, which async
SQLAlchemy refuses with MissingGreenlet. One expired attribute took out the
whole source's feed, every cycle.

The fix reads the Source's attributes into locals before the loop, so the
ORM instance is never touched after a rollback can have expired it.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.ingestion_service import ingestion_service


class _ExpiringSource:
    """Behaves like a Source whose attributes expire after the first reads.

    Allows one read each of `name` and `rss_url` (the up-front capture), then
    raises on any further attribute access — the same observable behaviour as
    an expired instance in an async session, where the lazy refresh dies.
    """

    def __init__(self) -> None:
        object.__setattr__(self, "_reads", {"name": 0, "rss_url": 0})

    def __getattr__(self, item):
        reads = object.__getattribute__(self, "_reads")
        if item in reads:
            reads[item] += 1
            if reads[item] > 1:
                raise AssertionError(
                    f"source.{item} read again after it may have expired — "
                    "this is the MissingGreenlet path"
                )
            return {"name": "Fox News", "rss_url": "https://feeds.example/rss"}[item]
        raise AttributeError(item)


def _entry(title: str) -> SimpleNamespace:
    return SimpleNamespace(title=title, summary="A long enough description of the event.")


@pytest.mark.asyncio
async def test_loop_survives_source_expiry_after_rollback():
    """Two qualifying entries; the first upsert rolls back (idempotency hit).

    The second iteration and the final log line must not touch the ORM
    instance again.
    """
    source = _ExpiringSource()
    urls = ["https://ex.com/a", "https://ex.com/b"]
    mapping = {
        u: _entry(f"Breaking headline number {i} with plenty of words") for i, u in enumerate(urls)
    }

    upserts: list[str] = []

    async def fake_upsert(*, title, rss_entry_meta, source_name, score, session):
        upserts.append(source_name)
        # Simulate what the idempotency branch does: a full rollback,
        # after which every instance in the session is expired.

    with (
        patch.object(ingestion_service, "_upsert_story_candidate", side_effect=fake_upsert),
        patch.object(ingestion_service, "calculate_metadata_score", return_value=(0.9, {})),
        patch("app.services.gnews_service.gnews_service._incr_metric", AsyncMock()),
    ):
        count = await ingestion_service._ingest_rss_story_first(
            feed_urls=urls,
            url_to_entry=mapping,
            existing_articles={},
            source=source,
            session=AsyncMock(),
        )

    assert count == 2
    assert upserts == ["Fox News", "Fox News"], "the captured name string is what flows down"


@pytest.mark.asyncio
async def test_candidate_race_branch_does_not_full_rollback():
    """The begin_nested() savepoint already undoes the failed INSERT.

    A full session.rollback() on top of it is what expired the Source for
    the rest of the feed. The race branch must not call it.
    """
    import inspect

    src = inspect.getsource(ingestion_service._upsert_story_candidate)
    race_branch = src.split("StoryCandidate race")[1].split("Create the associated")[0]
    assert "session.rollback()" not in race_branch, (
        "the race branch re-grew a full rollback; the savepoint handles it"
    )
