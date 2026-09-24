"""The pipeline must survive its AI providers failing.

Audited against production on 2026-09-23, three hours after a fresh start,
with the Gemini free-tier quota spent and the Bedrock key rejected:

* 205 of 603 articles were event_extraction_status='failed'. 'failed' was
  terminal after a single attempt, so none of them could ever be clustered.
* The auto-pause tested only for the legacy gateway's QuotaExhaustedError,
  which the current gateway never raises, so nothing paused.
* Overlapping extraction runs selected the same 20 articles: 860 AI calls for
  241 articles, 2.1 failures per failed article.
* Those runs held 3-4 of the worker's 4 slots for over two hours; discovery
  backed up to 1,822 queued tasks behind them.
* Batches with 20 of 20 articles failed were recorded as 'success'.
* A story whose synthesis died stayed 'pending' for good — nothing retried it.
* The admin "force trigger" restored the pause before its tasks could run.

The unit tests run anywhere. The database tests need the migrated Postgres
that CI provides and are skipped when none is reachable.
"""

import asyncio
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.ai.errors import (
    AIGatewayError,
    AllProvidersFailedError,
    AuthenticationError,
    ValidationError,
)
from app.core.config import settings
from app.llm_gateway.request_manager import QuotaExhaustedError
from app.services.cache_service import cache_service
from app.workers import tasks

# ── Outage classification ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (AllProvidersFailedError("every provider down", provider_outage=True), True),
        (AllProvidersFailedError("a model answered badly", provider_outage=False), False),
        (QuotaExhaustedError("all providers 429"), True),
        (AIGatewayError("unclassified gateway error"), False),
        (ValueError("not an AI error at all"), False),
    ],
)
def test_provider_outage_classification(exc, expected):
    assert tasks._is_provider_outage(exc) is expected


@asynccontextmanager
async def _no_llm_trace(**_kwargs):
    yield SimpleNamespace()


async def _run_stage_with_provider_error(error: Exception) -> None:
    """Drive the real generate_stage with every provider call raising ``error``."""
    from app.ai import gateway as gw

    client = MagicMock()
    client.generate = AsyncMock(side_effect=error)
    route = [(client, "key", {"provider": "gemini", "model": "gemini-3.5-flash-lite"})]
    with (
        patch.object(gw, "filter_healthy", AsyncMock(side_effect=lambda models: models)),
        patch.object(gw, "is_exhausted", AsyncMock(return_value=False)),
        patch.object(gw, "mark_exhausted", AsyncMock()),
        patch.object(gw, "track_llm_call", _no_llm_trace),
        patch.object(gw.asyncio, "sleep", AsyncMock()),
        patch.object(gw.capability_router, "get_model_route", return_value=route),
        patch.object(gw.capability_router, "health_trackers", defaultdict(MagicMock)),
        patch.object(gw.ai_gateway, "_persist_execution_record", AsyncMock()),
    ):
        await gw.ai_gateway.generate_stage(
            stage="event_extraction",
            prompt_variables={
                "title": "t",
                "source_name": "s",
                "published_at": "unknown",
                "content": "c",
            },
        )


async def test_gateway_reports_an_outage_when_no_provider_answers():
    with pytest.raises(AllProvidersFailedError) as info:
        await _run_stage_with_provider_error(AuthenticationError("key rejected"))
    assert info.value.provider_outage is True


async def test_gateway_does_not_call_bad_model_output_an_outage():
    with pytest.raises(AllProvidersFailedError) as info:
        await _run_stage_with_provider_error(ValidationError("schema mismatch"))
    assert info.value.provider_outage is False, (
        "a model answered, so the providers are up — pausing would be wrong"
    )


# ── Pause semantics ──────────────────────────────────────────────────────────


async def test_auto_pause_never_shortens_an_operator_pause():
    """An operator's pause lasts a year; a 1-hour auto-pause must not replace it."""
    await cache_service.set("pipeline_paused", True, ttl=86400 * 365)
    try:
        with patch.object(cache_service, "set", AsyncMock(wraps=cache_service.set)) as set_:
            await tasks._pause_pipeline_for_quota_cooldown("event_extraction")
        set_.assert_not_awaited()
    finally:
        await cache_service.delete("pipeline_paused")


