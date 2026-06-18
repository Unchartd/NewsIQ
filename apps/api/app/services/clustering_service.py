"""Service for clustering articles into stories using HDBSCAN and incremental vector match."""

import logging
import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete, func, select
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
from app.services.ai_service import CATEGORY_SLUGS, ai_service
from app.services.ner_service import ner_service
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80  # Cosine similarity threshold for real-time merge


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
        new_cat = Category(id=uuid.uuid4(), slug=slug, name=name.title(), icon="globe")
        session.add(new_cat)
        await session.commit()
        return new_cat.id

    async def _ensure_all_categories(self, session: AsyncSession) -> None:
        """Ensure all canonical category slugs exist in the DB."""
        for slug in CATEGORY_SLUGS:
            await self.get_or_create_category(slug, slug.replace("-", " ").title(), session)

    async def generate_story_content(
        self, story: Story, articles: list[Article], session: AsyncSession
    ) -> None:
        """Trigger AI generation and NER extraction to populate a story's sub-tables."""
        # 1. Prepare article details for Gemini prompt
        article_data = []
        full_text_corpus = ""
        source_countries = []
        for art in articles:
            # Fetch source name
            stmt = select(Source).where(Source.id == art.source_id)
            res = await session.execute(stmt)
            source = res.scalar_one_or_none()
            src_name = source.name if source else "Unknown Source"
            if source and source.country_code:
                source_countries.append(source.country_code)

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
        # Persist key_facts to JSONB column (previously discarded)
        story.key_facts = [f for f in ai_res.key_facts if f] if ai_res.key_facts else []

        # Resolve and assign location_country from article sources
        if source_countries:
            from collections import Counter
            story.location_country = Counter(source_countries).most_common(1)[0][0]
        else:
            story.location_country = None

        # 3. Resolve and assign category from AI response
        cat_slug = ai_res.category if ai_res.category in CATEGORY_SLUGS else "world"
        cat_id = await self.get_or_create_category(
            cat_slug, cat_slug.replace("-", " ").title(), session
        )
        story.category_id = cat_id

        # 4. Clear existing sub-table rows explicitly before regenerating
        #    Using DELETE statements is safer than .clear() on lazy-loaded collections
        await session.execute(
            delete(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id)
        )
        await session.execute(
            delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story.id)
        )
        await session.execute(
            delete(StoryDifference).where(StoryDifference.story_id == story.id)
        )
        await session.execute(
            delete(StoryEntity).where(StoryEntity.story_id == story.id)
        )
        await session.execute(
            delete(StoryTag).where(StoryTag.story_id == story.id)
        )
        await session.flush()

        # 5. Save Timeline Events
        for ev in ai_res.timeline:
            event_time: datetime | None = None
            try:
                event_time = datetime.fromisoformat(ev.date)
            except (ValueError, TypeError):
                pass  # Store raw string; frontend will display it as-is

            session.add(
                StoryTimelineEvent(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    event_time=event_time,
                    event_time_raw=ev.date,  # Always store the raw AI string
                    description=ev.description,
                    created_at=_now(),
                )
            )

        # 6. Save Source Coverages & Differences
        seen_sources: set[uuid.UUID] = set()
        for diff in ai_res.differences:
            stmt = select(Source).where(Source.name == diff.source_name)
            res = await session.execute(stmt)
            source = res.scalar_one_or_none()
            if not source or source.id in seen_sources:
                continue
            seen_sources.add(source.id)

            # Distill focus_area to a clean short label (max 100 chars, first sentence)
            raw_focus = diff.unique_information or "General coverage"
            first_sentence = raw_focus.split(".")[0].strip()
            focus_area = (first_sentence[:100] + ".") if first_sentence else "General coverage"

            session.add(
                StorySourceCoverage(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    source_id=source.id,
                    focus_area=focus_area,
                    published_at=_now(),
                )
            )
            session.add(
                StoryDifference(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    source_id=source.id,
                    unique_information=diff.unique_information,
                    missing_information=diff.missing_information,
                    contradictions=diff.contradictions,
                )
            )

        # 7. Extract Named Entities using NER Service
        entities = ner_service.extract_entities(full_text_corpus)
        for ent in entities[:15]:  # Limit to top 15 entities for storage
            session.add(
                StoryEntity(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    entity_type=ent["type"],
                    entity_value=ent["value"],
                )
            )

        # 8. Save Story Tags from entities
        tags_added: set[str] = set()
        for ent in entities:
            tag = ent["value"].lower().strip()
            if tag and len(tag) < 30 and tag not in tags_added:
                tags_added.add(tag)
                session.add(StoryTag(id=uuid.uuid4(), story_id=story.id, tag_name=tag))
                if len(tags_added) >= 5:
                    break

        # 9. key_facts are now stored in story.key_facts JSONB — no longer need fact: tags
        # (The prefixed-tag approach was a workaround; keep tags clean for display)

        await session.commit()

        # 10. Index in Meilisearch and invalidate caches for this story
        await self._index_and_invalidate(story, cat_slug, list(tags_added))

    async def _index_and_invalidate(
        self,
        story: Story,
        category_slug: str | None,
        tags: list[str],
    ) -> None:
        """Push the story document to Meilisearch and clear its Redis caches."""
        try:
            from app.services.cache_service import cache_service
            from app.services.search_service import build_story_document, search_service

            public_tags = [t for t in tags if not t.startswith("fact:")]
            document = build_story_document(story, category_slug, public_tags)
            await search_service.index_story(document)
            await cache_service.invalidate_story(str(story.id))
        except Exception as e:
            logger.warning("Failed to index/invalidate story %s: %s", story.id, e)

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
                return await self.merge_article_into_existing_story(article, story_id, session)

        return False

    async def run_batch_clustering(self, session: AsyncSession) -> int:
        """Run HDBSCAN clustering on unclustered articles."""
        # Ensure all canonical categories exist
        await self._ensure_all_categories(session)

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

        clusterer = HDBSCAN(
            min_cluster_size=2,
            min_samples=1,
            metric="euclidean",
            cluster_selection_epsilon=0.35,
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

        for label, art_list in clusters.items():
            logger.info("Found cluster label %d with %d articles.", label, len(art_list))

            story_id = uuid.uuid4()
            now = _now()
            story = Story(
                id=story_id,
                story_status="active",
                first_seen_at=min(
                    (a.published_at for a in art_list if a.published_at), default=now
                ),
                trend_score=1.0,
                created_at=now,
                updated_at=now,
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

            # Populate story summaries, timeline, differences, and category
            try:
                await self.generate_story_content(story, art_list, session)
                await self.compute_trending_score(story, session)
                stories_created += 1
            except Exception as e:
                logger.error("Failed to generate content for story cluster %s: %s", story_id, e)

        return stories_created

    async def compute_trending_score(self, story: Story, session: AsyncSession) -> float:
        """Compute a multi-signal trending score for a story.

        Formula:
            score = (0.40 × source_score) + (0.35 × recency_score) + (0.25 × engagement_score)

        source_score:      Unique source count / 5, capped at 1.0
        recency_score:     Exponential decay with 6-hour half-life
        engagement_score:  Weighted (views×1 + bookmarks×3 + shares×5) / 500, capped at 1.0
        """
        import math

        # ── Source diversity score ────────────────────────────────────────────
        # Count distinct sources contributing articles to this story
        stmt_sources = (
            select(func.count(func.distinct(Article.source_id)))
            .join(StoryArticle, Article.id == StoryArticle.article_id)
            .where(StoryArticle.story_id == story.id)
        )
        res = await session.execute(stmt_sources)
        unique_source_count: int = res.scalar_one() or 0
        source_score = min(unique_source_count / 5.0, 1.0)

        # ── Recency score (exponential decay, half-life = 6 hours) ────────────
        first_seen = story.first_seen_at or _now()
        hours_elapsed = max((_now() - first_seen).total_seconds() / 3600.0, 0)
        recency_score = math.exp(-0.1155 * hours_elapsed)  # ln(2)/6 ≈ 0.1155

        # ── Engagement score ──────────────────────────────────────────────────
        engagement_score = 0.0
        if story.metrics:
            m = story.metrics
            raw = (m.views or 0) * 1 + (m.bookmarks or 0) * 3 + (m.shares or 0) * 5
            engagement_score = min(raw / 500.0, 1.0)

        # ── Weighted composite ────────────────────────────────────────────────
        score = (0.40 * source_score) + (0.35 * recency_score) + (0.25 * engagement_score)

        story.trend_score = score
        await session.commit()

        logger.debug(
            "Trending score for story %s: %.4f "
            "(source=%.2f, recency=%.2f, engagement=%.2f, hours=%.1f)",
            story.id, score, source_score, recency_score, engagement_score, hours_elapsed,
        )
        return score


clustering_service = ClusteringService()

