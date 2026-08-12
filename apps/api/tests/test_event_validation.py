"""Tests for Dual-Stage Event Validation."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.event_validation_service import (
    StoryAnchor,
    ValidationOutcome,
    event_validation_service,
)


class MockArticle:
    def __init__(self, title, published_at, source_tier=5):
        self.title = title
        self.published_at = published_at

        class MockSource:
            trust_tier = source_tier

        self.source = MockSource()


@pytest.fixture
def mock_story_anchor():
    return StoryAnchor(
        story_id="test_1",
        headline="Apple announces new AI chip",
        first_seen_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=12),
        last_updated_at=datetime.now(UTC).replace(tzinfo=None),
        primary_entities={"apple", "ai"},
        top_locations={"california"},
        category="technology",
        event_type="product_launch",
        centroid_vector=[0.1, 0.2, 0.3],
        entity_graph_ids={"ent_1", "ent_2"},
    )


def test_stage_a_validation_pass(mock_story_anchor):
    # Highly related article
    article = MockArticle(
        title="Apple unveils latest AI processor in California",
        published_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        source_tier=1,
    )

    decision = event_validation_service.validate_stage_a(article, mock_story_anchor)
    assert decision.outcome == ValidationOutcome.PASS
    assert decision.score >= 60.0


def test_stage_a_validation_fail(mock_story_anchor):
    # Completely unrelated article
    article = MockArticle(
        title="Local sports team wins championship game",
        published_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        source_tier=5,
    )

    decision = event_validation_service.validate_stage_a(article, mock_story_anchor)
    assert decision.outcome == ValidationOutcome.FAIL
    assert decision.score < 45.0


def test_stage_a_validation_maybe(mock_story_anchor):
    # Borderline article (some time/trust overlap, but no entities)
    # If it happens at same time and high trust, but completely different title...
    article = MockArticle(
        title="Some tech company announces new hardware",
        published_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        source_tier=2,
    )

    decision = event_validation_service.validate_stage_a(article, mock_story_anchor)

    # An unrelated article must still FAIL — that is the assertion that matters.
    #
    # The score band was 25-30 when a missing entity overlap scored a hard 0.
    # That asymmetry (neutral when the STORY had no entities, zero when the
    # ARTICLE had none) is what pinned every real candidate at 44.5 against a
    # 45 threshold, so entity absence is now neutral on both sides and this
    # case lands in the mid-40s. Still below the bar, which is the point.
    assert 40.0 <= decision.score < 45.0
    assert decision.outcome == ValidationOutcome.FAIL


def test_stage_b_validation_pass(mock_story_anchor):
    # Exact same vector
    article_vector = [0.1, 0.2, 0.3]
    article_entities = {"ent_1"}

    decision = event_validation_service.validate_stage_b(
        None, mock_story_anchor, article_vector, article_entities
    )
    # Cosine will be 1.0 > 0.72 -> PASS
    assert decision.outcome == ValidationOutcome.PASS


def test_stage_b_validation_fail(mock_story_anchor):
    # Opposite vector
    article_vector = [-0.1, -0.2, -0.3]
    article_entities = {"ent_3"}

    decision = event_validation_service.validate_stage_b(
        None, mock_story_anchor, article_vector, article_entities
    )
    assert decision.outcome == ValidationOutcome.FAIL
