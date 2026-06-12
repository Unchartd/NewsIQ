"""API endpoints for news stories, feeds, and analytics."""

import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

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
    StoryEntity,
    StoryMetric,
    StorySourceCoverage,
    StoryTag,
    StoryTimelineEvent,
    User,
)
from app.schemas.story import (
    StoryDetailResponse,
    StoryListResponse,
    StoryArticleResponse,
    SourceInStory,
    TrendingWidgetsResponse,
    TrendingTopicWidget,
    PopularSourceWidget,
)

router = APIRouter()


@router.get("", response_model=List[StoryListResponse])
async def list_stories(
    category: Optional[str] = None,
    country: Optional[str] = None,
    state: Optional[str] = None,
    city: Optional[str] = None,
    q: Optional[str] = None,
    trending: bool = False,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve news stories with filtering, pagination, and sorting."""
    stmt = select(Story).options(
        selectinload(Story.category),
        selectinload(Story.articles).selectinload(StoryArticle.article).selectinload(Article.source)
    )

    # Filtering by category slug
    if category:
        stmt = stmt.join(Category).where(Category.slug == category)

    # Filtering by location
    if country:
        stmt = stmt.where(Story.location_country == country)
    if state:
        stmt = stmt.where(Story.location_state == state)
    if city:
        stmt = stmt.where(Story.location_city == city)

    # Filtering by search text
    if q:
        # Simple case-insensitive contains search
        stmt = stmt.where(
            Story.headline.ilike(f"%{q}%") |
            Story.one_line_summary.ilike(f"%{q}%") |
            Story.short_summary.ilike(f"%{q}%")
        )

    # Sorting
    if trending:
        stmt = stmt.order_by(Story.trend_score.desc())
    else:
        stmt = stmt.order_by(Story.updated_at.desc())

    # Pagination
    stmt = stmt.limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    stories = result.scalars().all()

    # Map to StoryListResponse
    response_list = []
    for story in stories:
        # Gather source logos and total count
        logos = []
        for art_link in story.articles:
            if art_link.article and art_link.article.source and art_link.article.source.logo_url:
                logos.append(art_link.article.source.logo_url)
        # Ensure logos are unique
        logos = list(set(logos))

        response_list.append(
            StoryListResponse(
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
                source_logos=logos[:5]  # Limit to first 5 source logos
            )
        )

    return response_list


@router.get("/trending-widgets", response_model=TrendingWidgetsResponse)
async def get_trending_widgets(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve trending topics and popular trusted sources for dashboard side widgets."""
    # Retrieve top active tags
    stmt_tags = select(StoryTag.tag_name).group_by(StoryTag.tag_name).limit(4)
    res_tags = await db.execute(stmt_tags)
    tags = res_tags.scalars().all()
    
    trending_topics = []
    for i, tag in enumerate(tags):
        trending_topics.append(
            TrendingTopicWidget(
                topic=tag,
                count="8 stories",
                category="general"
            )
        )
    
    # Fallback to default trending topics if DB is empty
    if not trending_topics:
        trending_topics = [
            TrendingTopicWidget(topic="Generative AI", count="12 stories", category="technology"),
            TrendingTopicWidget(topic="Federal Reserve", count="8 stories", category="business"),
            TrendingTopicWidget(topic="Climate Policy", count="6 stories", category="science"),
            TrendingTopicWidget(topic="Space Exploration", count="5 stories", category="science")
        ]

    # Retrieve popular sources
    stmt_sources = select(Source).where(Source.active == True).limit(3)
    res_sources = await db.execute(stmt_sources)
    sources = res_sources.scalars().all()

    popular_sources = []
    for src in sources:
        popular_sources.append(
            PopularSourceWidget(
                name=src.name,
                slug=src.slug,
                rating="94% neutrality"
            )
        )

    # Fallback default sources
    if not popular_sources:
        popular_sources = [
            PopularSourceWidget(name="Reuters", slug="reuters", rating="94% neutrality"),
            PopularSourceWidget(name="BBC News", slug="bbc-news", rating="91% neutrality"),
            PopularSourceWidget(name="Bloomberg", slug="bloomberg", rating="89% neutrality")
        ]

    return TrendingWidgetsResponse(
        trending_topics=trending_topics,
        popular_sources=popular_sources
    )


@router.get("/bookmarks", response_model=List[StoryListResponse])
async def list_bookmarked_stories(
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all stories bookmarked by the current user."""
    stmt = select(Story).join(Bookmark).where(Bookmark.user_id == current_user.id).options(
        selectinload(Story.category),
        selectinload(Story.articles).selectinload(StoryArticle.article).selectinload(Article.source)
    )
    result = await db.execute(stmt)
    stories = result.scalars().all()

    response_list = []
    for story in stories:
        logos = []
        for art_link in story.articles:
            if art_link.article and art_link.article.source and art_link.article.source.logo_url:
                logos.append(art_link.article.source.logo_url)
        logos = list(set(logos))

        response_list.append(
            StoryListResponse(
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
                source_logos=logos[:5]
            )
        )
    return response_list


@router.get("/{story_id}", response_model=StoryDetailResponse)
async def get_story_detail(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed story object with timeline, differences, and source coverage."""
    # We load all related items using selectinload
    stmt = select(Story).options(
        selectinload(Story.category),
        selectinload(Story.timeline_events),
        selectinload(Story.source_coverage).selectinload(StorySourceCoverage.source),
        selectinload(Story.differences).selectinload(StoryDifference.source),
        selectinload(Story.tags),
        selectinload(Story.entities),
        selectinload(Story.metrics),
        selectinload(Story.articles).selectinload(StoryArticle.article).selectinload(Article.source)
    ).where(Story.id == story_id)
    
    res = await db.execute(stmt)
    story = res.scalar_one_or_none()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found.",
        )

    # Increment views counter in background/metrics
    if story.metrics:
        story.metrics.views += 1
    else:
        story.metrics = StoryMetric(story_id=story.id, views=1, bookmarks=0, shares=0, clicks=0)
    await db.commit()

    # Map articles to Pydantic responses
    mapped_articles = []
    for sa in story.articles:
        if sa.article:
            mapped_articles.append(
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
                        country_code=sa.article.source.country_code
                    )
                )
            )

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
        timeline_events=story.timeline_events,
        source_coverage=story.source_coverage,
        differences=story.differences,
        tags=story.tags,
        entities=story.entities,
        metrics=story.metrics,
        articles=mapped_articles
    )


