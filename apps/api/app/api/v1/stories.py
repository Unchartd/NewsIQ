"""API endpoints for news stories, feeds, analytics, search, and categories."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_user
from app.models.models import (
    Article,
    Bookmark,
    Category,
    Source,
    Story,
    StoryArticle,
    StoryDifference,
    StoryMetric,
    StorySourceCoverage,
    StoryTag,
    User,
    UserCategory,
    UserLocation,
)
from app.schemas.story import (
    CategoryResponse,
    PopularSourceWidget,
    SearchResultResponse,
    SourceInStory,
    StoryArticleResponse,
    StoryDetailResponse,
    StoryListResponse,
    TrendingTopicWidget,
    TrendingWidgetsResponse,
)
from app.services.cache_service import TTL_STORY, cache_service
from app.services.search_service import search_service

router = APIRouter()


def _build_story_list_response(story: Story) -> StoryListResponse:
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
    )


@router.get("", response_model=list[StoryListResponse])
async def list_stories(
    category: str | None = None,
    country: str | None = None,
    state: str | None = None,
    city: str | None = None,
    q: str | None = Query(None, max_length=200),
    trending: bool = False,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve news stories with filtering, pagination, and sorting."""
    stmt = select(Story).options(
        selectinload(Story.category),
        selectinload(Story.articles)
        .selectinload(StoryArticle.article)
        .selectinload(Article.source),
    )

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

    if q:
        # Escape SQL LIKE wildcards in user input
        safe_q = q.replace("%", r"\%").replace("_", r"\_")
        stmt = stmt.where(
            Story.headline.ilike(f"%{safe_q}%")
            | Story.one_line_summary.ilike(f"%{safe_q}%")
            | Story.short_summary.ilike(f"%{safe_q}%")
        )

    if trending:
        stmt = stmt.order_by(Story.trend_score.desc())
    else:
        stmt = stmt.order_by(Story.updated_at.desc())

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    stories = result.scalars().all()

    return [_build_story_list_response(s) for s in stories]


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
        stmt = select(Story).options(*base_options).where(Story.id.in_(uuid_ids))
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
                Story.headline.ilike(f"%{safe_q}%")
                | Story.one_line_summary.ilike(f"%{safe_q}%")
                | Story.short_summary.ilike(f"%{safe_q}%")
                | Story.detailed_summary.ilike(f"%{safe_q}%")
            )
        )
        if category:
            stmt = stmt.join(Category, Story.category_id == Category.id).where(
                Category.slug == category
            )
        stmt = stmt.order_by(Story.trend_score.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        stories = result.scalars().all()

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

    Falls back to the global recency feed when the user has no preferences set.
    """
    # Resolve preferred category IDs
    cat_res = await db.execute(
        select(UserCategory.category_id).where(UserCategory.user_id == current_user.id)
    )
    category_ids = [row[0] for row in cat_res.all()]

    # Resolve preferred country codes
    loc_res = await db.execute(
        select(UserLocation.country_code).where(
            UserLocation.user_id == current_user.id, UserLocation.country_code.isnot(None)
        )
    )
    countries = [row[0] for row in loc_res.all()]

    stmt = select(Story).options(
        selectinload(Story.category),
        selectinload(Story.articles)
        .selectinload(StoryArticle.article)
        .selectinload(Article.source),
    )

    if category_ids:
        stmt = stmt.where(Story.category_id.in_(category_ids))
    if countries:
        stmt = stmt.where(Story.location_country.in_(countries))

    stmt = stmt.order_by(Story.trend_score.desc(), Story.updated_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    stories = result.scalars().all()
    return [_build_story_list_response(s) for s in stories]


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
    return [_build_story_list_response(s) for s in stories]


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed story object with timeline, differences, and source coverage."""
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

    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found.",
        )

    # Increment views counter
    if story.metrics:
        story.metrics.views += 1
    else:
        story.metrics = StoryMetric(story_id=story.id, views=1, bookmarks=0, shares=0, clicks=0)
    await db.commit()

    # Compute source_count from unique source IDs across linked articles
    source_ids = {
        sa.article.source_id for sa in story.articles if sa.article and sa.article.source_id
    }

    # Map articles to Pydantic responses
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

    return StoryDetailResponse(
        id=story.id,
        headline=story.headline,
        one_line_summary=story.one_line_summary,
        short_summary=story.short_summary,
        detailed_summary=story.detailed_summary,
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


@router.post("/{story_id}/bookmark", status_code=status.HTTP_201_CREATED)
async def bookmark_story(
    story_id: uuid.UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a story to the user's bookmarks."""
    stmt_story = select(Story).where(Story.id == story_id)
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

    await db.commit()
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

    stmt_story = select(Story).where(Story.id == story_id)
    res_story = await db.execute(stmt_story)
    story = res_story.scalar_one_or_none()
    if story and story.metrics and story.metrics.bookmarks > 0:
        story.metrics.bookmarks -= 1

    await db.commit()
    return {"message": "Bookmark removed successfully."}
