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


class _ExpiredReadError(RuntimeError):
    """Stands in for sqlalchemy.exc.MissingGreenlet in this double."""


class _ExpiringSource:
    """Behaves like a Source whose attributes expire after the first reads.

    Allows one read each of `name` and `rss_url` (the up-front capture), then
    raises on any further access — the same observable behaviour as an
    expired instance in an async session, where the lazy refresh dies.
    """

    _values = {"name": "Fox News", "rss_url": "https://feeds.example/rss"}

    def __init__(self) -> None:
        self._reads = dict.fromkeys(self._values, 0)

    def _read(self, item: str) -> str:
        self._reads[item] += 1
        if self._reads[item] > 1:
            raise _ExpiredReadError(
                f"source.{item} read again after it may have expired — "
                "this is the MissingGreenlet path"
            )
        return self._values[item]

    @property
    def name(self) -> str:
        return self._read("name")

    @property
    def rss_url(self) -> str:
        return self._read("rss_url")


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
async def test_candidate_race_branch_rolls_back_before_requerying():
    """A failed flush poisons the session, savepoint or not.

    Every statement after it raises PendingRollbackError until rollback()
    runs — removing this rollback (briefly shipped in v1.42.1) made the
    race branch's own winner re-query fail. The rollback must come BEFORE
    the re-query; the Source-expiry side effect it carries is neutralized
    by the caller reading attributes into locals up front (previous test).
    """
    import inspect

    src = inspect.getsource(ingestion_service._upsert_story_candidate)
    race_branch = src.split("StoryCandidate race")[1].split("Create the associated")[0]
    rollback_at = race_branch.find("session.rollback()")
    requery_at = race_branch.find("select(StoryCandidate)")
    assert rollback_at != -1, "the race branch must reset the poisoned session"
    assert requery_at != -1, "the race branch must re-query the winner"
    assert rollback_at < requery_at, "rollback must precede the re-query"


@pytest.mark.asyncio
async def test_event_extraction_loop_refetches_after_rollback():
    """Third instance of the expiry class, in extract_events_task.

    The clustering-failure branch rolls the session back mid-batch; the next
    iteration's first attribute read on a pre-loaded Article then raised
    MissingGreenlet and failed the whole task (observed post-v1.42.2). The
    loop must iterate over captured ids and session.get() each article fresh.
    """
    import inspect

    from app.workers import tasks

    src = inspect.getsource(tasks.extract_events_task)
    assert "article_ids = [article.id for article in articles]" in src, (
        "ids must be captured before the loop"
    )
    assert "for article_id in article_ids:" in src, "the loop must iterate ids, not instances"
    assert "session.get(Article, article_id)" in src, (
        "each iteration must re-fetch, surviving a prior rollback"
    )


def test_every_celery_module_uses_the_pool_disposing_run_async():
    """A second run_async that skipped pool disposal killed all digest tasks.

    tasks.run_async disposes the SQLAlchemy connection pool inherited from the
    prefork parent, so the new event loop gets fresh asyncpg connections; its
    own docstring calls that CRITICAL. digest_tasks.py carried a private copy
    that called asyncio.run() directly, so every digest task raised
    MissingGreenlet on its first query. One canonical helper, imported.
    """
    import pathlib
    import re

    workers = pathlib.Path(__file__).resolve().parents[1] / "app" / "workers"
    definitions = [
        p.name
        for p in workers.glob("*.py")
        if re.search(r"^def run_async\(", p.read_text(encoding="utf-8"), re.M)
    ]
    assert definitions == ["tasks.py"], (
        f"run_async is defined in {definitions}; every worker module must import "
        "the pool-disposing helper from app.workers.tasks instead of redefining it"
    )
