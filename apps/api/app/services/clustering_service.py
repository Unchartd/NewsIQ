"""Service for clustering articles into stories using HDBSCAN and incremental vector match."""

import logging
import uuid
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Article,
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
)
from app.services.ai_service import ai_service
from app.services.ner_service import ner_service
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80  # Cosine similarity threshold for real-time merge


class ClusteringService:
    """Clustering service using HDBSCAN and incremental Qdrant vector lookups."""

    async def get_or_create_category(
        self, slug: str, name: str, session: AsyncSession
    ) -> uuid.UUID:
        """Helper to get a category ID by slug, or create one if missing."""
        stmt = select(Category).where(Category.slug == slug)
        res = await session.execute(stmt)
        cat = res.scalar_one_or_none()
        if cat:
            return cat.id

        # Create category
        new_cat = Category(id=uuid.uuid4(), slug=slug, name=name, icon="globe")
        session.add(new_cat)
        await session.commit()
        return new_cat.id

    async def generate_story_content(
        self, story: Story, articles: list[Article], session: AsyncSession
    ) -> None:
        """Trigger AI generation and NER extraction to populate a story's sub-tables."""
        # 1. Prepare article details for Gemini prompt
        article_data = []
        full_text_corpus = ""
        for art in articles:
            # Fetch source name
            stmt = select(Source).where(Source.id == art.source_id)
            res = await session.execute(stmt)
            source = res.scalar_one_or_none()
            src_name = source.name if source else "Unknown Source"

            article_data.append(
                {
                    "source_name": src_name,
                    "title": art.title,
                    "content": art.content or art.description or "",
                    "published_at": art.published_at.isoformat() if art.published_at else None,
                }
            )
            full_text_corpus += (
                f"{(art.title or '')}\n{(art.description or '')}\n{(art.content or '')}\n\n"
            )

        # 2. Call AI Service
        ai_res = await ai_service.analyze_story(article_data)

        # Update main story details
        story.headline = ai_res.headline
        story.one_line_summary = ai_res.one_line_summary
        story.short_summary = ai_res.short_summary
        story.detailed_summary = ai_res.detailed_summary

        # Clear existing timeline events, differences, entities, tags to regenerate cleanly
        await session.execute(
            select(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id)
        )
        # Clear cascade is handled by SQLAlchemy back_populates cascading, but we can do it explicitly
        story.timeline_events.clear()
        story.differences.clear()
        story.entities.clear()
        story.tags.clear()
        story.source_coverage.clear()

        # 3. Save Timeline Events
        for ev in ai_res.timeline:
            event_time = None
            try:
                # Try parsing standard ISO/times, else default to None or parsed
                event_time = datetime.fromisoformat(ev.date)
            except Exception:
                pass
            story.timeline_events.append(
                StoryTimelineEvent(
                    id=uuid.uuid4(),
                    event_time=event_time,
                    description=f"[{ev.date}] {ev.description}",
                    created_at=datetime.utcnow(),
                )
            )

        # 4. Save Source Coverages & Differences
        for diff in ai_res.differences:
            # Find the source ID by name matching
            stmt = select(Source).where(Source.name == diff.source_name)
            res = await session.execute(stmt)
            source = res.scalar_one_or_none()
            if not source:
                continue

            story.source_coverage.append(
                StorySourceCoverage(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    focus_area=diff.unique_information or "General coverage",
                    published_at=datetime.utcnow(),
                )
            )

            story.differences.append(
                StoryDifference(
                    id=uuid.uuid4(),
                    source_id=source.id,
                    unique_information=diff.unique_information,
                    missing_information=diff.missing_information,
                    contradictions=diff.contradictions,
                )
            )

        # 5. Extract Named Entities using NER Service
        entities = ner_service.extract_entities(full_text_corpus)
        for ent in entities[:15]:  # Limit to top 15 entities for storage
            story.entities.append(
                StoryEntity(id=uuid.uuid4(), entity_type=ent["type"], entity_value=ent["value"])
            )

        # 6. Save Story Tags (Use a few prominent entities or mock tags)
        tags_added = set()
        for ent in entities:
            tag = ent["value"].lower().strip()
            if tag and len(tag) < 30 and tag not in tags_added:
                tags_added.add(tag)
                story.tags.append(StoryTag(id=uuid.uuid4(), tag_name=tag))
                if len(tags_added) >= 5:
                    break

        await session.commit()

    async def merge_article_into_existing_story(
        self, article: Article, story_id: uuid.UUID, session: AsyncSession
    ) -> bool:
        """Merge a new article into an existing story cluster."""
        # Check if relation already exists
        stmt = select(StoryArticle).where(
            StoryArticle.story_id == story_id, StoryArticle.article_id == article.id
        )
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            return False

        # Create link
        link = StoryArticle(story_id=story_id, article_id=article.id)
        session.add(link)
        await session.commit()

        # Retrieve the story and all associated articles to update summaries
        stmt = select(Story).where(Story.id == story_id)
        res = await session.execute(stmt)
        story = res.scalar_one_or_none()

        if story:
            # Get all articles in this story
            stmt = select(Article).join(StoryArticle).where(StoryArticle.story_id == story_id)
            res = await session.execute(stmt)
            all_articles = list(res.scalars().all())

            logger.info(
                "Merging article %s into story %s. Total articles: %d",
                article.id,
                story_id,
                len(all_articles),
            )
            await self.generate_story_content(story, all_articles, session)

            # Recalculate trending score
            await self.compute_trending_score(story, session)

        return True

    async def add_article_to_existing_story_if_similar(
        self, article_id: uuid.UUID, session: AsyncSession
    ) -> bool:
        """Incremental similarity check. Merges article into an existing story if highly similar."""
        stmt = select(Article).where(Article.id == article_id)
        res = await session.execute(stmt)
        article = res.scalar_one_or_none()
        if not article or article.embedding_status != "completed":
            return False

        # Fetch vector from Qdrant
        point_id = str(article_id)
        try:
            point_info = await vector_service.client.retrieve(
                collection_name="articles", ids=[point_id], with_vectors=True
            )
            if not point_info or not point_info[0].vector:
                return False

            vector = point_info[0].vector
        except Exception as e:
            logger.error("Failed to retrieve vector for article %s: %s", article_id, e)
            return False

        # Search for similar articles
        matches = await vector_service.search_similar(
            vector, limit=3, score_threshold=SIMILARITY_THRESHOLD
        )
        for match in matches:
            match_id = match["id"]
            if match_id == article_id:
                continue

            # Check if this similar article is associated with an existing story
            stmt = select(StoryArticle.story_id).where(StoryArticle.article_id == match_id).limit(1)
            res = await session.execute(stmt)
            story_id = res.scalar()
            if story_id:
                # Found a match! Merge it.
                return await self.merge_article_into_existing_story(article, story_id, session)

        return False

    async def run_batch_clustering(self, session: AsyncSession) -> int:
        """Run HDBSCAN clustering on unclustered articles."""
        # 1. Fetch unclustered articles
        # Select articles where embedding is completed and they are not in story_articles
        subquery = select(StoryArticle.article_id)
        stmt = select(Article).where(
            Article.embedding_status == "completed", ~Article.id.in_(subquery)
        )
        res = await session.execute(stmt)
        unclustered_articles = list(res.scalars().all())

        if len(unclustered_articles) < 2:
            logger.info(
                "Not enough unclustered articles to run batch clustering (count: %d).",
                len(unclustered_articles),
            )
            return 0

        logger.info(
            "Running batch clustering on %d unclustered articles.", len(unclustered_articles)
        )

        # Retrieve vectors for all these articles
        article_ids = [str(a.id) for a in unclustered_articles]
        vectors = []
        valid_articles = []

        try:
            points = await vector_service.client.retrieve(
                collection_name="articles", ids=article_ids, with_vectors=True
            )
            points_dict = {uuid.UUID(p.id): p.vector for p in points if p.vector}

            for art in unclustered_articles:
                if art.id in points_dict:
                    vectors.append(points_dict[art.id])
                    valid_articles.append(art)
        except Exception as e:
            logger.error("Failed to fetch vectors for batch clustering: %s", e)
            return 0

        if len(valid_articles) < 2:
            return 0

        # Run HDBSCAN
        from hdbscan import HDBSCAN

        X = np.array(vectors)

        # HDBSCAN parameters suited for small clusters
        clusterer = HDBSCAN(
            min_cluster_size=2,
            min_samples=1,
            metric="euclidean",  # cosine similarity is equivalent to euclidean for normalized vectors
            cluster_selection_epsilon=0.35,  # threshold for maximum distance
        )
        labels = clusterer.fit_predict(X)

        # Group articles by labels
        clusters: dict[int, list[Article]] = {}
        for idx, label in enumerate(labels):
            if label == -1:
                continue  # Outlier
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(valid_articles[idx])

        stories_created = 0
        default_cat_id = await self.get_or_create_category("world", "World", session)

        for label, art_list in clusters.items():
            logger.info("Found cluster label %d with %d articles.", label, len(art_list))

            # Create a new story
            story_id = uuid.uuid4()
            story = Story(
                id=story_id,
                category_id=default_cat_id,
                story_status="active",
                first_seen_at=min(a.published_at or datetime.utcnow() for a in art_list),
                trend_score=1.0,
                updated_at=datetime.utcnow(),
            )
            session.add(story)

            # Initialize metrics
            metrics = StoryMetric(story_id=story_id, views=0, bookmarks=0, shares=0, clicks=0)
            session.add(metrics)

            # Link articles
            for art in art_list:
                link = StoryArticle(story_id=story_id, article_id=art.id)
                session.add(link)

            await session.commit()

            # Populate story summaries & timeline & differences
            try:
                await self.generate_story_content(story, art_list, session)
                await self.compute_trending_score(story, session)
                stories_created += 1
            except Exception as e:
                logger.error("Failed to generate content for story cluster %s: %s", story_id, e)

        return stories_created

    async def compute_trending_score(self, story: Story, session: AsyncSession) -> float:
        """Compute the trending score for a story based on coverage count and recency."""
        # Fetch the count of articles linked to this story
        stmt = select(StoryArticle).where(StoryArticle.story_id == story.id)
        res = await session.execute(stmt)
        article_count = len(res.scalars().all())

        # Recency calculation: hours since first seen
        first_seen = story.first_seen_at or datetime.utcnow()
        hours_elapsed = (datetime.utcnow() - first_seen).total_seconds() / 3600.0

        # Exponential gravity decay factor (similar to Hacker News / Reddit)
        # Score = (article_count) / (hours_elapsed + 2)^1.5
        score = article_count / ((hours_elapsed + 2.0) ** 1.5)

        story.trend_score = score
        await session.commit()
        return score


clustering_service = ClusteringService()
