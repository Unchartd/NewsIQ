"""API endpoints for news stories, feeds, analytics, search, and categories."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_user
from app.models.models import (
    Article,
    Bookmark,
    CanonicalEntity,
    Category,
    Source,
    Story,
    StoryArticle,
    StoryDifference,
    StoryEntity,
    StoryMetric,
    StorySourceCoverage,
    StoryTag,
    User,
    UserCategory,
    UserEvent,
    UserLocation,
)
from app.schemas.story import (
    CategoryResponse,
    FetchNewsRequest,
    FetchNewsResponse,
    PopularSourceWidget,
    ProcessStoryResponse,
    SearchResultResponse,
    SourceComparisonItem,
    SourceInStory,
    StoryArticleResponse,
    StoryComparisonResponse,
    StoryDetailResponse,
    StoryListResponse,
    TrendingTopicWidget,
    TrendingWidgetsResponse,
)
from app.services.cache_service import TTL_STORY, cache_service
from app.services.search_service import search_service

router = APIRouter()


# Only stories first seen inside this window are eligible for /trending.
# Without it, any active story ranked forever: production served a
# 105-hour-old story in the top 15.
TRENDING_WINDOW = timedelta(hours=48)

# Fresh coverage arriving inside this window is what "trending" means, as
# distinct from "big". A 9-source story assembled over three days and a
# 5-source story assembled in forty minutes are different things, and the
# stored score could not tell them apart.
VELOCITY_WINDOW = timedelta(hours=6)

_RECENCY_DECAY_PER_HOUR = 0.1155  # ln(2)/6 → six-hour half-life


def _now_naive() -> datetime:
    """Wall clock in the same naive-UTC form the timestamp columns use."""
    return datetime.now(UTC).replace(tzinfo=None)


def _trending_rank():
    """Live trending score, evaluated by Postgres at query time.

        0.35 x source breadth + 0.35 x recency + 0.30 x velocity

    Source breadth uses a log curve rather than the stored formula's
    `min(n/5, 1)`: that cap made every story with 5+ publishers score
    identically, so the most-covered story in production (11 sources) ranked
    15th behind three-source stories.
    """
    source_count = (
        select(func.count(func.distinct(Article.source_id)))
        .select_from(StoryArticle)
        .join(Article, Article.id == StoryArticle.article_id)
        .where(StoryArticle.story_id == Story.id)
        .correlate(Story)
        .scalar_subquery()
    )
    recent_articles = (
        select(func.count())
        .select_from(StoryArticle)
        .join(Article, Article.id == StoryArticle.article_id)
        .where(
            StoryArticle.story_id == Story.id,
            Article.created_at >= _now_naive() - VELOCITY_WINDOW,
        )
        .correlate(Story)
        .scalar_subquery()
    )

    breadth = func.least(func.ln(1 + source_count) / func.ln(6.0), 1.2)

    # timezone('utc', now()) keeps this naive, matching the column type;
    # a bare now() is timestamptz and would compare against session time.
    age_hours = (
        func.extract("epoch", func.timezone("utc", func.now()) - Story.first_seen_at) / 3600.0
    )
    recency = func.exp(-_RECENCY_DECAY_PER_HOUR * func.greatest(age_hours, 0.0))

    velocity = func.least(recent_articles / 5.0, 1.0)

    return 0.35 * breadth + 0.35 * recency + 0.30 * velocity


# The home banner's headline slot: a story we surfaced recently that several
# independent publishers are covering.
#
# It is deliberately NOT called "breaking", and it keys on created_at
# (discovery) rather than first_seen_at (publication). Two measurements
# forced both choices:
#
#   * first_seen_at is min(published_at) across the cluster, so it moves
#     BACKWARD as older articles join and is not a story age at all. Median
#     gap between it and the story row being created: 72 hours.
#   * Median age of the actual reporting inside a story we discovered in the
#     last 6h is 69 hours. Requiring genuinely fresh coverage returns zero
#     stories at every threshold tried (2h/6h through 12h/24h).
#
# A pipeline three days behind publication cannot truthfully say BREAKING.
# It can truthfully say "we just surfaced this and N publishers are on it",
# which is what this flag means and what the banner now says.
TOP_STORY_MAX_AGE = timedelta(hours=6)
TOP_STORY_MIN_SOURCES = 3


def _is_top_story(created_at: datetime | None, source_count: int) -> bool:
    """Recently surfaced by us, with several publishers already covering it."""
    if created_at is None or source_count < TOP_STORY_MIN_SOURCES:
        return False
    # Stored naive UTC; compare like for like.
    return (datetime.now(UTC).replace(tzinfo=None) - created_at) <= TOP_STORY_MAX_AGE


def _build_story_list_response(
    story: Story, cluster_confidence: float | None = None
) -> StoryListResponse:
    """Map a Story ORM object to StoryListResponse."""
    logos: list[str] = []
    source_ids: set[uuid.UUID] = set()
    for art_link in story.articles:
        if art_link.article and art_link.article.source:
            source_ids.add(art_link.article.source.id)
            if art_link.article.source.logo_url and art_link.article.source.logo_url not in logos:
                logos.append(art_link.article.source.logo_url)

    return StoryListResponse(
        id=story.id,
        headline=story.headline,
        one_line_summary=story.one_line_summary,
        short_summary=story.short_summary,
        location_country=story.location_country,
        location_state=story.location_state,
        location_city=story.location_city,
        trend_score=float(story.trend_score) if story.trend_score is not None else 0.0,
        first_seen_at=story.first_seen_at,
        updated_at=story.updated_at,
        category=story.category,
        article_count=len(story.articles),
        source_count=len(source_ids),
        source_logos=logos[:5],
        story_status=story.story_status or "active",
        cluster_confidence=cluster_confidence,
        is_top_story=_is_top_story(story.created_at, len(source_ids)),
    )


async def _build_story_list_responses(
    stories: Sequence[Story], db: AsyncSession
) -> list[StoryListResponse]:
    """Build StoryListResponse list in batch with dynamic similarity calculations."""
    if not stories:
        return []

    story_ids = [s.id for s in stories]

    from app.models.models import ArticleEvent
    from app.services.clustering_service import clustering_service

    events_result = await db.execute(
        select(ArticleEvent, StoryArticle.story_id)
        .join(StoryArticle, StoryArticle.article_id == ArticleEvent.article_id)
        .where(StoryArticle.story_id.in_(story_ids))
    )
    events_rows = events_result.all()

    # Group events by story_id
    story_events_map: dict[uuid.UUID, list[ArticleEvent]] = {}
    for event, story_id in events_rows:
        if story_id not in story_events_map:
            story_events_map[story_id] = []
        story_events_map[story_id].append(event)

    response_items = []
    for s in stories:
        events = story_events_map.get(s.id, [])
        if len(events) <= 1:
            avg_sim = 1.0
        else:
            total_sim = 0.0
            pairs_count = 0
            for i in range(len(events)):
                for j in range(i + 1, len(events)):
                    total_sim += clustering_service._compute_event_similarity_direct(
                        events[i], events[j]
                    )
                    pairs_count += 1
            avg_sim = total_sim / pairs_count if pairs_count > 0 else 1.0

        response_items.append(_build_story_list_response(s, cluster_confidence=avg_sim))
    return response_items


@router.get("", response_model=list[StoryListResponse])
async def list_stories(
    category: str | None = None,
    country: str | None = None,
    state: str | None = None,
    city: str | None = None,
    q: str | None = Query(None, max_length=200),
    status: str | None = Query("active", description="active, approved, rejected, all"),
    trending: bool = False,
    sort: str | None = Query(None, description="updated_at, first_seen_at, trend_score"),
    after: datetime | None = Query(
        None, description="Filter stories updated or created after this UTC datetime"
    ),
    window_hours: int | None = Query(
        None,
        ge=1,
        le=720,
        description=(
            "Trending eligibility window in hours (default 48). Only applies "
            "when trending=true or sort=trend_score."
        ),
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve news stories with filtering, pagination, and sorting."""
    # ISO timestamps with an offset ("...T00:00:00.000Z") parse as tz-aware,
    # but the timestamp columns are naive UTC — asyncpg refuses to compare
    # them and the request 500s. The news sitemap sends exactly that format,
    # so every one of its requests failed and it rendered empty since launch.
    # isinstance, not `is not None`: tests calling this function directly
    # leave unpassed params as FastAPI Query sentinels.
    if isinstance(after, datetime) and after.tzinfo is not None:
        after = after.astimezone(UTC).replace(tzinfo=None)

    stmt = (
        select(Story)
        .options(
            selectinload(Story.category),
            selectinload(Story.articles)
            .selectinload(StoryArticle.article)
            .selectinload(Article.source),
        )
        .where(
            Story.headline.not_like("[Mock]%"),
            Story.headline.isnot(None),
            Story.headline != "",
            Story.short_summary.isnot(None),
            Story.short_summary != "",
        )
    )

    if status and status != "all":
        stmt = stmt.where(Story.story_status == status)

    if category:
        stmt = stmt.join(Category, Story.category_id == Category.id).where(
            Category.slug == category
        )

    if country:
        stmt = stmt.where(Story.location_country == country)
    if state:
        stmt = stmt.where(Story.location_state == state)
    if city:
        stmt = stmt.where(Story.location_city == city)

    if after:
        if sort == "first_seen_at":
            stmt = stmt.where(Story.first_seen_at >= after)
        else:
            stmt = stmt.where(Story.updated_at >= after)

    if q:
        # Escape SQL LIKE wildcards in user input
        safe_q = q.replace("%", r"\%").replace("_", r"\_")
        stmt = stmt.where(
            Story.headline.ilike(f"%{safe_q}%")
            | Story.one_line_summary.ilike(f"%{safe_q}%")
            | Story.short_summary.ilike(f"%{safe_q}%")
        )

    # Sorting
    if trending or sort == "trend_score":
        # Ranked at read time, not by the stored trend_score.
        #
        # compute_trending_score() runs only when clustering touches a story
        # and nothing ever recomputes it, so its recency term froze at write
        # time. Measured across the top 50 stories, that inflated scores by
        # an average of 0.116 (max 0.350 — the entire recency budget), and
        # /trending was serving a 105-hour-old story. Evaluating the decay in
        # SQL costs nothing at this table size and cannot go stale.
        window = timedelta(hours=window_hours) if window_hours else TRENDING_WINDOW
        stmt = stmt.where(Story.first_seen_at >= _now_naive() - window)
        stmt = stmt.order_by(_trending_rank().desc())
    elif sort == "first_seen_at":
        stmt = stmt.order_by(Story.first_seen_at.desc())
    elif sort == "updated_at":
        stmt = stmt.order_by(Story.updated_at.desc())
    else:
        # first_seen_at, not updated_at: re-synthesis and reconciliation bump
        # updated_at, which floated days-old stories to the top of "Top
        # Stories" — and fed the breaking banner its 72.9-hour-old headline.
        stmt = stmt.order_by(Story.first_seen_at.desc())

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    stories = result.scalars().all()

    return await _build_story_list_responses(stories, db)