async def test_auto_pause_sets_a_cooldown_when_running():
    await cache_service.delete("pipeline_paused")
    try:
        with patch.object(cache_service, "set", AsyncMock(wraps=cache_service.set)) as set_:
            await tasks._pause_pipeline_for_quota_cooldown("event_extraction")
        set_.assert_awaited_once_with("pipeline_paused", True, ttl=tasks._QUOTA_COOLDOWN_SECONDS)
        assert await cache_service.get("pipeline_paused")
    finally:
        await cache_service.delete("pipeline_paused")


@pytest.mark.parametrize(("paused", "force", "bypass"), [(True, True, True), (False, True, False)])
async def test_forced_trigger_runs_past_the_pause_without_touching_it(paused, force, bypass):
    """The old version cleared the flag, queued the tasks and restored it in
    one request — so the tasks met the restored pause and skipped."""
    from app.api.v1 import admin

    await cache_service.delete("pipeline_paused")
    if paused:
        await cache_service.set("pipeline_paused", True, ttl=86400 * 365)
    try:
        with (
            patch.object(tasks.ingest_news_task, "delay") as ingest,
            patch.object(tasks.cluster_news_task, "delay") as cluster,
            patch.object(cache_service, "delete", AsyncMock(wraps=cache_service.delete)) as dele,
        ):
            ingest.return_value = SimpleNamespace(id="ingest")
            cluster.return_value = SimpleNamespace(id="cluster")
            result = await admin.trigger_pipeline(force=force, _admin=MagicMock())

        ingest.assert_called_once_with(force=bypass)
        cluster.assert_called_once_with(force=bypass)
        dele.assert_not_awaited()
        assert bool(await cache_service.get("pipeline_paused")) is paused
        assert result["forced"] is bypass
    finally:
        await cache_service.delete("pipeline_paused")


def test_forced_tasks_skip_only_the_pause_check():
    import inspect

    for task in (tasks.ingest_news_task, tasks.cluster_news_task):
        assert "if not force and await is_pipeline_paused():" in inspect.getsource(task)


# ── Stage status ─────────────────────────────────────────────────────────────


async def test_a_batch_that_failed_everything_is_recorded_as_failed():
    from app.core.trace import StageTrace

    with (
        patch.object(StageTrace, "_persist_db", AsyncMock()),
        patch.object(StageTrace, "_emit_event", AsyncMock()) as emit,
    ):
        async with StageTrace("event_extraction") as stage:
            stage.mark_failed("All 20 articles in the batch failed extraction.")

    assert stage.status == "FAILED"
    assert stage.errors == ["All 20 articles in the batch failed extraction."]
    assert emit.await_args_list[-1].args == ("StageFailed",)


async def test_an_unmarked_stage_still_succeeds():
    from app.core.trace import StageTrace

    with (
        patch.object(StageTrace, "_persist_db", AsyncMock()),
        patch.object(StageTrace, "_emit_event", AsyncMock()) as emit,
    ):
        async with StageTrace("event_extraction") as stage:
            pass

    assert stage.status == "SUCCESS"
    assert emit.await_args_list[-1].args == ("StageCompleted",)


# ── Extraction concurrency slots ─────────────────────────────────────────────


async def test_extraction_runs_are_capped_and_release_only_their_own_slot():
    cap = settings.EVENT_EXTRACTION_MAX_CONCURRENT_RUNS
    keys = [tasks._EXTRACTION_SLOT_KEY.format(i) for i in range(cap)]
    await cache_service.delete(*keys)
    try:
        slots = [await tasks._acquire_extraction_slot() for _ in range(cap)]
        assert all(slots), "every slot up to the cap must be available"
        assert await tasks._acquire_extraction_slot() is None, "a run beyond the cap must wait"

        # A holder whose slot expired and was taken by another run must not
        # free the new holder's slot when it finally finishes.
        stale_key, _ = slots[0]
        await cache_service.delete(stale_key)
        fresh = await tasks._acquire_extraction_slot()
        assert fresh is not None and fresh[0] == stale_key
        await tasks._release_extraction_slot(slots[0])
        assert await cache_service.get_raw(stale_key) == fresh[1]

        await tasks._release_extraction_slot(fresh)
        assert await tasks._acquire_extraction_slot() is not None
    finally:
        await cache_service.delete(*keys)


# ── Database behaviour (real Postgres) ───────────────────────────────────────