@router.post("/{story_id}/bookmark", status_code=status.HTTP_201_CREATED)
async def bookmark_story(
    story_id: uuid.UUID,
    current_user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a story to the user's bookmarks."""
    # Check if story exists
    stmt_story = select(Story).where(Story.id == story_id)
    res_story = await db.execute(stmt_story)
    story = res_story.scalar_one_or_none()
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found.",
        )

    # Check if already bookmarked
    stmt_bm = select(Bookmark).where(
        Bookmark.user_id == current_user.id,
        Bookmark.story_id == story_id
    )
    res_bm = await db.execute(stmt_bm)
    if res_bm.scalar_one_or_none():
        return {"message": "Already bookmarked."}

    bookmark = Bookmark(user_id=current_user.id, story_id=story_id, created_at=datetime.utcnow())
    db.add(bookmark)
    
    # Increment bookmarks metric
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
        Bookmark.user_id == current_user.id,
        Bookmark.story_id == story_id
    )
    res_bm = await db.execute(stmt_bm)
    bookmark = res_bm.scalar_one_or_none()
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bookmark not found.",
        )

    await db.delete(bookmark)
    
    # Decrement bookmarks metric
    stmt_story = select(Story).where(Story.id == story_id)
    res_story = await db.execute(stmt_story)
    story = res_story.scalar_one_or_none()
    if story and story.metrics and story.metrics.bookmarks > 0:
        story.metrics.bookmarks -= 1

    await db.commit()
    return {"message": "Bookmark removed successfully."}