@router.get("/search", response_model=list[SearchResultResponse])
async def search_stories(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    category: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across stories.

    Uses Meilisearch when available (ranked relevance) and transparently falls
    back to a PostgreSQL ILIKE query if Meilisearch is unreachable.
    """
    base_options = (
        selectinload(Story.category),
        selectinload(Story.articles)
        .selectinload(StoryArticle.article)
        .selectinload(Article.source),
    )

    # 1. Try Meilisearch first — returns ranked story IDs or None on failure
    matched_ids = await search_service.search(q, category=category, limit=limit, offset=offset)

    if matched_ids is not None:
        if not matched_ids:
            return []
        uuid_ids = [uuid.UUID(i) for i in matched_ids]
        stmt = (
            select(Story)
            .options(*base_options)
            .where(
                Story.id.in_(uuid_ids),
                Story.headline.not_like("[Mock]%"),
                Story.story_status == "active",
                Story.headline.isnot(None),
                Story.headline != "",
                Story.short_summary.isnot(None),
                Story.short_summary != "",
            )
        )
        result = await db.execute(stmt)
        stories_by_id = {s.id: s for s in result.scalars().all()}
        # Preserve Meilisearch ranking order
        stories = [stories_by_id[i] for i in uuid_ids if i in stories_by_id]
    else:
        # 2. PostgreSQL fallback
        safe_q = q.replace("%", r"\%").replace("_", r"\_")
        stmt = (
            select(Story)
            .options(*base_options)
            .where(
                (
                    Story.headline.ilike(f"%{safe_q}%")
                    | Story.one_line_summary.ilike(f"%{safe_q}%")
                    | Story.short_summary.ilike(f"%{safe_q}%")
                    | Story.detailed_summary.ilike(f"%{safe_q}%")
                ),
                Story.headline.not_like("[Mock]%"),
                Story.story_status == "active",
                Story.headline.isnot(None),
                Story.headline != "",
                Story.short_summary.isnot(None),
                Story.short_summary != "",
            )
        )
        if category:
            stmt = stmt.join(Category, Story.category_id == Category.id).where(
                Category.slug == category
            )
        stmt = stmt.order_by(Story.trend_score.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        stories = list(result.scalars().all())

    return [
        SearchResultResponse(
            id=s.id,
            headline=s.headline,
            one_line_summary=s.one_line_summary,
            category=s.category,
            trend_score=float(s.trend_score) if s.trend_score is not None else 0.0,
            updated_at=s.updated_at,
            article_count=len(s.articles),
            source_count=len({sa.article.source_id for sa in s.articles if sa.article}),
        )
        for s in stories
    ]


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Return all available news categories."""
    result = await db.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.get("/feed/personalized", response_model=list[StoryListResponse])
async def personalized_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a feed filtered by the user's preferred categories and locations.

    Falls back to the global trending feed when the user has no preferences set.
    """
    cat_res = await db.execute(
        select(UserCategory.category_id).where(UserCategory.user_id == current_user.id)
    )
    category_ids = [row[0] for row in cat_res.all()]

    loc_res = await db.execute(
        select(UserLocation.country_code).where(
            UserLocation.user_id == current_user.id, UserLocation.country_code.isnot(None)
        )
    )
    countries = [row[0] for row in loc_res.all()]

    stmt = (
        select(Story)
        .options(
            selectinload(Story.category),
            selectinload(Story.articles)
            .selectinload(StoryArticle.article)
            .selectinload(Article.source),
        )
        .where(
            Story.headline.not_like("[Mock]%"),
            Story.story_status == "active",
            Story.headline.isnot(None),
            Story.headline != "",
            Story.short_summary.isnot(None),
            Story.short_summary != "",
        )
    )

    if category_ids:
        stmt = stmt.where(Story.category_id.in_(category_ids))
    if countries:
        stmt = stmt.where(Story.location_country.in_(countries))

    stmt = stmt.order_by(Story.trend_score.desc(), Story.updated_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    stories = result.scalars().all()
    return await _build_story_list_responses(stories, db)


@router.get("/trending-widgets", response_model=TrendingWidgetsResponse)
async def get_trending_widgets(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve trending topics and popular trusted sources for dashboard side widgets."""
    stmt_tags = select(StoryTag.tag_name).group_by(StoryTag.tag_name).limit(4)
    res_tags = await db.execute(stmt_tags)
    tags = res_tags.scalars().all()

    trending_topics = [
        TrendingTopicWidget(topic=tag, count="8 stories", category="general")
        for tag in tags
        if not tag.startswith("fact:")  # Exclude persisted key_facts tags from widget
    ]

    if not trending_topics:
        trending_topics = [
            TrendingTopicWidget(topic="Generative AI", count="12 stories", category="technology"),
            TrendingTopicWidget(topic="Federal Reserve", count="8 stories", category="business"),
            TrendingTopicWidget(topic="Climate Policy", count="6 stories", category="science"),
            TrendingTopicWidget(topic="Space Exploration", count="5 stories", category="science"),
        ]

    stmt_sources = select(Source).where(Source.active).limit(3)
    res_sources = await db.execute(stmt_sources)
    sources = res_sources.scalars().all()

    popular_sources = [
        PopularSourceWidget(name=src.name, slug=src.slug, rating="94% neutrality")
        for src in sources
    ]

    if not popular_sources:
        popular_sources = [
            PopularSourceWidget(name="Reuters", slug="reuters", rating="94% neutrality"),
            PopularSourceWidget(name="BBC News", slug="bbc-news", rating="91% neutrality"),
            PopularSourceWidget(name="Bloomberg", slug="bloomberg", rating="89% neutrality"),
        ]

    return TrendingWidgetsResponse(trending_topics=trending_topics, popular_sources=popular_sources)


@router.get("/bookmarks", response_model=list[StoryListResponse])
async def list_bookmarked_stories(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all stories bookmarked by the current user."""
    stmt = (
        select(Story)
        .join(Bookmark)
        .where(Bookmark.user_id == current_user.id)
        .options(
            selectinload(Story.category),
            selectinload(Story.articles)
            .selectinload(StoryArticle.article)
            .selectinload(Article.source),
        )
    )
    result = await db.execute(stmt)
    stories = result.scalars().all()
    return await _build_story_list_responses(stories, db)


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed story object with timeline, differences, and source coverage.

    The serialized payload is cached in Redis for 15 minutes. View counts are
    always incremented in the database regardless of cache hits.
    """
    cache_key = cache_service.story_key(str(story_id))

    # Increment the view counter directly (keeps metrics accurate on cache hits)
    await db.execute(
        update(StoryMetric)
        .where(StoryMetric.story_id == story_id)
        .values(views=StoryMetric.views + 1)
    )
    await db.commit()

    # Serve from cache when available
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return StoryDetailResponse(**cached)

    stmt = (
        select(Story)
        .options(
            selectinload(Story.category),
            selectinload(Story.timeline_events),
            selectinload(Story.source_coverage).selectinload(StorySourceCoverage.source),
            selectinload(Story.differences).selectinload(StoryDifference.source),
            selectinload(Story.tags),
            selectinload(Story.entities),
            selectinload(Story.metrics),
            selectinload(Story.articles)
            .selectinload(StoryArticle.article)
            .selectinload(Article.source),
        )
        .where(Story.id == story_id)
    )

    res = await db.execute(stmt)
    story = res.scalar_one_or_none()

    if (
        not story
        or story.story_status != "active"
        or not story.headline
        or story.headline.strip() == ""
        or not story.short_summary
        or story.short_summary.strip() == ""
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found.",
        )

    # Ensure a metrics row exists (first view)
    if not story.metrics:
        story.metrics = StoryMetric(story_id=story.id, views=1, bookmarks=0, shares=0, clicks=0)
        await db.commit()

    source_ids = {
        sa.article.source_id for sa in story.articles if sa.article and sa.article.source_id
    }

    mapped_articles = [
        StoryArticleResponse(
            id=sa.article.id,
            title=sa.article.title,
            description=sa.article.description,
            url=sa.article.url,
            author=sa.article.author,
            image_url=sa.article.image_url,
            published_at=sa.article.published_at,
            source=SourceInStory(
                id=sa.article.source.id,
                name=sa.article.source.name,
                slug=sa.article.source.slug,
                website_url=sa.article.source.website_url,
                logo_url=sa.article.source.logo_url,
                country_code=sa.article.source.country_code,
            ),
        )
        for sa in story.articles
        if sa.article and sa.article.source
    ]

    response = StoryDetailResponse(
        id=story.id,
        headline=story.headline,
        one_line_summary=story.one_line_summary,
        short_summary=story.short_summary,
        detailed_summary=story.detailed_summary,
        key_facts=story.key_facts or [],
        location_country=story.location_country,
        location_state=story.location_state,
        location_city=story.location_city,
        trend_score=float(story.trend_score) if story.trend_score is not None else 0.0,
        first_seen_at=story.first_seen_at,
        updated_at=story.updated_at,
        category=story.category,
        source_count=len(source_ids),
        timeline_events=story.timeline_events,
        source_coverage=story.source_coverage,
        differences=story.differences,
        tags=story.tags,
        entities=story.entities,
        metrics=story.metrics,
        articles=mapped_articles,
    )

    # Cache the JSON-serialized payload
    await cache_service.set(cache_key, response.model_dump(mode="json"), ttl=TTL_STORY)

    return response


@router.post("/{story_id}/bookmark", status_code=status.HTTP_201_CREATED)
async def bookmark_story(
    story_id: uuid.UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a story to the user's bookmarks."""
    stmt_story = select(Story).options(selectinload(Story.metrics)).where(Story.id == story_id)
    res_story = await db.execute(stmt_story)
    story = res_story.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")

    stmt_bm = select(Bookmark).where(
        Bookmark.user_id == current_user.id, Bookmark.story_id == story_id
    )
    res_bm = await db.execute(stmt_bm)
    if res_bm.scalar_one_or_none():
        return {"message": "Already bookmarked."}

    bookmark = Bookmark(
        user_id=current_user.id,
        story_id=story_id,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(bookmark)

    if story.metrics:
        story.metrics.bookmarks += 1
    else:
        story.metrics = StoryMetric(story_id=story.id, views=0, bookmarks=1, shares=0, clicks=0)

    # Record UserEvent
    event = UserEvent(
        id=uuid.uuid4(),
        user_id=current_user.id,
        story_id=story_id,
        event_type="bookmark_story",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(event)

    await db.commit()
    await cache_service.invalidate_story(str(story_id))
    return {"message": "Story bookmarked successfully."}


@router.delete("/{story_id}/bookmark", status_code=status.HTTP_200_OK)
async def unbookmark_story(
    story_id: uuid.UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a story from the user's bookmarks."""
    stmt_bm = select(Bookmark).where(
        Bookmark.user_id == current_user.id, Bookmark.story_id == story_id
    )
    res_bm = await db.execute(stmt_bm)
    bookmark = res_bm.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found.")

    await db.delete(bookmark)

    stmt_story = select(Story).options(selectinload(Story.metrics)).where(Story.id == story_id)
    res_story = await db.execute(stmt_story)
    story = res_story.scalar_one_or_none()
    if story and story.metrics and story.metrics.bookmarks > 0:
        story.metrics.bookmarks -= 1

    await db.commit()
    await cache_service.invalidate_story(str(story_id))
    return {"message": "Bookmark removed successfully."}


# ──────────────────────────────────────────────────────────────────────────────
# GET /trending — dedicated trending endpoint with Redis caching
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/trending", response_model=list[StoryListResponse])
async def get_trending_stories(
    category: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Return stories ranked by trending score (multi-signal: source diversity + recency + engagement).

    Results are cached in Redis for 5 minutes. Cache is scoped per category.
    """
    scope = category or "global"
    cache_key = cache_service.trending_key(scope)
    if offset == 0:  # Only cache first page
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return [StoryListResponse(**s) for s in cached]

    stmt = (
        select(Story)
        .options(
            selectinload(Story.category),
            selectinload(Story.articles)
            .selectinload(StoryArticle.article)
            .selectinload(Article.source),
        )
        .where(Story.story_status == "active", Story.headline.not_like("[Mock]%"))
    )

    if category:
        stmt = stmt.join(Category, Story.category_id == Category.id).where(
            Category.slug == category
        )

    stmt = stmt.order_by(Story.trend_score.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    stories = result.scalars().all()
    response = await _build_story_list_responses(stories, db)

    if offset == 0:
        await cache_service.set(
            cache_key,
            [r.model_dump(mode="json") for r in response],
            ttl=5 * 60,
        )

    return response


# ──────────────────────────────────────────────────────────────────────────────
# GET /{id}/comparison — source comparison view
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/{story_id}/comparison", response_model=StoryComparisonResponse)
async def get_story_comparison(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return per-source difference analysis for a story.

    Combines StoryDifference (unique/missing/contradictions) with
    StorySourceCoverage (focus area) into a unified comparison view.
    """
    stmt = (
        select(Story)
        .options(
            selectinload(Story.differences).selectinload(StoryDifference.source),
            selectinload(Story.source_coverage).selectinload(StorySourceCoverage.source),
        )
        .where(Story.id == story_id)
    )
    res = await db.execute(stmt)
    story = res.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")

    # Build a lookup of focus_area by source_id from source_coverage
    focus_by_source: dict[uuid.UUID, str] = {
        sc.source_id: sc.focus_area or "General coverage"
        for sc in story.source_coverage
        if sc.source_id
    }

    # Count unique sources from differences
    source_ids = {d.source_id for d in story.differences if d.source_id}

    comparison_items = []
    for diff in story.differences:
        if not diff.source:
            continue
        src = diff.source
        comparison_items.append(
            SourceComparisonItem(
                source=SourceInStory(
                    id=src.id,
                    name=src.name,
                    slug=src.slug,
                    website_url=src.website_url,
                    logo_url=src.logo_url,
                    country_code=src.country_code,
                ),
                focus_area=focus_by_source.get(src.id, "General coverage"),
                unique_information=diff.unique_information,
                missing_information=diff.missing_information,
                contradictions=diff.contradictions,
            )
        )

    return StoryComparisonResponse(
        story_id=story.id,
        headline=story.headline,
        source_count=len(source_ids),
        sources=comparison_items,
        source_coverage=story.source_coverage,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /entity/{canonical_entity_id}/timeline — entity timeline view
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/entity/{canonical_entity_id}/timeline", response_model=list[StoryListResponse])
async def get_entity_timeline(
    canonical_entity_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all stories linked to a specific Canonical Entity (Entity Timeline).

    Returns stories ordered by updated_at descending.
    """
    # First verify if the Canonical Entity exists
    ent_stmt = select(CanonicalEntity).where(CanonicalEntity.id == canonical_entity_id)
    res_ent = await db.execute(ent_stmt)
    entity = res_ent.scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canonical Entity not found.",
        )

    # Fetch stories linked through StoryEntity
    stmt = (
        select(Story)
        .join(StoryEntity, Story.id == StoryEntity.story_id)
        .where(StoryEntity.canonical_entity_id == canonical_entity_id)
        .options(
            selectinload(Story.category),
            selectinload(Story.articles)
            .selectinload(StoryArticle.article)
            .selectinload(Article.source),
        )
        .order_by(Story.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    stories = result.scalars().all()

    return await _build_story_list_responses(stories, db)


# ──────────────────────────────────────────────────────────────────────────────
# Internal admin trigger endpoints
# ──────────────────────────────────────────────────────────────────────────────


@router.post("/internal/fetch-news", response_model=FetchNewsResponse)
async def trigger_fetch_news(
    request: FetchNewsRequest = Body(default_factory=FetchNewsRequest),
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger news ingestion (admin only).

    Runs GNews API and/or RSS fetching immediately, outside the Celery schedule.
    Use this for testing, seeding data, or immediate refresh after an event.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for internal endpoints.",
        )

    gnews_count = 0
    rss_count = 0

    if request.gnews:
        try:
            from app.services.gnews_service import gnews_service

            results = await gnews_service.ingest_all(db)
            gnews_count = sum(results.values())
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error("Manual GNews fetch failed: %s", exc)

    if request.rss:
        try:
            from app.services.ingestion_service import ingestion_service

            results = await ingestion_service.ingest_all_active_sources(db)
            rss_count = sum(results.values())
        except Exception as exc:
            import logging

            logging.getLogger(__name__).error("Manual RSS fetch failed: %s", exc)

    total = gnews_count + rss_count
    triggered = False
    if total > 0:
        from app.workers.tasks import process_pending_embeddings_task

        process_pending_embeddings_task.delay()
        triggered = True

    return FetchNewsResponse(
        gnews_articles=gnews_count,
        rss_articles=rss_count,
        total_articles=total,
        embedding_triggered=triggered,
    )


@router.post("/internal/process-story", response_model=ProcessStoryResponse)
async def trigger_process_story(
    current_user: User = Depends(require_user),
):
    """Manually trigger the embedding + clustering pipeline (admin only).

    Queues the embedding task and clustering task via Celery.
    Results appear asynchronously — poll GET /stories to see new stories.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for internal endpoints.",
        )

    from app.workers.tasks import cluster_news_task, process_pending_embeddings_task

    embed_result = process_pending_embeddings_task.delay()
    cluster_result = cluster_news_task.delay()

    return ProcessStoryResponse(
        stories_created=0,  # Async — actual count available via Celery result
        articles_clustered=0,
        message=(
            f"Embedding task queued: {embed_result.id}. "
            f"Clustering task queued: {cluster_result.id}. "
            "Check GET /stories in ~30s for new stories."
        ),
    )
