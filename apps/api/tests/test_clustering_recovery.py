"""Regression tests for the defects that stopped story creation entirely.

Each of these was independently sufficient to reduce the pipeline to
"N articles -> 0 stories", and all were live in production simultaneously:

  BUG-01  batch clustering read discovery_queue, whose producer was deleted
  BUG-02  Story had no story_embedding column, so Stage B cosine was always 0.0
  BUG-03  stories were created "emerging" but candidate retrieval excluded it
  BUG-06  synthesis committed inside a SAVEPOINT, raising and half-persisting
  BUG-07  a session-scoped advisory lock was stranded by intervening commits
"""

import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.services.clustering_service import clustering_service

# ── BUG-01: eligibility no longer depends on the orphaned queue ──────────────


def test_batch_clustering_does_not_read_discovery_queue():
    """The only automated story creator must not depend on an unwritten table."""
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    assert "DiscoveryQueue" not in src, "batch clustering still joins the orphaned queue"
    assert "DiscoveryState" not in src


def test_batch_clustering_selects_unclustered_processed_articles():
    """Eligibility = embedded + event-extracted + not already in a story."""
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    assert 'Article.embedding_status == "completed"' in src
    assert 'Article.event_extraction_status == "completed"' in src
    assert "StoryArticle.article_id" in src and "exists()" in src, (
        "must test unclustered via NOT EXISTS against story_articles"
    )


# ── BUG-03: the lifecycle deadlock ───────────────────────────────────────────


def test_candidate_retrieval_includes_emerging_stories():
    """Newly created stories must be reachable as merge candidates.

    Stories are created "emerging" and only leave that state at >= 3 articles,
    which requires merges, which requires being a candidate. Excluding
    "emerging" closed the loop: production ended with 476/476 stories stuck
    there, 462 of them holding a single article.
    """
    src = inspect.getsource(clustering_service.add_article_to_existing_story_if_similar)
    assert "StoryLifecycleState.EMERGING" in src, (
        "candidate retrieval excludes emerging stories — they can never grow"
    )


def test_new_stories_are_created_with_an_explicit_lifecycle_state():
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    assert "lifecycle_state=StoryLifecycleState.EMERGING" in src


# ── BUG-02: the Stage B anchor ───────────────────────────────────────────────


def test_story_model_has_story_embedding_column():
    """clustering_service reads this via getattr; without it Stage B is dead.

    getattr(story, "story_embedding", None) silently returned None for every
    candidate, so cosine similarity was always exactly 0.0 and Stage B could
    never return PASS or MAYBE.
    """
    from app.models.models import Story

    assert hasattr(Story, "story_embedding"), "Story.story_embedding is missing"
    assert "story_embedding" in Story.__table__.columns


@pytest.mark.asyncio
async def test_refresh_story_centroid_returns_unit_vector():
    """The centroid must be re-normalized: the mean of unit vectors is not one."""
    from app.models.models import Story

    story = Story(id=uuid.uuid4())
    session = AsyncMock()

    v1 = (np.array([1.0, 0.0, 0.0]) / 1.0).tolist()
    v2 = (np.array([0.0, 1.0, 0.0]) / 1.0).tolist()

    with patch(
        "app.services.clustering_service.vector_service.retrieve_vectors",
        AsyncMock(return_value={"a": v1, "b": v2}),
    ):
        centroid = await clustering_service.refresh_story_centroid(
            story, session, article_ids=[uuid.uuid4(), uuid.uuid4()]
        )

    assert centroid is not None
    assert story.story_embedding == centroid
    assert np.isclose(np.linalg.norm(centroid), 1.0), "centroid is not unit-norm"


@pytest.mark.asyncio
async def test_refresh_story_centroid_leaves_value_alone_when_no_vectors():
    """A missing-vector story must not have its anchor clobbered with garbage."""
    from app.models.models import Story

    story = Story(id=uuid.uuid4())
    story.story_embedding = [0.5, 0.5]

    with patch(
        "app.services.clustering_service.vector_service.retrieve_vectors",
        AsyncMock(return_value={}),
    ):
        result = await clustering_service.refresh_story_centroid(
            story, AsyncMock(), article_ids=[uuid.uuid4()]
        )

    assert result is None
    assert story.story_embedding == [0.5, 0.5]


def test_stage_b_can_pass_once_a_centroid_exists():
    """End state of the BUG-02 fix: a real centroid produces a real cosine."""
    from app.services.event_validation_service import EventValidationService, StoryAnchor

    vector = [1.0] + [0.0] * 767
    anchor = StoryAnchor(
        story_id="s1",
        headline="h",
        first_seen_at=MagicMock(tzinfo=None),
        last_updated_at=MagicMock(tzinfo=None),
        primary_entities=set(),
        top_locations=set(),
        category=None,
        event_type=None,
        centroid_vector=vector,  # was always None before the column existed
        entity_graph_ids=set(),
    )
    article = MagicMock(title="t", published_at=None, source=None)

    decision = EventValidationService().validate_stage_b(article, anchor, vector, set())
    assert decision.score == pytest.approx(1.0)
    assert decision.outcome.value == "PASS"


# ── BUG-06 / BUG-07: transaction and lock safety ─────────────────────────────


def test_synthesis_runs_outside_the_cluster_savepoint():
    """Synthesis commits internally, so it must not run inside begin_nested().

    Committing while a SAVEPOINT is open raises InvalidRequestError, which the
    handler swallowed — leaving a half-committed story while reporting that no
    stories were created.
    """
    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    savepoint_idx = src.index("session.begin_nested()")
    synth_idx = src.index("generate_story_content")
    assert synth_idx > savepoint_idx

    savepoint_block = src[savepoint_idx:synth_idx]
    assert "await session.commit()" in savepoint_block, (
        "cluster creation should be committed before synthesis begins"
    )


def test_global_lock_uses_a_dedicated_connection_and_try_lock():
    """The advisory lock must outlive the session's commits, and not block."""
    src = inspect.getsource(clustering_service.run_batch_clustering)
    assert "engine.connect()" in src, "lock must not ride on the session's connection"
    assert "pg_try_advisory_lock" in src, "blocking pg_advisory_lock piles up waiters"
    assert "lock_conn.execute" in src


@pytest.mark.asyncio
async def test_batch_clustering_skips_when_lock_is_held():
    """A concurrent run must return 0, not duplicate every story."""
    lock_conn = AsyncMock()
    not_acquired = MagicMock()
    not_acquired.scalar.return_value = False
    lock_conn.execute = AsyncMock(return_value=not_acquired)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=lock_conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    fake_engine = MagicMock()
    fake_engine.connect = MagicMock(return_value=cm)

    with (
        patch("app.services.clustering_service.engine", fake_engine),
        patch.object(clustering_service, "_run_batch_clustering_locked", AsyncMock()) as inner,
    ):
        result = await clustering_service.run_batch_clustering(AsyncMock())

    assert result == 0
    inner.assert_not_awaited()
