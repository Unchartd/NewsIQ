"""Unit tests for the StoryKnowledgeGraph builder."""

import uuid
import datetime

from app.models.models import Article, ArticleEvent, StoryEntity, Source, CanonicalEntity
from app.services.knowledge_graph import build_story_knowledge_graph, StoryKnowledgeGraph


def test_build_story_knowledge_graph():
    """Verify building a Story Knowledge Graph from raw models."""
    story_id = uuid.uuid4()
    source_id = uuid.uuid4()
    article_id = uuid.uuid4()
    event_id = uuid.uuid4()
    canonical_entity_id = uuid.uuid4()

    # 1. Setup mock models
    source = Source(
        id=source_id,
        name="BBC News",
        website_url="https://bbc.com",
        country_code="GB",
    )

    article = Article(
        id=article_id,
        source_id=source_id,
        title="Rahul Gandhi Protests",
        url="https://bbc.com/news/123",
        published_at=datetime.datetime(2026, 6, 20, 12, 0),
    )

    event = ArticleEvent(
        id=event_id,
        article_id=article_id,
        event_type="PROTEST",
        event_type_canonical="PROTEST",
        actors=["Rahul Gandhi"],
        targets=["Government"],
        location="New Delhi, India",
        event_time=datetime.datetime(2026, 6, 20, 10, 0),
        event_time_raw="2026-06-20T10:00:00Z",
        confidence=0.9,
    )

    canonical_ent = CanonicalEntity(
        id=canonical_entity_id,
        canonical_name="Rahul Gandhi",
        entity_type="PERSON",
        wikidata_id="Q981309",
        aliases=["Rahul Gandhi", "Gandhi"],
        metadata_payload={"description": "Indian politician"},
    )

    story_entity = StoryEntity(
        id=uuid.uuid4(),
        story_id=story_id,
        canonical_entity_id=canonical_entity_id,
        entity_type="PERSON",
        entity_value="Rahul Gandhi",
        canonical_entity=canonical_ent,
    )

    # 2. Build graph
    kg = build_story_knowledge_graph(
        articles=[article],
        article_events=[event],
        story_entities=[story_entity],
        sources=[source],
    )

    # 3. Verify graph structure
    kg_dict = kg.to_dict()
    nodes = kg_dict["nodes"]
    edges = kg_dict["edges"]

    # Verify node counts (1 source, 1 article, 1 event, 1 entity)
    assert len(nodes) == 4
    
    # Verify nodes
    node_ids = {n["id"] for n in nodes}
    assert f"source_{source_id}" in node_ids
    assert f"article_{article_id}" in node_ids
    assert f"event_{event_id}" in node_ids
    assert f"entity_{canonical_entity_id}" in node_ids

    # Verify article properties
    art_node = next(n for n in nodes if n["id"] == f"article_{article_id}")
    assert art_node["label"] == "Rahul Gandhi Protests"
    assert art_node["type"] == "article"

    # Verify event properties
    evt_node = next(n for n in nodes if n["id"] == f"event_{event_id}")
    assert evt_node["label"] == "PROTEST"
    assert evt_node["properties"]["location_raw"] == "New Delhi, India"
    assert evt_node["properties"]["confidence"] == 0.9

    # Verify edges
    # Should have:
    # - article -> source (reported_by)
    # - article -> event (describes_event)
    # - entity -> event (participated_in, actor)
    assert len(edges) == 3

    # Check reported_by
    e_reported = next(e for e in edges if e["type"] == "reported_by")
    assert e_reported["source"] == f"article_{article_id}"
    assert e_reported["target"] == f"source_{source_id}"

    # Check describes_event
    e_describes = next(e for e in edges if e["type"] == "describes_event")
    assert e_describes["source"] == f"article_{article_id}"
    assert e_describes["target"] == f"event_{event_id}"

    # Check participated_in
    e_participated = next(e for e in edges if e["type"] == "participated_in")
    assert e_participated["source"] == f"entity_{canonical_entity_id}"
    assert e_participated["target"] == f"event_{event_id}"
    assert e_participated["properties"]["role"] == "actor"