def _database_url() -> str:
    url = settings.DATABASE_URL
    if "?" in url:
        url = url.split("?")[0]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def _postgres_reachable() -> bool:
    try:
        probe = create_async_engine(_database_url(), pool_pre_ping=True)
        try:
            async with probe.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        finally:
            await probe.dispose()
    except Exception:
        return False


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class _Fixture:
    """Rows owned by one test, created newest-first so the claim picks them."""

    def __init__(self) -> None:
        self.engine = create_async_engine(_database_url())
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.source_id = uuid.uuid4()
        self.article_ids: list[uuid.UUID] = []
        self.story_ids: list[uuid.UUID] = []

    async def setup(self) -> None:
        from app.models.models import Source

        async with self.sessions() as s:
            s.add(Source(id=self.source_id, name="test", slug=f"test-{self.source_id}"))
            await s.commit()

    async def add_articles(self, count: int, **overrides) -> list[uuid.UUID]:
        """Create ``count`` claimable articles, each newer than any real one."""
        from app.models.models import Article

        created: list[uuid.UUID] = []
        async with self.sessions() as s:
            for _ in range(count):
                aid = uuid.uuid4()
                offset = len(self.article_ids) + len(created) + 1
                values = {
                    "embedding_status": "completed",
                    "event_extraction_status": "pending",
                    "event_extraction_attempts": 0,
                    # In the future so the claim's newest-first order picks
                    # these before any row another test left behind.
                    "created_at": _now() + timedelta(days=30, minutes=offset),
                    "crawled_at": _now(),
                } | overrides
                s.add(
                    Article(
                        id=aid,
                        source_id=self.source_id,
                        title=f"article {offset}",
                        url=f"https://example.test/{aid}",
                        url_hash=aid.hex,
                        **values,
                    )
                )
                created.append(aid)
            await s.commit()
        self.article_ids.extend(created)
        return created

    async def articles(self) -> dict[uuid.UUID, object]:
        from app.models.models import Article

        async with self.sessions() as s:
            rows = await s.execute(select(Article).where(Article.id.in_(self.article_ids)))
            return {a.id: a for a in rows.scalars().all()}

    async def teardown(self) -> None:
        from app.models.models import Article, Source, Story

        async with self.sessions() as s:
            if self.story_ids:
                await s.execute(delete(Story).where(Story.id.in_(self.story_ids)))
            if self.article_ids:
                await s.execute(delete(Article).where(Article.id.in_(self.article_ids)))
            await s.execute(delete(Source).where(Source.id == self.source_id))
            await s.commit()
        await self.engine.dispose()


@pytest.fixture
async def db():
    if not await _postgres_reachable():
        pytest.skip("live Postgres not reachable — database behaviour is proven in CI")
    fixture = _Fixture()
    await fixture.setup()
    try:
        yield fixture
    finally:
        await fixture.teardown()


@pytest.fixture
def shared_cache():
    """One fake Redis for the test's loop and the task's own loop.

    The cache service keeps a client per event loop, and a Celery task runs on
    a fresh loop — without this, the task would see an empty cache.
    """

    async def _fake_redis_class():
        return type(cache_service._redis)

    loop = asyncio.new_event_loop()
    try:
        fake = loop.run_until_complete(_fake_redis_class())()
    finally:
        loop.close()
    cache_service._redis = fake
    try:
        yield fake
    finally:
        del cache_service._redis


async def _run_in_worker_thread(task) -> list[tuple[str, str, list]]:
    """Run a Celery task the way a worker does: its own thread and event loop.

    Returns (stage, status, errors) for every StageTrace the task finished.
    The suite's autouse fixture stubs PipelineRun persistence, so stage and
    failure rows — which reference the run — are captured here instead of
    being written.
    """
    from app.core.database import engine as app_engine
    from app.core.trace import StageTrace

    finished: list[tuple[str, str, list]] = []

    async def capture(self) -> None:
        finished.append((self.stage, self.status, list(self.errors)))

    def run_async_and_close_pool(coro):
        # tasks.run_async, minus its production-only extras, plus one step:
        # close the pool inside the task's own loop. Otherwise its connections
        # outlive the loop, and later tests could be handed them.
        async def main():
            try:
                return await coro
            finally:
                await app_engine.dispose()

        return asyncio.run(main())

    # Close — on this loop, where they belong — any pooled connections earlier
    # tests left behind, so the task's loop starts with an empty pool.
    await app_engine.dispose()
    with (
        patch.object(tasks, "run_async", run_async_and_close_pool),
        patch("app.core.trace.save_artifact", return_value=None),
        patch.object(StageTrace, "_persist_db", capture),
        patch("app.core.failure_recorder.record_pipeline_failure", AsyncMock()),
    ):
        await asyncio.to_thread(task.run)
    return finished


