"""Knowledge Graph service — build and serialize story-level knowledge graphs.

Constructs in-memory representation of events, entities, and sources,
then serializes it to be stored in the PostgreSQL 'stories.knowledge_graph' column.
"""

from __future__ import annotations

import logging
from typing import Any
import uuid

from app.models.models import Article, ArticleEvent, StoryEntity, Source

logger = logging.getLogger(__name__)


class StoryKnowledgeGraph:
    """Story-level Knowledge Graph representing events, entities, and sources."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._node_ids: set[str] = set()

    def add_node(
        self,
        node_id: str,
        label: str,
        node_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a unique node to the graph."""
        if node_id in self._node_ids:
            # Update properties if needed, but don't add duplicate
            return
        self._node_ids.add(node_id)
        self.nodes.append(
            {
                "id": node_id,
                "label": label,
                "type": node_type,
                "properties": properties or {},
            }
        )

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add an edge between two nodes if both nodes exist in the graph."""
        if source_id not in self._node_ids or target_id not in self._node_ids:
            # Log warning or skip to prevent orphan edges
            return

        self.edges.append(
            {
                "source": source_id,
                "target": target_id,
                "type": edge_type,
                "properties": properties or {},
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the dictionary representation of the knowledge graph."""
        return {"nodes": self.nodes, "edges": self.edges}


def build_story_knowledge_graph(
    articles: list[Article],
    article_events: list[ArticleEvent],
    story_entities: list[StoryEntity],
    sources: list[Source],
) -> StoryKnowledgeGraph:
    """Build a Knowledge Graph from a story cluster's articles, events, and entities.

    Nodes:
    - article_{id}
    - source_{id}
    - event_{id}
    - entity_{canonical_id or entity_id}

    Edges:
    - reported_by (Article -> Source)
    - describes_event (Article -> Event)
    - participated_in (Entity -> Event, with role actor/target)
    - located_at (Event -> Location Entity)
    """
    graph = StoryKnowledgeGraph()

    # 1. Add Source Nodes
    for src in sources:
        graph.add_node(
            node_id=f"source_{src.id}",
            label=src.name,
            node_type="source",
            properties={
                "website_url": src.website_url,
                "country_code": src.country_code,
            },
        )

    # 2. Add Article Nodes & reported_by Edges
    for art in articles:
        graph.add_node(
            node_id=f"article_{art.id}",
            label=art.title or "Untitled Article",
            node_type="article",
            properties={
                "url": art.url,
                "published_at": art.published_at.isoformat() if art.published_at else None,
            },
        )
        if art.source_id:
            graph.add_edge(
                source_id=f"article_{art.id}",
                target_id=f"source_{art.source_id}",
                edge_type="reported_by",
            )

    # 3. Add Event Nodes & describes_event Edges
    for evt in article_events:
        event_time_str = evt.event_time.isoformat() if evt.event_time else None
        graph.add_node(
            node_id=f"event_{evt.id}",
            label=evt.event_type_canonical or evt.event_type or "EVENT",
            node_type="event",
            properties={
                "event_type": evt.event_type,
                "location_raw": evt.location,
                "event_time": event_time_str,
                "event_time_raw": evt.event_time_raw,
                "confidence": float(evt.confidence) if evt.confidence is not None else 0.5,
                "numbers": evt.numbers or {},
            },
        )
        if evt.article_id:
            graph.add_edge(
                source_id=f"article_{evt.article_id}",
                target_id=f"event_{evt.id}",
                edge_type="describes_event",
            )

    # 4. Add Entity Nodes & participated_in / located_at Edges
    entity_id_map: dict[str, str] = {}
    for sent in story_entities:
        canonical_id = sent.canonical_entity_id or sent.id
        node_id = f"entity_{canonical_id}"
        
        # Link raw values/aliases to this node_id for easy lookup when building edges
        entity_id_map[sent.entity_value.lower()] = node_id
        if sent.canonical_entity:
            entity_id_map[sent.canonical_entity.canonical_name.lower()] = node_id
            for alias in (sent.canonical_entity.aliases or []):
                entity_id_map[alias.lower()] = node_id

            label = sent.canonical_entity.canonical_name
            wikidata_id = sent.canonical_entity.wikidata_id
            desc = sent.canonical_entity.metadata_payload.get("description") if sent.canonical_entity.metadata_payload else None
        else:
            label = sent.entity_value
            wikidata_id = None
            desc = None

        graph.add_node(
            node_id=node_id,
            label=label,
            node_type="entity",
            properties={
                "entity_type": sent.entity_type,
                "wikidata_id": wikidata_id,
                "description": desc,
            },
        )

    # 5. Build Relationship Edges (Entity -> Event)
    for evt in article_events:
        event_node_id = f"event_{evt.id}"

        # Link actors (e.g. PERSON, ORG)
        for actor in (evt.actors or []):
            actor_lower = actor.lower()
            if actor_lower in entity_id_map:
                graph.add_edge(
                    source_id=entity_id_map[actor_lower],
                    target_id=event_node_id,
                    edge_type="participated_in",
                    properties={"role": "actor"},
                )

        # Link targets
        for target in (evt.targets or []):
            target_lower = target.lower()
            if target_lower in entity_id_map:
                graph.add_edge(
                    source_id=entity_id_map[target_lower],
                    target_id=event_node_id,
                    edge_type="participated_in",
                    properties={"role": "target"},
                )

        # Link locations (Event -> Location Entity)
        if evt.location:
            loc_lower = evt.location.lower()
            # Try exact match or sub-phrase match in entity mapping
            matched_node_id: str | None = None
            if loc_lower in entity_id_map:
                matched_node_id = entity_id_map[loc_lower]
            else:
                for k, v in entity_id_map.items():
                    if k in loc_lower or loc_lower in k:
                        matched_node_id = v
                        break
            
            if matched_node_id:
                graph.add_edge(
                    source_id=event_node_id,
                    target_id=matched_node_id,
                    edge_type="located_at",
                )

    return graph
