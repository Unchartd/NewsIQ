"""An article's journey must be followable, and reachable from the UI.

/admin/articles/{id}/trace has existed all along with **no consumer anywhere in
the frontend**, which is why the audit found data lineage unreachable despite
the backend supporting it.

It was also thin on its own terms: it filtered stage_runs on article_id, and
only clustering_incremental ever set that column — 5,916 of 48,019 spans — so an
article's "end-to-end trace" was a single stage repeated. The crawl span is 1:1
with the article it creates and is now tagged, which makes it the entry point.
"""

import inspect
import re
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1.admin import get_article_trace
from app.workers import tasks

STORY_PAGE = (
    Path(__file__).resolve().parents[2]
    / "admin"
    / "src"
    / "app"
    / "admin"
    / "stories"
    / "[storyId]"
    / "page.tsx"
)


def _article():
    a = MagicMock()
    a.id = uuid.uuid4()
    a.url = "https://example.com/a"
    a.title = "T"
    a.source_id = uuid.uuid4()
    a.crawled_at = None
    a.published_at = None
    a.content = "x" * 2237
    a.event_extraction_status = "completed"
    return a


def _session(article=None, stages=(), story=None, story_stages=(), traces=()):
    """Drive the endpoint's queries in order."""

    def _scalar(v):
        r = MagicMock()
        r.scalar_one_or_none.return_value = v
        return r

    def _list(items):
        r = MagicMock()
        r.scalars.return_value.all.return_value = list(items)
        return r

    results = [_scalar(article), _list(stages), _scalar(story)]
    if story is not None:
        results.append(_list(story_stages))
    results.append(_list(traces))

    s = AsyncMock()
    s.execute.side_effect = results
    return s


# ── backend ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_article_returns_404_not_an_empty_journey():
    """An empty list used to be indistinguishable from a missing article."""
    with pytest.raises(HTTPException) as exc:
        await get_article_trace(article_id=uuid.uuid4(), _admin=None, db=_session(article=None))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_trace_returns_the_article_and_the_story_it_joined():
    art = _article()
    story = MagicMock()
    story.id = uuid.uuid4()
    story.headline = "H"
    story.story_status = "active"
    story.one_line_summary = "s"

    res = await get_article_trace(
        article_id=art.id, _admin=None, db=_session(article=art, story=story)
    )

    assert res["article"]["url"] == "https://example.com/a"
    assert res["article"]["content_length"] == 2237
    assert res["story"]["headline"] == "H", "the story link is what makes it a journey"


@pytest.mark.asyncio
async def test_article_without_a_story_still_traces():
    """An article that never clustered is exactly the one to investigate."""
    art = _article()
    res = await get_article_trace(
        article_id=art.id, _admin=None, db=_session(article=art, story=None)
    )
    assert res["story"] is None
    assert res["story_stages"] == []


@pytest.mark.asyncio
async def test_stages_key_is_preserved_for_existing_consumers():
    art = _article()
    res = await get_article_trace(
        article_id=art.id, _admin=None, db=_session(article=art, story=None)
    )
    assert "stages" in res, "renaming this would break any existing caller"


def test_crawl_span_is_tagged_with_the_article_it_creates():
    """Without this, lineage has no entry point — only clustering set article_id."""
    src = inspect.getsource(tasks.discovery_crawl_task)
    assert "span.article_id = str(new_article.id)" in src, (
        "the crawl span must carry the article id, or stage_runs.article_id stays "
        "populated only by clustering_incremental"
    )


# ── frontend wiring ───────────────────────────────────────────────────────────


@pytest.mark.skipif(not STORY_PAGE.exists(), reason="admin app not present")
def test_lineage_endpoint_now_has_a_frontend_consumer():
    """The audit's core lineage finding was a missing UI, not a missing API."""
    text = STORY_PAGE.read_text(encoding="utf-8")
    assert "/admin/articles/" in text and "/trace" in text, (
        "no frontend code calls the lineage endpoint"
    )


@pytest.mark.skipif(not STORY_PAGE.exists(), reason="admin app not present")
def test_lineage_is_fetched_lazily_on_expand():
    """Fetching per row would cost one request per article on every page load."""
    text = STORY_PAGE.read_text(encoding="utf-8")
    match = re.search(r'queryKey: \["article-lineage".*?enabled: ([^,\n]+)', text, re.S)
    assert match, "lineage query not found"
    assert "open" in match.group(1), "lineage must only load once the row is expanded"