async def test_concurrent_claims_never_share_an_article(db):
    mine = await db.add_articles(6)
    with patch.object(tasks, "_EXTRACTION_BATCH_SIZE", 3):
        async with db.sessions() as a, db.sessions() as b:
            # A holds its claim uncommitted — exactly the window in which two
            # overlapping runs used to select the same rows.
            first = await tasks._claim_extraction_batch(a)
            second = await tasks._claim_extraction_batch(b)
            await a.rollback()
            await b.rollback()

    assert len(first) == 3 and len(second) == 3
    assert not set(first) & set(second), "two runs claimed the same article"
    assert set(first) | set(second) == set(mine)


async def test_articles_with_null_status_are_claimable(db):
    """`IN ('pending', NULL)` never matches NULL; the claim must not use it."""
    (null_article,) = await db.add_articles(1, event_extraction_status=None)
    with patch.object(tasks, "_EXTRACTION_BATCH_SIZE", 1):
        async with db.sessions() as s:
            claimed = await tasks._claim_extraction_batch(s)
            await s.rollback()
    assert claimed == [null_article]


async def test_a_failure_is_terminal_only_at_the_attempt_cap(db):
    cap = settings.EVENT_EXTRACTION_MAX_ATTEMPTS
    (fresh,) = await db.add_articles(1)
    (last_try,) = await db.add_articles(1, event_extraction_attempts=cap - 1)

    async with db.sessions() as s:
        await tasks._charge_extraction_attempts(s, [fresh, last_try])

    rows = await db.articles()
    assert (rows[fresh].event_extraction_status, rows[fresh].event_extraction_attempts) == (
        "pending",
        1,
    )
    assert (rows[last_try].event_extraction_status, rows[last_try].event_extraction_attempts) == (
        "failed",
        cap,
    )


async def test_released_claims_return_to_pending_uncharged(db):
    ids = await db.add_articles(2, event_extraction_status="processing")
    async with db.sessions() as s:
        await tasks._release_extraction_claims(s, ids)
    for article in (await db.articles()).values():
        assert article.event_extraction_status == "pending"
        assert article.event_extraction_attempts == 0
        assert article.event_extraction_started_at is None


async def test_recovery_keys_on_claim_time_not_crawl_time(db, shared_cache):
    two_hours_ago = _now() - timedelta(hours=2)
    (live,) = await db.add_articles(
        1,
        event_extraction_status="processing",
        event_extraction_started_at=_now(),
        crawled_at=two_hours_ago,
        created_at=two_hours_ago,
    )
    (stale,) = await db.add_articles(
        1,
        event_extraction_status="processing",
        event_extraction_started_at=two_hours_ago,
    )
    (legacy,) = await db.add_articles(
        1,
        event_extraction_status="processing",
        event_extraction_started_at=None,
        crawled_at=two_hours_ago,
        created_at=two_hours_ago,
    )

    await _run_in_worker_thread(tasks.recover_stuck_embeddings_task)

    rows = await db.articles()
    assert rows[live].event_extraction_status == "processing", (
        "an article claimed a moment ago is mid-flight, however old its crawl"
    )
    assert rows[stale].event_extraction_status == "pending"
    assert rows[legacy].event_extraction_status == "pending"


