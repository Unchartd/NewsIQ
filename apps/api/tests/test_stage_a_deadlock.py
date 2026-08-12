"""Regression tests for the Stage A deadlock that made merging impossible.

Measured in production across 809 clustering traces: 801 FAIL, every one of
them at Stage A, and Stage B never executed once. The rejection reasons were
all "Low score (44.5 < 45)", "(37.0 < 45)", "(29.5 < 45)".

The 44.5 is not a coincidence — it was the arithmetic ceiling:

    entity_overlap  17.5  (neutral: the story had no entities)
    location        10.0  (neutral)
    time_proximity  15.0  (max)
    title_similarity 0.0  (the story had no headline)
    publisher_trust  2.0  (every source resolved to tier 5)
    -------------------------
    total           44.5  against a threshold of 45

Both zero-scoring components came from the same place: `headline` and
`story_entities` are written only by generate_story_content, which is
deliberately skipped for single-article clusters. So a story could not be
matched until it had 2 articles, and could not reach 2 articles without being
matched. 103 of 104 production stories had headline NULL; exactly 1 had any
entities.

Fixed by seeding a story's identity from its own articles at creation — no LLM
needed, since titles and article entities already exist — and by making the
entity-overlap component symmetric.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.event_validation_service import EventValidationService, StoryAnchor

NOW = datetime.now(UTC).replace(tzinfo=None)
HEADLINE = "Virudhunagar firecracker factory blast: death toll rises to 23"
STORY_ENTITIES = {"virudhunagar", "firecracker factory", "tamil nadu"}


def _anchor(headline: str, entities: set[str]) -> StoryAnchor:
    return StoryAnchor(
        story_id="s1",
        headline=headline,
        first_seen_at=NOW - timedelta(hours=3),
        last_updated_at=NOW,
        primary_entities=entities,
        top_locations=set(),
        category=None,
        event_type=None,
        centroid_vector=None,
        entity_graph_ids=set(),
    )


def _article(title: str):
    return MagicMock(title=title, published_at=NOW, source=None)


def test_unseeded_story_cannot_reach_the_threshold():
    """Pins the exact production failure: the ceiling sat below the threshold."""
    svc = EventValidationService()
    decision = svc.validate_stage_a(_article(HEADLINE), _anchor("", set()))

    assert decision.details["title_similarity_score"] == 0.0
    assert decision.outcome.value == "FAIL"
    # A story with no identity cannot be matched even by its own headline.
    assert decision.score < svc.stage_a_thresh.get("maybe", 45)


def test_seeded_anchor_lets_an_identical_story_pass():
    svc = EventValidationService()
    decision = svc.validate_stage_a(
        _article(HEADLINE),
        _anchor(HEADLINE, STORY_ENTITIES),
        article_entities={"Virudhunagar", "firecracker factory", "Tamil Nadu"},
    )
    assert decision.outcome.value == "PASS"


def test_related_article_with_different_wording_passes():
    """The case clustering exists for: same event, different newsroom's words."""
    svc = EventValidationService()
    decision = svc.validate_stage_a(
        _article("Death toll in Tamil Nadu cracker unit explosion climbs to 23"),
        _anchor(HEADLINE, STORY_ENTITIES),
        article_entities={"Tamil Nadu", "Virudhunagar"},
    )
    assert decision.outcome.value in ("PASS", "MAYBE"), (
        f"related article scored {decision.score}, still below the bar"
    )


def test_unrelated_article_is_still_rejected():
    """The fix must not become a blanket pass."""
    svc = EventValidationService()
    decision = svc.validate_stage_a(
        _article("Manchester United sign new midfielder in summer window"),
        _anchor(HEADLINE, STORY_ENTITIES),
        article_entities={"Manchester United"},
    )
    assert decision.outcome.value == "FAIL"


def test_missing_entities_on_either_side_scores_neutral_not_zero():
    """Absence of extractable entities is uninformative, not disconfirming.

    Scoring 0 when only the article side was empty punished the article for the
    extractor's weakness on short headlines — a 17.5-point swing that, against a
    45 threshold, was on its own enough to force a rejection.
    """
    svc = EventValidationService()
    weight = svc.stage_a_weights.get("entity_overlap", 35)

    article_empty = svc.validate_stage_a(
        _article("Blast kills several"), _anchor(HEADLINE, STORY_ENTITIES)
    )
    story_empty = svc.validate_stage_a(
        _article(HEADLINE), _anchor(HEADLINE, set()), article_entities={"Virudhunagar"}
    )

    assert article_empty.details["entity_overlap_score"] == pytest.approx(weight * 0.5)
    assert story_empty.details["entity_overlap_score"] == pytest.approx(weight * 0.5)


def test_stored_entities_are_used_not_just_the_title():
    """The body-derived entities must contribute, not only the headline scrape."""
    svc = EventValidationService()
    without = svc.validate_stage_a(
        _article("Blast kills several"), _anchor(HEADLINE, STORY_ENTITIES)
    )
    with_stored = svc.validate_stage_a(
        _article("Blast kills several"),
        _anchor(HEADLINE, STORY_ENTITIES),
        article_entities={"Virudhunagar", "Tamil Nadu"},
    )
    assert with_stored.score > without.score


def test_story_creation_seeds_the_anchor():
    """A story must be matchable the moment it exists, not only after synthesis."""
    import inspect

    from app.services.clustering_service import clustering_service

    src = inspect.getsource(clustering_service._run_batch_clustering_locked)
    assert "seed_story_anchor" in src, (
        "stories are created without a headline or entities, so Stage A cannot match them"
    )

    seed_src = inspect.getsource(clustering_service.seed_story_anchor)
    assert "story.headline" in seed_src
    assert "StoryEntity" in seed_src
    assert "if not story.headline" in seed_src, "must not clobber a synthesised headline"
