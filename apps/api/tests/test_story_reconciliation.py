"""Regression tests for continuous story reconciliation.

The structural gap this closes: clustering evaluates an article exactly once,
at extraction time, against the stories that existed then. Nothing revisits an
already-clustered article, and no process ever compares two *stories*. So two
articles about the same event arriving in different batches each create a
story, and those stories stay split forever — regardless of how good the
scoring is.

Production measured 41 duplicate groups across 144 stories (28%), including
five separate "OpenAI launches ChatGPT desktop app for Linux" stories whose
article vectors scored 0.9458 against each other.
"""

import inspect

import pytest

from app.services.story_reconciliation_service import (
    CENTROID_PREFILTER,
    DERIVED_CHILD_TABLES,
    USER_OWNED_TABLES,
    StoryReconciliationService,
    _cosine,
)


def test_user_owned_rows_are_never_in_the_delete_list():
    """Bookmarks must be repointed, not deleted.

    Deleting them would destroy someone's saved story to tidy up a clustering
    mistake the user never made.
    """
    user_tables = {t for t, _ in USER_OWNED_TABLES}
    assert user_tables == {"bookmarks", "user_events"}
    assert user_tables.isdisjoint(set(DERIVED_CHILD_TABLES))

    src = inspect.getsource(StoryReconciliationService.merge)
    assert "UPDATE {table} SET story_id = :keep" in src, "user rows must be repointed"


def test_every_story_fk_child_is_handled():
    """A missed FK table makes the DELETE fail at runtime, not at review.

    An earlier draft deleted only story_articles/story_entities and would have
    failed on every merge, because story_metrics exists for every story.
    """
    handled = set(DERIVED_CHILD_TABLES) | {t for t, _ in USER_OWNED_TABLES}
    required = {
        "story_timeline_events",
        "story_source_coverage",
        "story_differences",
        "story_entities",
        "story_tags",
        "story_contradictions",
        "story_metrics",
        "story_versions",
        "story_evolutions",
        "synthesis_artifacts",
        "story_reviews",
        "story_articles",
        "bookmarks",
        "user_events",
    }
    missing = required - handled
    assert not missing, f"unhandled FK children would break the merge: {sorted(missing)}"

    src = inspect.getsource(StoryReconciliationService.merge)
    assert "current_version_id = NULL" in src, "circular FK must be broken first"
    assert "story_candidates" in src, "nullable references must be detached"


def test_reconciliation_reuses_the_production_validators():
    """A merge here must mean exactly what a merge means in the live path.

    Bespoke similarity logic would drift from Stage A/B and silently apply a
    different standard to the same decision.
    """
    src = inspect.getsource(StoryReconciliationService.find_duplicates)
    assert "validate_stage_a" in src
    assert "validate_stage_b" in src
    assert 'decision_b.outcome.value != "PASS"' in src, "Stage B must PASS, not merely be MAYBE"


def test_centroid_prefilter_cannot_decide_a_merge():
    """The cheap prefilter must sit well below Stage B's threshold.

    If it were near or above it, the prefilter — not the validators — would be
    making merge decisions, and it has no entity or title signal at all.
    """
    from app.services.event_validation_service import event_validation_service

    stage_b_cosine = event_validation_service.stage_b_thresh.get("cosine", 0.72)
    assert CENTROID_PREFILTER < stage_b_cosine, (
        f"prefilter {CENTROID_PREFILTER} must be below Stage B's {stage_b_cosine}"
    )


@pytest.mark.asyncio
async def test_reconcile_is_bounded_per_run():
    """A scoring regression must not be able to collapse the corpus in one pass."""
    from unittest.mock import AsyncMock, patch

    svc = StoryReconciliationService()
    many = [
        {
            "keep_id": f"k{i}",
            "drop_id": f"d{i}",
            "keep_headline": "a",
            "drop_headline": "b",
            "stage_a": 70.0,
            "stage_b": 0.9,
        }
        for i in range(100)
    ]
    with (
        patch.object(svc, "find_duplicates", AsyncMock(return_value=many)),
        patch.object(svc, "merge", AsyncMock(return_value=True)) as merge_mock,
    ):
        result = await svc.reconcile(hours=48, max_merges=25)

    assert result["found"] == 100
    assert result["merged"] == 25, "the per-run cap was not enforced"
    assert merge_mock.await_count == 25


def test_reconciliation_is_actually_scheduled():
    """An unscheduled maintenance task is one that does not exist.

    recover_stuck_embeddings_task shipped unscheduled and left 53 articles
    stranded in 'processing' indefinitely.
    """
    from app.workers.celery_app import celery_app

    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert "app.workers.tasks.reconcile_duplicate_stories_task" in scheduled


def test_merge_refreshes_the_survivors_identity():
    """Otherwise the next pass compares against a stale centroid and headline."""
    src = inspect.getsource(StoryReconciliationService.merge)
    assert "refresh_story_centroid" in src
    assert "seed_story_anchor" in src


def test_cosine_handles_missing_and_zero_vectors():
    assert _cosine(None, [1.0, 0.0]) == 0.0
    assert _cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert _cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
