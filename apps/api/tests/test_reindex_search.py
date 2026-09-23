"""The search-index rebuild must write exactly what the pipeline writes.

A rebuilt index that differs from the live one (e.g. leaking internal `fact:`
tags, or a missing field the search filters on) would change search results
after every migration. `document_for` must match the pipeline's own
`build_story_document` call, including its tag filter.
"""

import uuid
from datetime import datetime
from types import SimpleNamespace

from app.scripts.reindex_search import document_for
from app.services.search_service import build_story_document


def _story(tags: list[str]):
    return SimpleNamespace(
        id=uuid.uuid4(),
        headline="Parliament passes the data protection bill",
        one_line_summary="one line",
        short_summary="short",
        detailed_summary="detailed",
        location_country="IN",
        story_status="active",
        trend_score=0.4,
        updated_at=datetime(2026, 9, 1, 12, 0),
        category=SimpleNamespace(slug="politics"),
        tags=[SimpleNamespace(tag_name=t) for t in tags],
    )


def test_internal_fact_tags_never_reach_the_index():
    doc = document_for(_story(["privacy", "fact:vote_count=311", "parliament"]))
    assert doc["tags"] == ["privacy", "parliament"]


def test_matches_the_pipelines_document_exactly():
    story = _story(["privacy", "fact:x"])
    assert document_for(story) == build_story_document(story, "politics", ["privacy"])


def test_story_without_category_or_tags_still_indexes():
    story = _story([])
    story.category = None
    story.tags = []
    doc = document_for(story)
    assert doc["category_slug"] == ""
    assert doc["tags"] == []
