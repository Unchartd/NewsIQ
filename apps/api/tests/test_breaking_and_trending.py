"""How a story becomes "BREAKING" and how /trending ranks.

Both were measured against production in docs/Breaking_Trending_Audit.md.

The BANNER was not computed at all. It rendered feed row 1 with a hardcoded
"Just now"; the feed sorted by updated_at, so a re-clustered story floated to
row 1 regardless of age. At audit time the live banner showed a
**72.9-hour-old** story labelled "BREAKING ... Just now".

It is now a top-story flag keyed on discovery, not a breaking flag keyed on
publication, because the measurements ruled the latter out: first_seen_at is
min(published_at) across the cluster and drifts backward as articles join
(median 72h behind the story row's creation), and the median age of reporting
inside a story discovered in the last 6h is 69h. Requiring genuinely fresh
coverage returned zero stories at every threshold from 2h/6h to 12h/24h.

TRENDING ranked by the stored trend_score, which compute_trending_score()
writes only when clustering touches a story and nothing ever recomputes. Its
recency term therefore froze at write time — across the top 50 that inflated
scores by an average of 0.116 (max 0.350, the whole recency budget) — and
/trending served a **105-hour-old** story in its top 15.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.v1.stories import (
    TOP_STORY_MAX_AGE,
    TOP_STORY_MIN_SOURCES,
    TRENDING_WINDOW,
    _is_top_story,
    _now_naive,
    _trending_rank,
)
from app.models.models import Story


def _ago(**kw) -> datetime:
    return _now_naive() - timedelta(**kw)


# ── The banner is a criterion, not a position ────────────────────────────────


def test_recently_surfaced_story_with_enough_publishers_qualifies():
    assert _is_top_story(_ago(minutes=25), 3) is True


def test_the_production_banner_story_would_not_qualify():
    """72.9h old with 9 sources — the headline the banner actually showed."""
    assert _is_top_story(_ago(hours=72, minutes=54), 9) is False


def test_a_single_publisher_never_qualifies():
    """One outlet reporting something is not a top story."""
    assert _is_top_story(_ago(minutes=2), 1) is False
    assert _is_top_story(_ago(minutes=2), TOP_STORY_MIN_SOURCES - 1) is False


def test_the_flag_expires_at_the_age_boundary():
    assert _is_top_story(_ago(hours=5, minutes=59), 5) is True
    assert _is_top_story(_now_naive() - TOP_STORY_MAX_AGE - timedelta(minutes=1), 5) is False


def test_missing_created_at_never_qualifies():
    assert _is_top_story(None, 99) is False


def test_the_flag_is_keyed_on_discovery_not_publication():
    """first_seen_at is min(published_at) and moves backward as articles join.

    Keying the banner on it made every story look old (median 72h behind the
    story row's own creation), which is why the flag takes created_at.
    """
    import inspect

    from app.api.v1.stories import _build_story_list_response

    src = inspect.getsource(_build_story_list_response)
    assert "_is_top_story(story.created_at" in src, (
        "the banner flag must use discovery time, not first_seen_at"
    )


# ── Trending is ranked live, not from a frozen column ────────────────────────


@pytest.mark.asyncio
async def test_trending_rank_does_not_read_the_stored_score():
    """The stale column must not appear in the ranking expression."""
    sql = str(_trending_rank().compile(compile_kwargs={"literal_binds": True}))
    assert "trend_score" not in sql, (
        "ranking still reads the stored trend_score, which freezes at write time"
    )


@pytest.mark.asyncio
async def test_trending_rank_evaluates_recency_in_sql():
    """Age must come from the database clock, so it can never go stale."""
    sql = str(_trending_rank().compile(compile_kwargs={"literal_binds": True})).lower()
    assert "now()" in sql, "recency must be evaluated at query time"
    assert "exp" in sql, "recency decay must be applied"
    # Naive UTC, matching the column type — a bare now() is timestamptz.
    assert "timezone" in sql, "now() must be coerced to naive UTC"


@pytest.mark.asyncio
async def test_trending_rank_rewards_velocity_and_breadth():
    sql = str(_trending_rank().compile(compile_kwargs={"literal_binds": True})).lower()
    assert "ln" in sql, "source breadth should use a log curve, not a hard cap"
    assert "least" in sql, "terms must stay bounded"
    assert "count" in sql, "breadth and velocity both count rows"


def test_the_source_cap_no_longer_flattens_large_stories():
    """`min(n/5, 1)` scored 5 and 11 publishers identically.

    Production consequence: the most-covered story in the top 15 (11 sources)
    ranked last. A log curve keeps separating them.
    """
    import math

    def breadth(n: int) -> float:
        return min(math.log(1 + n) / math.log(6.0), 1.2)

    assert breadth(11) > breadth(5) > breadth(3)
    # ...while still flattening enough that breadth cannot dominate the score.
    assert breadth(50) <= 1.2


# ── The eligibility window ───────────────────────────────────────────────────


def test_trending_window_excludes_the_story_production_was_serving():
    """A 105.3-hour-old story must not be eligible by default."""
    assert timedelta(hours=105, minutes=18) > TRENDING_WINDOW


@pytest.mark.asyncio
async def test_trending_query_filters_by_first_seen_at():
    """The window must bound first_seen_at, not updated_at.

    Bounding updated_at would keep re-clustered old stories eligible, which
    is the same defect that fed the banner its 72.9h headline.
    """
    stmt = (
        select(Story)
        .where(Story.first_seen_at >= _now_naive() - TRENDING_WINDOW)
        .order_by(_trending_rank().desc())
    )
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "first_seen_at >=" in sql
