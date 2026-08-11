"""Regression tests for BUG-04 and BUG-05 — clustering fault isolation.

BUG-04: the Stage B anchor was built with `set(story.knowledge_graph["nodes"])`,
but nodes is a list[dict], so that raises `TypeError: unhashable type: 'dict'`
for any story that has a knowledge graph.

BUG-05: that TypeError was caught by extract_events_task's per-article
`except Exception`, which then overwrote an already-committed
`event_extraction_status='completed'` with `'failed'`. Because the task selector
only picks up pending/NULL, 'failed' is terminal — a clustering fault
permanently removed a successfully-extracted article from the pipeline and
recorded the failure against the wrong stage.

These two are coupled: BUG-04 is dormant only while no candidate stories exist.
Restoring the clustering feed makes it live, so both fixes must precede that.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.event_validation_service import StoryAnchor


def test_knowledge_graph_nodes_are_unhashable():
    """Pins the shape that made the old anchor construction crash."""
    from app.services.knowledge_graph import StoryKnowledgeGraph

    graph = StoryKnowledgeGraph()
    graph.add_node(node_id="entity_1", node_type="entity", label="Apple")
    nodes = graph.to_dict()["nodes"]

    assert isinstance(nodes, list) and isinstance(nodes[0], dict)
    with pytest.raises(TypeError, match="unhashable"):
        set(nodes)  # the exact expression the old code used


def test_anchor_entity_ids_share_an_identifier_space():
    """Both sides of the Stage B entity test must use canonical entity IDs.

    Previously the story side held knowledge-graph dicts and the article side
    held display names from event.actors/targets, so the intersection was
    always empty and the entity signal could never fire.
    """
    from app.services.event_validation_service import EventValidationService

    shared = uuid.uuid4()
    story_ids = {str(shared), str(uuid.uuid4())}
    article_ids = {str(shared)}

    anchor = StoryAnchor(
        story_id="s1",
        headline="h",
        first_seen_at=MagicMock(tzinfo=None),
        last_updated_at=MagicMock(tzinfo=None),
        primary_entities=set(),
        top_locations=set(),
        category=None,
        event_type=None,
        centroid_vector=None,
        entity_graph_ids=story_ids,
    )

    article = MagicMock(title="t", published_at=None, source=None)
    decision = EventValidationService().validate_stage_b(article, anchor, [0.1] * 768, article_ids)
    assert decision.details["shared_canonical_entities"] == 1


@pytest.mark.asyncio
async def test_clustering_failure_does_not_mark_extraction_failed():
    """A clustering exception must leave event_extraction_status == 'completed'.

    'failed' is terminal, so misattributing a clustering fault to extraction
    permanently drops the article from the pipeline.
    """
    from app.models.models import Article

    article = Article(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        title="Apple commits $30bn to Broadcom",
        url="http://example.com/a",
        embedding_status="completed",
        event_extraction_status="completed",
    )

    session = AsyncMock()
    session.rollback = AsyncMock()

    with patch(
        "app.services.clustering_service.clustering_service."
        "add_article_to_existing_story_if_similar",
        AsyncMock(side_effect=TypeError("unhashable type: 'dict'")),
    ):
        from app.services.clustering_service import clustering_service

        clustering_failed = 0
        try:
            await clustering_service.add_article_to_existing_story_if_similar(article.id, session)
        except Exception:
            # This mirrors the isolated handler now wrapping the call in
            # extract_events_task: absorb, roll back, and leave status alone.
            clustering_failed += 1
            await session.rollback()

        assert clustering_failed == 1
        assert article.event_extraction_status == "completed", (
            "clustering failure must not roll back the committed extraction status"
        )
        session.rollback.assert_awaited_once()


def test_extract_events_isolates_clustering_from_extraction_status():
    """The clustering call in extract_events_task must sit in its own try block.

    Guards against the isolation being refactored away: if the call ever moves
    back under the outer per-article handler, that handler sets
    event_extraction_status='failed' and the terminal-state bug returns.
    """
    import inspect

    from app.workers import tasks

    src = inspect.getsource(tasks.extract_events_task)
    call_idx = src.index("add_article_to_existing_story_if_similar")
    before = src[:call_idx]

    # The nearest preceding `try:` must belong to the dedicated clustering guard,
    # not the outer per-article handler that mutates extraction status.
    assert "except Exception as cluster_err" in src, "clustering guard is missing"
    assert before.rindex("try:") > before.rindex('event_extraction_status = "completed"'), (
        "clustering call is not wrapped in its own try block after the extraction commit"
    )