async def test_an_outage_pauses_the_pipeline_and_charges_nobody(db, shared_cache):
    ids = await db.add_articles(5)
    extract = AsyncMock(side_effect=AllProvidersFailedError("all down", provider_outage=True))

    from app.services.event_service import event_service

    with (
        patch.object(tasks, "_EXTRACTION_BATCH_SIZE", len(ids)),
        patch.object(event_service, "extract_events", extract),
        patch.object(tasks.cluster_news_task, "delay") as cluster,
        patch.object(tasks.extract_events_task, "apply_async") as rechain,
    ):
        stages = await _run_in_worker_thread(tasks.extract_events_task)

    assert extract.await_count == tasks._OUTAGE_CONFIRM_STREAK, (
        "once the outage is confirmed the batch must stop calling providers"
    )
    for article in (await db.articles()).values():
        assert article.event_extraction_status == "pending"
        assert article.event_extraction_attempts == 0, "an outage is not the article's fault"
        assert article.event_extraction_started_at is None
    assert await cache_service.get("pipeline_paused"), "the pipeline must pause"
    cluster.assert_not_called()
    rechain.assert_not_called()

    [(stage, status, errors)] = stages
    assert (stage, status) == ("event_extraction", "FAILED"), "an outage batch is not a success"
    assert "No AI provider could answer" in errors[0]


async def test_an_isolated_outage_failure_is_charged_like_any_other(db, shared_cache):
    """If a provider answers for the next article, the first one's 'outage'
    was specific to it — uncharged, it would retry every batch until it aged
    out."""
    cap = settings.EVENT_EXTRACTION_MAX_ATTEMPTS
    # Newest first: the outage article is processed before the others.
    at_cap = (await db.add_articles(1, event_extraction_attempts=cap - 1))[0]
    ordinary = (await db.add_articles(1))[0]
    outage = (await db.add_articles(1))[0]
    titles = {aid: n for n, aid in enumerate((at_cap, ordinary, outage), start=1)}

    async def fake_extract(title, **_kwargs):
        if title == f"article {titles[outage]}":
            raise AllProvidersFailedError("that one request failed", provider_outage=True)
        raise ValueError("unparseable model output")

    from app.services.event_service import event_service

    with (
        patch.object(tasks, "_EXTRACTION_BATCH_SIZE", 3),
        patch.object(event_service, "extract_events", AsyncMock(side_effect=fake_extract)),
        patch.object(tasks.cluster_news_task, "delay"),
        patch.object(tasks.extract_events_task, "apply_async"),
    ):
        stages = await _run_in_worker_thread(tasks.extract_events_task)

    rows = await db.articles()
    assert (rows[outage].event_extraction_status, rows[outage].event_extraction_attempts) == (
        "pending",
        1,
    )
    assert (rows[ordinary].event_extraction_status, rows[ordinary].event_extraction_attempts) == (
        "pending",
        1,
    )
    assert rows[at_cap].event_extraction_status == "failed", "the cap makes it terminal"
    assert not await cache_service.get("pipeline_paused"), "providers answered: no outage"
    [(_, status, errors)] = stages
    assert status == "FAILED" and errors == ["All 3 articles in the batch failed extraction."]


async def test_stuck_pending_stories_are_retried_up_to_the_cap(db, shared_cache):
    from app.models.models import Story, StoryArticle
    from app.services.story_synthesis_service import story_synthesis_orchestrator

    two, one = uuid.uuid4(), uuid.uuid4()
    articles = await db.add_articles(3, event_extraction_status="completed")
    # Just inside the age window and long settled, so these sort ahead of any
    # pending story another test left behind (the task retries oldest first).
    created = _now() - timedelta(hours=settings.PIPELINE_MAX_ARTICLE_AGE_HOURS - 1)
    async with db.sessions() as s:
        for sid in (two, one):
            s.add(
                Story(
                    id=sid,
                    story_status="pending",
                    headline="stuck",
                    created_at=created,
                    updated_at=created,
                )
            )
        await s.flush()
        s.add_all(
            [
                StoryArticle(story_id=two, article_id=articles[0]),
                StoryArticle(story_id=two, article_id=articles[1]),
                StoryArticle(story_id=one, article_id=articles[2]),
            ]
        )
        await s.commit()
    db.story_ids.extend([two, one])

    synth = AsyncMock()
    with patch.object(story_synthesis_orchestrator, "synthesize_story", synth):
        for _ in range(settings.STORY_SYNTHESIS_MAX_RETRIES + 1):
            await _run_in_worker_thread(tasks.retry_pending_story_synthesis_task)

    mine = [c for c in synth.await_args_list if c.kwargs["story_id"] in (two, one)]
    assert [c.kwargs["story_id"] for c in mine] == [two] * settings.STORY_SYNTHESIS_MAX_RETRIES, (
        "only the multi-article story is retried, and only up to the cap"
    )
    assert all(c.kwargs["trigger"] == "retry_pending" for c in mine)
