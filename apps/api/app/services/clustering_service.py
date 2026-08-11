"""Service for clustering articles into stories using HDBSCAN and incremental vector match."""

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import numpy as np
import yaml
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import engine
from app.core.metrics import (
    newsiq_clustering_candidates,
    newsiq_clustering_eligible_articles,
    newsiq_clustering_similarity,
    newsiq_discovery_clusters_total,
    newsiq_reflection_requests_total,
    newsiq_stage_a_validation_total,
    newsiq_story_article_count,
)
from app.core.trace import PipelineStage, StageSpan
from app.models.models import (
    Article,
    ArticleEntity,
    ArticleEvent,
    Category,
    Source,
    Story,
    StoryArticle,
    StoryContradiction,
    StoryDifference,
    StoryEntity,
    StoryLifecycleState,
    StoryMetric,
    StorySourceCoverage,
    StoryTag,
    StoryTimelineEvent,
)
from app.services.ai_service import CATEGORY_SLUGS, ai_service
from app.services.contradiction_service import contradiction_service
from app.services.entity_linker import entity_linker
from app.services.event_identity_service import event_identity_service
from app.services.event_validation_service import (
    StoryAnchor,
    ValidationOutcome,
    event_validation_service,
)
from app.services.knowledge_graph import build_story_knowledge_graph
from app.services.ner_service_v2 import ner_service_v2
from app.services.source_comparison_service import source_comparison_service
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)

# Load tunable thresholds from config rather than hardcoding them at call sites.
config_path = os.path.join(os.path.dirname(__file__), "..", "config", "event_validation.yaml")
with open(config_path) as f:
    config = yaml.safe_load(f)

REFLECTION_THRESHOLD = config.get("reflection", {}).get("threshold", 0.55)

_batch_cfg = config.get("batch_clustering", {})
# Merge two sub-clusters outright above this combined similarity.
AUTO_MERGE_THRESHOLD = _batch_cfg.get("auto_merge", 0.90)
# Between agent_review and auto_merge, defer to the verification agents.
AGENT_REVIEW_THRESHOLD = _batch_cfg.get("agent_review", 0.70)
# Applied only when the agents are unreachable and the decision degrades to a
# bare threshold comparison.
DETERMINISTIC_FALLBACK_THRESHOLD = _batch_cfg.get("deterministic_fallback", 0.80)

_OPENAI_VERIFICATION_MODEL = config.get("agents", {}).get(
    "openai_verification_model", "gpt-4o-mini"
)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def uuid_to_advisory_lock_id(u: uuid.UUID) -> int:
    """Fold a 128-bit UUID into a signed 64-bit integer lock ID."""
    val = u.int
    upper = val >> 64
    lower = val & 0xFFFFFFFFFFFFFFFF
    lock_id = (upper ^ lower) & 0xFFFFFFFFFFFFFFFF
    if lock_id >= 0x8000000000000000:
        lock_id -= 0x10000000000000000
    return lock_id


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
        self, story: Story, articles: list[Article], session: AsyncSession, commit: bool = True
    ) -> None:
        """Trigger AI generation and NER extraction to populate a story's sub-tables."""
        # 1. Clear existing sub-table rows explicitly before regenerating
        #    Using DELETE statements is safer than .clear() on lazy-loaded collections
        await session.execute(
            delete(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id)
        )
        await session.execute(
            delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story.id)
        )
        await session.execute(delete(StoryDifference).where(StoryDifference.story_id == story.id))
        await session.execute(delete(StoryEntity).where(StoryEntity.story_id == story.id))
        await session.execute(delete(StoryTag).where(StoryTag.story_id == story.id))
        await session.execute(
            delete(StoryContradiction).where(StoryContradiction.story_id == story.id)
        )
        await session.flush()

        # 2. Prepare article details, fetch sources and article events
        #    Single batch SELECT instead of N per-article queries (B06 fix)
        full_text_corpus = ""
        source_countries = []
        seen_sources: set = set()
        sources_list = []
        article_source_map = {}

        # Collect all distinct source_ids up front
        source_ids = list({art.source_id for art in articles if art.source_id is not None})
        if source_ids:
            src_res = await session.execute(select(Source).where(Source.id.in_(source_ids)))
            source_by_id: dict = {src.id: src for src in src_res.scalars().all()}
        else:
            source_by_id = {}

        for art in articles:
            source = source_by_id.get(art.source_id)
            if source:
                article_source_map[art.id] = source.name
                if source.country_code:
                    source_countries.append(source.country_code)
                if source.id not in seen_sources:
                    seen_sources.add(source.id)
                    sources_list.append(source)
            else:
                article_source_map[art.id] = "Unknown Source"

            full_text_corpus += (
                f"{(art.title or '')}\n{(art.description or '')}\n{(art.content or '')}\n\n"
            )

        # Resolve and assign location_country from article sources
        if source_countries:
            from collections import Counter

            story.location_country = Counter(source_countries).most_common(1)[0][0]
        else:
            story.location_country = None

        # 4. Extract Named Entities — use pre-extracted ArticleEntities if available
        entities = []
        async with StageSpan(stage=PipelineStage.ENTITY_EXTRACTION, story_id=str(story.id)) as span:
            # Check if articles have pre-extracted entities from the event extraction phase
            article_ids = [art.id for art in articles]
            pre_extracted_stmt = select(ArticleEntity).where(
                ArticleEntity.article_id.in_(article_ids)
            )
            pre_result = await session.execute(pre_extracted_stmt)
            pre_entities = list(pre_result.scalars().all())

            if pre_entities:
                # Use pre-extracted article-level entities — no redundant LLM call
                entities = [{"type": e.entity_type, "value": e.entity_value} for e in pre_entities]
                logger.info(
                    "Using %d pre-extracted article entities for story %s.",
                    len(entities),
                    story.id,
                )
            else:
                # Fallback: run NER v2 on full corpus (for old articles without pre-extraction)
                entities = await ner_service_v2.extract_entities(full_text_corpus)

            span.set_metadata(
                {
                    "inputs": {
                        "corpus_length": len(full_text_corpus),
                        "pre_extracted": bool(pre_entities),
                    },
                    "outputs": {"entities_extracted": len(entities)},
                }
            )

        # Perform Local Coreference Resolution & Entity Linking
        saved_story_entities = []
        tags_added = set()
        async with StageSpan(stage=PipelineStage.ENTITY_LINKING, story_id=str(story.id)) as span:
            grouped_entities = entity_linker.group_entities_locally(entities)

            # Limit to top 15 groups/canonical entities for storage
            for rep, grouped_mentions in list(grouped_entities.items())[:15]:
                etype = grouped_mentions[0]["type"]

                # Resolve/Link to globally unique CanonicalEntity
                try:
                    canonical_ent = await entity_linker.link_entity(
                        name=rep,
                        entity_type=etype,
                        context=full_text_corpus,
                        session=session,
                    )
                    canonical_entity_id = canonical_ent.id
                except Exception as e:
                    logger.error("Failed to link entity %s: %s", rep, e)
                    canonical_ent = None
                    canonical_entity_id = None

                # Add StoryEntity rows for each variant mention in the group
                for mention in grouped_mentions:
                    story_ent = StoryEntity(
                        id=uuid.uuid4(),
                        story_id=story.id,
                        canonical_entity_id=canonical_entity_id,
                        entity_type=mention["type"],
                        entity_value=mention["value"],
                    )
                    story_ent.canonical_entity = canonical_ent
                    session.add(story_ent)
                    saved_story_entities.append(story_ent)

                # Add to tag list
                tag = rep.lower().strip()
                if tag and len(tag) < 30 and tag not in tags_added:
                    tags_added.add(tag)

            # Save Story Tags from entities (limit to 5)
            for tag in list(tags_added)[:5]:
                session.add(StoryTag(id=uuid.uuid4(), story_id=story.id, tag_name=tag))

            span.set_metadata(
                {
                    "inputs": {"entities_to_link": len(entities)},
                    "outputs": {
                        "canonical_entities_linked": len(saved_story_entities),
                        "tags": list(tags_added),
                    },
                }
            )

        # Delegate to StorySynthesisOrchestrator
        from app.services.story_synthesis_service import story_synthesis_orchestrator

        await story_synthesis_orchestrator.synthesize_story(
            session=session,
            story_id=story.id,
            trigger="new_article",
            articles_override=articles,
            story_override=story,
        )

        cat_slug = "world"
        if story.category:
            cat_slug = story.category.slug

        if commit:
            await session.commit()
        else:
            await session.flush()

        # Index in Meilisearch and invalidate caches for this story
        async with StageSpan(stage=PipelineStage.INDEXING, story_id=str(story.id)) as span:
            await self._index_and_invalidate(story, cat_slug, list(tags_added))
            span.set_metadata(
                {
                    "inputs": {
                        "story_id": str(story.id),
                        "category": cat_slug,
                        "tags": list(tags_added),
                    },
                    "outputs": {"indexed": True},
                }
            )

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

    async def should_run_reflection(
        self,
        story: Story,
        articles: list[Article],
        category_slug: str,
        saved_contras: list[StoryContradiction],
        saved_differences: list[StoryDifference],
        saved_coverage: list[StorySourceCoverage],
        session: AsyncSession,
    ) -> bool:
        """Determine if summary reflection should be run based on multi-dimensional signal analysis."""
        # 0. Budget gate — never run expensive reflection if stage budget is exceeded
        from app.services.cost_budget import cost_budget_manager

        budget_exceeded = await cost_budget_manager.is_stage_budget_exceeded(
            str(story.id), "summary_reflection", category_slug
        )
        if budget_exceeded:
            logger.info(
                "Reflection skipped for story %s: stage budget exceeded (category: %s).",
                story.id,
                category_slug,
            )
            return False

        # 1. Admin override
        if getattr(story, "force_reflection", False):
            logger.info("Reflection triggered by admin force override for story %s.", story.id)
            return True

        # 2. High-stakes categories
        if category_slug in ("politics", "business", "health"):
            logger.info(
                "Reflection triggered by high-stakes category '%s' for story %s.",
                category_slug,
                story.id,
            )
            return True

        # 3. High-confidence contradictions
        for contra in saved_contras:
            if contra.confidence and float(contra.confidence) >= 0.8:
                logger.info(
                    "Reflection triggered by high-confidence contradiction (confidence: %s) for story %s.",
                    contra.confidence,
                    story.id,
                )
                return True

        # 4. Source divergence
        divergent_sources = 0
        for diff in saved_differences:
            if diff.unique_information and diff.missing_information:
                divergent_sources += 1
        if divergent_sources >= 2:
            logger.info(
                "Reflection triggered by source divergence (count: %d) for story %s.",
                divergent_sources,
                story.id,
            )
            return True

        # 5. Breaking news or fast-moving stories
        is_breaking = getattr(story, "is_breaking", False)
        hours_since_creation = 999.0
        if story.created_at:
            hours_since_creation = (_now() - story.created_at).total_seconds() / 3600.0

        unique_sources = len({art.source_id for art in articles if art.source_id})
        if is_breaking or (hours_since_creation < 2.0 and unique_sources >= 3):
            logger.info("Reflection triggered by breaking news/fast-moving story %s.", story.id)
            return True

        # 6. Large stories (secondary signal)
        if len(articles) >= 5:
            logger.info(
                "Reflection triggered by large story (articles: %d) for story %s.",
                len(articles),
                story.id,
            )
            return True

        logger.info("Reflection skipped for story %s: no significant signals detected.", story.id)
        return False

    async def update_story_incrementally(
        self,
        story: Story,
        new_article: Article,
        existing_articles: list[Article],
        session: AsyncSession,
    ) -> None:
        """Incrementally update an existing active story when a new article is merged."""
        logger.info(
            "Incrementally updating story %s with new article %s.",
            story.id,
            new_article.id,
        )

        # 1. Load details of the new article
        stmt = select(Source).where(Source.id == new_article.source_id)
        res = await session.execute(stmt)
        new_source = res.scalar_one_or_none()
        new_src_name = new_source.name if new_source else "Unknown Source"

        # Update country location if empty
        if new_source and new_source.country_code and not story.location_country:
            story.location_country = new_source.country_code

        # 2. Incremental Timeline
        event_stmt = select(ArticleEvent).where(ArticleEvent.article_id == new_article.id)
        event_res = await session.execute(event_stmt)
        new_events = list(event_res.scalars().all())

        new_timeline_objects = []
        for evt in new_events:
            t = evt.event_time or evt.created_at or _now()
            if t.tzinfo is not None:
                t = t.astimezone(UTC).replace(tzinfo=None)

            evt_type = (
                (evt.event_type_canonical or evt.event_type or "Event").replace("_", " ").title()
            )

            details = []
            if evt.actors:
                details.append(f"Actors: {', '.join(evt.actors)}")
            if evt.targets:
                details.append(f"Targets: {', '.join(evt.targets)}")
            if evt.location:
                details.append(f"Location: {evt.location}")
            if evt.numbers:
                num_parts = [f"{k}: {v}" for k, v in evt.numbers.items()]
                details.append(f"Data: {', '.join(num_parts)}")

            details_str = f" ({'; '.join(details)})" if details else ""
            desc = f"{evt_type} reported by {new_src_name}{details_str}."

            tl_event = StoryTimelineEvent(
                id=uuid.uuid4(),
                story_id=story.id,
                event_time=t,
                event_time_raw=evt.event_time_raw or t.strftime("%Y-%m-%d %H:%M:%S UTC"),
                description=desc,
                created_at=_now(),
            )
            session.add(tl_event)
            new_timeline_objects.append(tl_event)

        # 3. Incremental Entities & Tags
        pre_extracted_stmt = select(ArticleEntity).where(ArticleEntity.article_id == new_article.id)
        pre_result = await session.execute(pre_extracted_stmt)
        pre_entities = list(pre_result.scalars().all())

        # Construct corpus context (for fallback NER)
        full_text_corpus = f"{(new_article.title or '')}\n{(new_article.description or '')}\n{(new_article.content or '')}\n\n"
        if pre_entities:
            entities = [{"type": e.entity_type, "value": e.entity_value} for e in pre_entities]
        else:
            entities = await ner_service_v2.extract_entities(full_text_corpus)

        grouped_entities = entity_linker.group_entities_locally(entities)

        # Retrieve existing entity names to avoid duplicates
        existing_entities_stmt = select(StoryEntity.entity_value).where(
            StoryEntity.story_id == story.id
        )
        existing_entities_res = await session.execute(existing_entities_stmt)
        existing_entity_values = set(existing_entities_res.scalars().all())

        existing_tags_stmt = select(StoryTag.tag_name).where(StoryTag.story_id == story.id)
        existing_tags_res = await session.execute(existing_tags_stmt)
        existing_tags = set(existing_tags_res.scalars().all())

        for rep, grouped_mentions in list(grouped_entities.items())[:5]:
            etype = grouped_mentions[0]["type"]
            canonical_entity_id = None
            canonical_ent = None

            # Check if this group already exists in the story
            if rep not in existing_entity_values:
                try:
                    canonical_ent = await entity_linker.link_entity(
                        name=rep,
                        entity_type=etype,
                        context=full_text_corpus,
                        session=session,
                    )
                    canonical_entity_id = canonical_ent.id
                except Exception as e:
                    logger.error("Incremental entity link failed for %s: %s", rep, e)

                for mention in grouped_mentions:
                    if mention["value"] not in existing_entity_values:
                        story_ent = StoryEntity(
                            id=uuid.uuid4(),
                            story_id=story.id,
                            canonical_entity_id=canonical_entity_id,
                            entity_type=mention["type"],
                            entity_value=mention["value"],
                        )
                        story_ent.canonical_entity = canonical_ent
                        session.add(story_ent)

                tag = rep.lower().strip()
                if tag and len(tag) < 30 and tag not in existing_tags and len(existing_tags) < 5:
                    session.add(StoryTag(id=uuid.uuid4(), story_id=story.id, tag_name=tag))
                    existing_tags.add(tag)

        # 4. Incremental Contradictions
        try:
            await contradiction_service.detect_and_save_contradictions_incremental(
                story.id, new_article, existing_articles, session
            )
        except Exception as e:
            logger.error("Incremental contradiction detection failed for story %s: %s", story.id, e)

        # 5. Incremental Source Comparison
        all_articles = existing_articles + [new_article]

        all_art_ids = [art.id for art in all_articles]
        art_evt_stmt = select(ArticleEvent).where(ArticleEvent.article_id.in_(all_art_ids))
        art_evt_res = await session.execute(art_evt_stmt)
        all_article_events = list(art_evt_res.scalars().all())

        source_ids_incr = list({art.source_id for art in all_articles if art.source_id is not None})
        if source_ids_incr:
            src_res_incr = await session.execute(
                select(Source).where(Source.id.in_(source_ids_incr))
            )
            source_by_id_incr = {src.id: src for src in src_res_incr.scalars().all()}
        else:
            source_by_id_incr = {}

        sources_list = []
        seen_sources = set()
        for art in all_articles:
            source = source_by_id_incr.get(art.source_id)
            if source and source.id not in seen_sources:
                seen_sources.add(source.id)
                sources_list.append(source)

        article_source_map = {
            art.id: source_by_id_incr[art.source_id].name
            for art in all_articles
            if art.source_id in source_by_id_incr
        }

        try:
            await source_comparison_service.compare_sources_and_save(
                story_id=story.id,
                session=session,
                articles=all_articles,
                article_events=all_article_events,
                article_source_map=article_source_map,
                sources_list=sources_list,
            )
        except Exception as e:
            logger.error("Incremental source comparison failed for story %s: %s", story.id, e)

        # 6. Update Knowledge Graph
        try:
            # Fetch all timeline events for this story
            tl_stmt = select(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id)
            tl_res = await session.execute(tl_stmt)
            saved_timeline_objects = list(tl_res.scalars().all())

            # Fetch all entities for this story
            ent_stmt = select(StoryEntity).where(StoryEntity.story_id == story.id)
            ent_res = await session.execute(ent_stmt)
            saved_story_entities = list(ent_res.scalars().all())

            kg = build_story_knowledge_graph(
                articles=all_articles,
                article_events=all_article_events,
                story_entities=saved_story_entities,
                sources=sources_list,
            )
            kg_dict = kg.to_dict()
            story.knowledge_graph = kg_dict
        except Exception as e:
            logger.error("Incremental knowledge graph update failed for story %s: %s", story.id, e)
            kg_dict = story.knowledge_graph or {}

        # 7. Update Summaries and Category
        try:
            contras_stmt = select(StoryContradiction).where(StoryContradiction.story_id == story.id)
            contras_res = await session.execute(contras_stmt)
            saved_contras = list(contras_res.scalars().all())

            contradictions_list = [
                {
                    "fact_type": c.fact_type,
                    "description": c.description,
                    "confidence": float(c.confidence),
                    "source_attribution": c.source_attribution,
                }
                for c in saved_contras
            ]

            timeline_list = [
                {
                    "date": t.event_time_raw
                    or (t.event_time.isoformat() if t.event_time else "Unknown"),
                    "description": t.description,
                }
                for t in saved_timeline_objects
            ]

            diff_stmt = select(StoryDifference).where(StoryDifference.story_id == story.id)
            diff_res = await session.execute(diff_stmt)
            saved_differences = list(diff_res.scalars().all())

            cov_stmt = select(StorySourceCoverage).where(StorySourceCoverage.story_id == story.id)
            cov_res = await session.execute(cov_stmt)
            saved_coverage = list(cov_res.scalars().all())

            article_source_map = {}
            for art in all_articles:
                stmt = select(Source).where(Source.id == art.source_id)
                res = await session.execute(stmt)
                src = res.scalar_one_or_none()
                article_source_map[art.id] = src.name if src else "Unknown Source"

            source_comparisons_list = []
            for diff in saved_differences:
                cov = next((c for c in saved_coverage if c.source_id == diff.source_id), None)
                focus = cov.focus_area if cov else "General coverage"
                src_name = article_source_map.get(
                    next((art.id for art in all_articles if art.source_id == diff.source_id), None),
                    "Unknown Source",
                )
                source_comparisons_list.append(
                    {
                        "source_name": src_name,
                        "focus_area": focus,
                        "unique_information": diff.unique_information or "",
                        "missing_information": diff.missing_information or "",
                        "contradictions": diff.contradictions or "",
                    }
                )

            summary_res = await ai_service.summarize_story_from_kg(
                kg=kg_dict,
                contradictions=contradictions_list,
                timeline=timeline_list,
                source_comparisons=source_comparisons_list,
            )

            story.headline = summary_res.headline
            story.one_line_summary = summary_res.one_line_summary
            story.short_summary = summary_res.short_summary
            story.detailed_summary = summary_res.detailed_summary
            story.key_facts = (
                [f for f in summary_res.key_facts if f] if summary_res.key_facts else []
            )

            cat_slug = summary_res.category if summary_res.category in CATEGORY_SLUGS else "world"
            cat_id = await self.get_or_create_category(
                cat_slug, cat_slug.replace("-", " ").title(), session
            )
            story.category_id = cat_id

            # Index and invalidate caches
            await self._index_and_invalidate(story, cat_slug, list(existing_tags))
        except Exception as e:
            logger.error("Incremental summary generation failed for story %s: %s", story.id, e)

    async def merge_article_into_existing_story(
        self, article: Article, story_id: uuid.UUID, session: AsyncSession
    ) -> bool:
        """Merge a new article into an existing story cluster."""
        # Acquire transaction-bound advisory lock on story_id
        lock_id = uuid_to_advisory_lock_id(story_id)
        await session.execute(text(f"SELECT pg_advisory_xact_lock({lock_id})"))

        # Check if relation already exists with any story (prevent duplication)
        stmt = select(StoryArticle).where(StoryArticle.article_id == article.id).limit(1)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            logger.info("Article %s is already linked to a story. Aborting merge.", article.id)
            return False

        # Create link
        link = StoryArticle(story_id=story_id, article_id=article.id)
        session.add(link)
        await session.flush()

        # Retrieve the story and all associated articles to update summaries with eagerly loaded relations
        story_stmt = (
            select(Story)
            .options(selectinload(Story.category), selectinload(Story.metrics))
            .where(Story.id == story_id)
        )
        story_res = await session.execute(story_stmt)
        story = story_res.scalar_one_or_none()

        if story:
            # Get all articles in this story
            article_stmt = (
                select(Article).join(StoryArticle).where(StoryArticle.story_id == story_id)
            )
            article_res = await session.execute(article_stmt)
            all_articles = list(article_res.scalars().all())

            logger.info(
                "Merging article %s into story %s. Total articles: %d",
                article.id,
                story_id,
                len(all_articles),
            )

            # Keep the Stage B anchor current — a stale centroid makes the story
            # progressively harder to match as it grows.
            await self.refresh_story_centroid(
                story, session, article_ids=[a.id for a in all_articles]
            )
            newsiq_story_article_count.observe(len(all_articles))
            # Delegate to StorySynthesisOrchestrator
            from app.services.story_synthesis_service import story_synthesis_orchestrator

            await story_synthesis_orchestrator.synthesize_story(
                session=session,
                story_id=story_id,
                trigger="new_article",
                articles_override=all_articles,
                story_override=story,
            )
            await self.compute_trending_score(story, session)

            from app.services.story_evolution_service import record_story_evolution

            await record_story_evolution(
                db=session,
                story_id=story_id,
                event_type="article_merged",
                article_id=article.id,
                before_state={"article_count": len(all_articles) - 1},
                after_state={"article_count": len(all_articles)},
                notes=f"Article {article.id} incrementally merged into story.",
            )

        return True

    async def refresh_story_centroid(
        self, story: Story, session: AsyncSession, article_ids: list[uuid.UUID] | None = None
    ) -> list[float] | None:
        """Recompute story.story_embedding as the unit-norm mean of member vectors.

        This is the anchor Stage B compares incoming articles against. Vectors
        are read back from Qdrant, which normalizes on write for cosine
        distance, so the inputs are unit vectors and the mean is meaningful.
        The result is re-normalized because the mean of unit vectors is not.

        Returns the new centroid, or None if no member vectors were available
        (in which case the stored value is left untouched rather than being
        clobbered with a degenerate vector).
        """
        if article_ids is None:
            res = await session.execute(
                select(StoryArticle.article_id).where(StoryArticle.story_id == story.id)
            )
            article_ids = list(res.scalars().all())

        if not article_ids:
            return None

        try:
            vectors_by_id = await vector_service.retrieve_vectors([str(a) for a in article_ids])
        except Exception as e:
            logger.warning("Failed to fetch vectors for story %s centroid: %s", story.id, e)
            return None

        vectors = [v for v in vectors_by_id.values() if v]
        if not vectors:
            logger.warning(
                "No vectors found in Qdrant for story %s (%d articles) — centroid not updated.",
                story.id,
                len(article_ids),
            )
            return None

        matrix = np.asarray(vectors, dtype=np.float64)
        centroid = matrix.mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm == 0.0:
            logger.warning("Degenerate (zero) centroid for story %s — not updated.", story.id)
            return None

        unit_centroid: list[float] = (centroid / norm).tolist()
        story.story_embedding = unit_centroid
        logger.debug(
            "Refreshed centroid for story %s from %d/%d member vectors.",
            story.id,
            len(vectors),
            len(article_ids),
        )
        return unit_centroid

    def _compute_event_similarity_direct(self, evt1: ArticleEvent, evt2: ArticleEvent) -> float:
        """Directly compare two ArticleEvent objects and compute similarity score."""
        from app.services.event_taxonomy import get_parent_type

        # 1. Event Type Similarity (15%)
        type_sim = 0.0
        if evt1.event_type_canonical and evt2.event_type_canonical:
            if evt1.event_type_canonical == evt2.event_type_canonical:
                type_sim = 1.0
            elif get_parent_type(evt1.event_type_canonical) == get_parent_type(
                evt2.event_type_canonical
            ):
                type_sim = 0.5

        # 2. Actor Similarity (25% components weight)
        a1 = set(evt1.actors or [])
        a2 = set(evt2.actors or [])
        if a1 and a2:
            actor_sim = len(a1.intersection(a2)) / len(a1.union(a2))
        else:
            actor_sim = 0.0

        # 3. Target Similarity (20% components weight)
        t1 = set(evt1.targets or [])
        t2 = set(evt2.targets or [])
        if t1 and t2:
            target_sim = len(t1.intersection(t2)) / len(t1.union(t2))
        else:
            target_sim = 0.0

        # 4. Location Similarity (20%)
        loc_sim = 0.5
        if evt1.location and evt2.location:
            l1 = evt1.location.strip().lower()
            l2 = evt2.location.strip().lower()
            if l1 == l2:
                loc_sim = 1.0
            elif l1 in l2 or l2 in l1:
                loc_sim = 0.8
            else:
                loc_sim = 0.0

        # 5. Time Similarity (10%)
        if not evt1.event_time or not evt2.event_time:
            time_sim = 0.5
        elif evt1.event_time.date() == evt2.event_time.date():
            time_sim = 1.0
        else:
            time_sim = 0.0

        return (
            0.25 * actor_sim
            + 0.20 * target_sim
            + 0.20 * loc_sim
            + 0.15 * type_sim
            + 0.10 * time_sim
            # Entity overlap (10%) is added externally when available
        )

    async def _verify_merge_with_agents(
        self,
        article_a: Article,
        event_a: ArticleEvent,
        article_b: Article,
        event_b: ArticleEvent,
        similarity_score: float,
        category_slug: str = "",
        kg_nodes: list = None,
        metadata: dict = None,
    ) -> bool:
        """Call Agno agents to verify if two articles describe the same event, using Judge Agent if needed."""
        import asyncio

        from app.agents.cluster_verification_agent import verify_cluster_decision
        from app.core.config import settings

        if metadata is None:
            metadata = {}

        # Report the model that is actually used, not a hardcoded guess. These
        # strings are persisted into clustering traces, and the previous literals
        # ("gemini-2.5-flash", "gpt-4o") never matched reality — the agents
        # resolve their model from settings.SUMMARIZATION_MODEL via
        # get_default_model(), so every stored trace named a model that had not
        # run. An audit trail that lies is worse than no audit trail.
        _agent_model = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"

        metadata["triggered"] = True
        metadata["gemini"] = {
            "decision": None,
            "latency_ms": 0.0,
            "provider": "gemini",
            "model": _agent_model,
        }
        metadata["openai"] = {
            "decision": None,
            "latency_ms": 0.0,
            "provider": "openai",
            "model": _OPENAI_VERIFICATION_MODEL,
        }
        metadata["judge"] = {
            "decision": None,
            "latency_ms": 0.0,
            # judge_agent uses get_default_model() like the others — it is not
            # an OpenAI agent, despite what the old hardcoded metadata claimed.
            "provider": "gateway",
            "model": _agent_model,
        }
        metadata["fallback"] = {"reason": None, "used": None}

        art_a_evt_dict = {
            "type": event_a.event_type_canonical,
            "actors": event_a.actors,
            "targets": event_a.targets,
            "location": event_a.location,
            "time": str(event_a.event_time) if event_a.event_time else "",
        }
        art_b_evt_dict = {
            "type": event_b.event_type_canonical,
            "actors": event_b.actors,
            "targets": event_b.targets,
            "location": event_b.location,
            "time": str(event_b.event_time) if event_b.event_time else "",
        }

        text_to_check = ((article_a.title or "") + " " + (article_b.title or "")).lower()
        high_stakes = category_slug in ("world", "politics", "business") or any(
            w in text_to_check
            for w in ("war", "election", "finance", "military", "police", "arrest", "attack")
        )

        gemini_ver = None
        start_g = _now()
        try:
            gemini_ver = await verify_cluster_decision(
                article_a_title=article_a.title or "",
                article_a_event=art_a_evt_dict,
                article_b_title=article_b.title or "",
                article_b_event=art_b_evt_dict,
                similarity_score=similarity_score,
                kg_nodes=kg_nodes,
            )
            metadata["gemini"]["decision"] = "PASS" if gemini_ver.same_event else "FAIL"
            metadata["gemini"]["confidence"] = getattr(gemini_ver, "confidence", 1.0)
        except Exception as e:
            logger.error("Gemini cluster verification agent failed: %s", e)
            metadata["gemini"]["decision"] = "ERROR"
            metadata["gemini"]["error"] = str(e)
            gemini_ver = None
        metadata["gemini"]["latency_ms"] = (_now() - start_g).total_seconds() * 1000.0

        if high_stakes and settings.OPENAI_API_KEY and gemini_ver is not None:
            try:
                from agno.agent import Agent
                from agno.models.openai import OpenAIChat

                from app.agents.base_agent import run_agent_with_observability
                from app.agents.cluster_verification_agent import cluster_verification_agent
                from app.agents.judge_agent import resolve_disagreement

                openai_agent = Agent(
                    name="OpenAI Verification Agent",
                    model=OpenAIChat(id=_OPENAI_VERIFICATION_MODEL),
                    instructions=cluster_verification_agent.instructions,
                    output_schema=cluster_verification_agent.output_schema,
                )

                prompt = f"""
                Compare the following two articles and decide if they describe the exact same event:

                Article A:
                - Title: {article_a.title}
                - Extracted Event: {art_a_evt_dict}

                Article B:
                - Title: {article_b.title}
                - Extracted Event: {art_b_evt_dict}

                Determined Similarity Score: {similarity_score:.4f}
                Knowledge Graph Context: {kg_nodes or "None"}

                Determine if they represent the same event.
                """

                # Run OpenAI agent with configurable timeout
                start_o = _now()
                openai_ver = None
                try:
                    run_output_oa = await asyncio.wait_for(
                        run_agent_with_observability(
                            agent=openai_agent, prompt=prompt, stage="cluster_verification"
                        ),
                        timeout=settings.REFLECTION_AGENT_TIMEOUT_SECONDS,
                    )
                    openai_ver = run_output_oa.content
                    metadata["openai"]["decision"] = "PASS" if openai_ver.same_event else "FAIL"
                    metadata["openai"]["confidence"] = getattr(openai_ver, "confidence", 1.0)
                except TimeoutError:
                    logger.warning("OpenAI Verification Agent timed out.")
                    from app.core.metrics import newsiq_reflection_timeout_total

                    newsiq_reflection_timeout_total.labels(agent_type="openai").inc()
                    metadata["openai"]["decision"] = "TIMEOUT"
                except Exception as ex:
                    logger.warning("OpenAI Verification Agent failed: %s", ex)
                    metadata["openai"]["decision"] = "ERROR"
                    metadata["openai"]["error"] = str(ex)
                metadata["openai"]["latency_ms"] = (_now() - start_o).total_seconds() * 1000.0

                if openai_ver is not None:
                    if gemini_ver.same_event != openai_ver.same_event:
                        start_j = _now()
                        try:
                            judgment = await asyncio.wait_for(
                                resolve_disagreement(
                                    task_description="Verify if two articles describe the same event",
                                    provider_a_name="gemini",
                                    provider_a_output=gemini_ver.model_dump(),
                                    provider_b_name="openai",
                                    provider_b_output=openai_ver.model_dump(),
                                    context=f"Article A: {article_a.title}\nArticle B: {article_b.title}",
                                ),
                                timeout=settings.REFLECTION_AGENT_TIMEOUT_SECONDS,
                            )
                            metadata["judge"]["decision"] = (
                                "PASS" if judgment.final_decision else "FAIL"
                            )
                            metadata["judge"]["chosen_provider"] = judgment.chosen_provider
                            metadata["judge"]["explanation"] = judgment.explanation
                            metadata["judge"]["latency_ms"] = (
                                _now() - start_j
                            ).total_seconds() * 1000.0
                            return judgment.final_decision
                        except TimeoutError:
                            logger.warning("Judge Agent arbitration timed out.")
                            from app.core.metrics import (
                                newsiq_reflection_cache_reused_total,
                                newsiq_reflection_fallback_total,
                                newsiq_reflection_timeout_total,
                            )

                            newsiq_reflection_timeout_total.labels(agent_type="judge").inc()
                            newsiq_reflection_fallback_total.labels(
                                fallback_type="cached_gemini"
                            ).inc()
                            newsiq_reflection_cache_reused_total.inc()
                            metadata["judge"]["decision"] = "TIMEOUT"
                            metadata["fallback"]["reason"] = "judge_timeout"
                            metadata["fallback"]["used"] = "cached_gemini"
                            return gemini_ver.same_event
                        except Exception as j_err:
                            logger.warning("Judge Agent arbitration failed: %s", j_err)
                            from app.core.metrics import (
                                newsiq_reflection_cache_reused_total,
                                newsiq_reflection_fallback_total,
                            )

                            newsiq_reflection_fallback_total.labels(
                                fallback_type="cached_gemini"
                            ).inc()
                            newsiq_reflection_cache_reused_total.inc()
                            metadata["judge"]["decision"] = "ERROR"
                            metadata["judge"]["error"] = str(j_err)
                            metadata["fallback"]["reason"] = "judge_error"
                            metadata["fallback"]["used"] = "cached_gemini"
                            return gemini_ver.same_event
                    else:
                        return gemini_ver.same_event
                else:
                    # OpenAI failed/timed out, reuse cached Gemini decision
                    from app.core.metrics import (
                        newsiq_reflection_cache_reused_total,
                        newsiq_reflection_fallback_total,
                    )

                    newsiq_reflection_fallback_total.labels(fallback_type="cached_gemini").inc()
                    newsiq_reflection_cache_reused_total.inc()
                    metadata["fallback"]["reason"] = "openai_unavailable"
                    metadata["fallback"]["used"] = "cached_gemini"
                    return gemini_ver.same_event
            except Exception as e:
                logger.error("Dual-agent verification setup failed: %s", e)

        # Primary Gemini-only path / fallback if cached Gemini succeeded
        if gemini_ver is not None:
            if high_stakes and settings.OPENAI_API_KEY:
                from app.core.metrics import (
                    newsiq_reflection_cache_reused_total,
                    newsiq_reflection_fallback_total,
                )

                newsiq_reflection_fallback_total.labels(fallback_type="cached_gemini").inc()
                newsiq_reflection_cache_reused_total.inc()
                metadata["fallback"]["reason"] = "dual_agent_setup_error"
                metadata["fallback"]["used"] = "cached_gemini"
            return gemini_ver.same_event

        # Deterministic fallback threshold (Gemini failed entirely)
        from app.core.metrics import newsiq_reflection_fallback_total

        newsiq_reflection_fallback_total.labels(fallback_type="deterministic_threshold").inc()
        metadata["fallback"]["reason"] = "gemini_unavailable"
        metadata["fallback"]["used"] = "deterministic_threshold"

        should_merge_det = similarity_score >= DETERMINISTIC_FALLBACK_THRESHOLD
        return should_merge_det

    async def add_article_to_existing_story_if_similar(
        self, article_id: uuid.UUID, session: AsyncSession
    ) -> bool:
        """Incremental similarity check. Merges article into an existing story if highly similar."""
        # Check if already linked to any story (prevent duplication)
        chk_stmt = select(StoryArticle).where(StoryArticle.article_id == article_id).limit(1)
        chk_res = await session.execute(chk_stmt)
        if chk_res.scalar_one_or_none():
            logger.info("Article %s is already linked to a story.", article_id)
            return False

        stmt = select(Article).where(Article.id == article_id)
        res = await session.execute(stmt)
        article = res.scalar_one_or_none()
        if not article or article.embedding_status != "completed":
            return False

        # Candidate Retrieval: Hybrid filtering
        # 1. Base time window (e.g. 72 hours)
        from datetime import UTC, datetime, timedelta

        time_window = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=72)

        # 2. Extract article entities for indexing
        from app.services.event_validation_service import EventValidationService

        extracted_ents = EventValidationService()._extract_entities(article.title)

        # 3. Build query
        from sqlalchemy import exists, or_, text

        recent_stories_stmt = (
            select(Story)
            .options(selectinload(Story.category), selectinload(Story.entities))
            .where(
                # "emerging" MUST be included. Stories are created in that state,
                # and lifecycle_rules only promotes emerging -> developing once a
                # story has >= 3 articles. Excluding it meant a new story could
                # never be a merge candidate, so it could never reach 3 articles,
                # so it could never leave "emerging" — a closed loop. In
                # production this left 476/476 stories stuck at "emerging" with
                # 462 of them holding exactly one article.
                Story.lifecycle_state.in_(
                    [
                        StoryLifecycleState.EMERGING,
                        StoryLifecycleState.DEVELOPING,
                        StoryLifecycleState.MONITORING,
                        StoryLifecycleState.STABLE,
                    ]
                ),
                Story.updated_at >= time_window,
                ~Story.id.in_(
                    select(StoryArticle.story_id).where(StoryArticle.article_id == article.id)
                ),
            )
        )

        # Boost by entity overlap (if extracted entities exist)
        if extracted_ents:
            has_matching_entity = exists().where(
                StoryEntity.story_id == Story.id,
                func.lower(StoryEntity.entity_value).in_([e.lower() for e in extracted_ents]),
            )
            has_no_entities = ~exists().where(StoryEntity.story_id == Story.id)
            recent_stories_stmt = recent_stories_stmt.where(
                or_(has_matching_entity, has_no_entities)
            )

        recent_stories_stmt = recent_stories_stmt.order_by(Story.updated_at.desc()).limit(20)

        recent_stories_res = await session.execute(recent_stories_stmt)
        candidates = recent_stories_res.scalars().all()

        newsiq_clustering_candidates.observe(len(candidates))

        if not candidates:
            logger.info(
                "Article %s: no candidate stories in the last 72h "
                "(lifecycle in emerging/developing/monitoring/stable).",
                article_id,
            )
            return False

        stage_a_passed_candidates = []
        for story in candidates:
            # Build Story Anchor
            primary_entities = (
                {e.entity_value.lower() for e in story.entities} if story.entities else set()
            )
            # Simple fallback for locations from primary entities
            top_locations = (
                {
                    e.entity_value.lower()
                    for e in story.entities
                    if getattr(e, "entity_type", "") in ("GPE", "LOC")
                }
                if story.entities
                else set()
            )

            # Stage B compares this set against the article's canonical entity IDs,
            # so it must be built from the SAME identifier space. It previously read
            # knowledge_graph["nodes"], which is a list[dict] — `set()` over it raises
            # TypeError: unhashable type: 'dict' for any story that has a graph, and
            # for stories without one it silently produced an empty set that could
            # never intersect anything. StoryEntity.canonical_entity_id is the
            # identifier the article side actually uses.
            story_canonical_entity_ids = (
                {
                    str(e.canonical_entity_id)
                    for e in story.entities
                    if e.canonical_entity_id is not None
                }
                if story.entities
                else set()
            )

            anchor = StoryAnchor(
                story_id=str(story.id),
                headline=story.headline or "",
                first_seen_at=story.first_seen_at or datetime.now(UTC).replace(tzinfo=None),
                last_updated_at=story.updated_at or datetime.now(UTC).replace(tzinfo=None),
                primary_entities=primary_entities,
                top_locations=top_locations,
                category=story.category.slug if story.category else None,
                event_type=getattr(story, "event_type", None),
                centroid_vector=getattr(story, "story_embedding", None),
                entity_graph_ids=story_canonical_entity_ids,
            )

            start_time_a = _now()
            decision = event_validation_service.validate_stage_a(article, anchor)
            latency_a = (_now() - start_time_a).total_seconds() * 1000.0

            # Expose Stage A Prom Counter
            from app.core.metrics import newsiq_stage_a_pass_total

            newsiq_stage_a_pass_total.labels(outcome=decision.outcome.value).inc()

            if decision.outcome in (ValidationOutcome.PASS, ValidationOutcome.MAYBE):
                stage_a_passed_candidates.append((story, anchor, decision, start_time_a, latency_a))
                newsiq_stage_a_validation_total.labels(outcome=decision.outcome.value).inc()
            else:
                newsiq_stage_a_validation_total.labels(outcome="rejected").inc()
                logger.debug(
                    "Article %s rejected for story %s at Stage A: %s",
                    article_id,
                    story.id,
                    decision.reason,
                )
                # Save single trace entry for Stage A rejection
                import json

                from app.models import PipelineTraceModel

                trace_data = {
                    "stage_a": {
                        "score": round(decision.score, 4),
                        "decision": decision.outcome.value,
                        "reason": decision.reason,
                        "latency_ms": round(latency_a, 2),
                        "details": decision.details,
                    },
                    "stage_b": {"triggered": False},
                    "reflection": {"triggered": False},
                    "overall_decision": "FAIL",
                }
                trace = PipelineTraceModel(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    article_id=article.id,
                    stage="article_clustering",
                    started_at=start_time_a,
                    completed_at=_now(),
                    latency_ms=latency_a,
                    decision="FAIL",
                    reason=json.dumps(trace_data),
                )
                session.add(trace)

        if not stage_a_passed_candidates:
            logger.info(
                "Article %s failed Stage A validation for all top candidates. Routing to Discovery Queue.",
                article_id,
            )
            return False

        # Fetch vector from Qdrant for Stage B
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

        # Fetch the article's event/entities for multi-signal verification
        event_stmt = select(ArticleEvent).where(ArticleEvent.article_id == article_id).limit(1)
        event_res = await session.execute(event_stmt)
        article_event = event_res.scalar_one_or_none()

        # Canonical entity IDs for Stage B's entity-overlap test.
        # These were previously taken from event.actors/targets, which are raw
        # display names ("Narendra Modi") — type-disjoint from the story side, so
        # the intersection was always empty and the entity signal never fired.
        art_ent_stmt = select(ArticleEntity.canonical_entity_id).where(
            ArticleEntity.article_id == article_id,
            ArticleEntity.canonical_entity_id.isnot(None),
        )
        art_ent_res = await session.execute(art_ent_stmt)
        article_canonical_entity_ids = {str(row[0]) for row in art_ent_res.all()}

        # Sort stage_a_passed_candidates by Stage A score descending and take Top 3
        stage_a_passed_candidates.sort(key=lambda x: x[2].score, reverse=True)
        top_3_candidates = stage_a_passed_candidates[:3]
        skipped_candidates = stage_a_passed_candidates[3:]

        # Record traces for skipped candidates (passed Stage A but not in Top 3)
        import json

        from app.models import PipelineTraceModel

        for story, anchor, stage_a_decision, start_time_a, latency_a in skipped_candidates:
            trace_data = {
                "stage_a": {
                    "score": round(stage_a_decision.score, 4),
                    "decision": stage_a_decision.outcome.value,
                    "reason": stage_a_decision.reason,
                    "latency_ms": round(latency_a, 2),
                    "details": stage_a_decision.details,
                },
                "stage_b": {
                    "triggered": False,
                    "reason": "Skipped: Story did not make Top 3 Stage A cut",
                },
                "reflection": {"triggered": False},
                "overall_decision": "FAIL",
            }
            trace = PipelineTraceModel(
                id=uuid.uuid4(),
                story_id=story.id,
                article_id=article.id,
                stage="article_clustering",
                started_at=start_time_a,
                completed_at=_now(),
                latency_ms=latency_a,
                decision="FAIL",
                reason=json.dumps(trace_data),
            )
            session.add(trace)

        for story, anchor, stage_a_decision, start_time_a, latency_a in top_3_candidates:
            start_time_b = _now()
            decision_b = event_validation_service.validate_stage_b(
                article, anchor, cast(list[float], vector), article_canonical_entity_ids
            )
            latency_b = (_now() - start_time_b).total_seconds() * 1000.0

            # Expose Stage B Prom Counter
            from app.core.metrics import newsiq_stage_b_pass_total

            newsiq_stage_b_pass_total.labels(outcome=decision_b.outcome.value).inc()
            # decision_b.score is the cosine. Pinned at exactly 0.0 means the
            # story anchor has no centroid — the shape BUG-02 had in production.
            newsiq_clustering_similarity.observe(decision_b.score)

            story_id = story.id
            if decision_b.outcome == ValidationOutcome.PASS:
                # Merge directly
                logger.info(
                    "Article %s passed Stage B for story %s. Merging.", article_id, story_id
                )
                trace_data = {
                    "stage_a": {
                        "score": round(stage_a_decision.score, 4),
                        "decision": stage_a_decision.outcome.value,
                        "reason": stage_a_decision.reason,
                        "latency_ms": round(latency_a, 2),
                        "details": stage_a_decision.details,
                    },
                    "stage_b": {
                        "triggered": True,
                        "cosine": round(getattr(decision_b, "score", 0.0), 4),
                        "entities": decision_b.details.get("shared_canonical_entities", 0),
                        "decision": decision_b.outcome.value,
                        "reason": decision_b.reason,
                        "latency_ms": round(latency_b, 2),
                        "details": decision_b.details,
                    },
                    "reflection": {"triggered": False},
                    "overall_decision": "PASS",
                }
                trace = PipelineTraceModel(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    article_id=article.id,
                    stage="article_clustering",
                    started_at=start_time_a,
                    completed_at=_now(),
                    latency_ms=latency_a + latency_b,
                    decision="PASS",
                    reason=json.dumps(trace_data),
                )
                session.add(trace)

                return await self.merge_article_into_existing_story(article, story_id, session)

            elif decision_b.outcome == ValidationOutcome.MAYBE:
                if decision_b.score < REFLECTION_THRESHOLD:
                    logger.info(
                        "Article %s scored MAYBE (%.2f) but below reflection threshold (%.2f). Skipping reflection.",
                        article_id,
                        decision_b.score,
                        REFLECTION_THRESHOLD,
                    )
                    trace_data = {
                        "stage_a": {
                            "score": round(stage_a_decision.score, 4),
                            "decision": stage_a_decision.outcome.value,
                            "reason": stage_a_decision.reason,
                            "latency_ms": round(latency_a, 2),
                            "details": stage_a_decision.details,
                        },
                        "stage_b": {
                            "triggered": True,
                            "cosine": round(getattr(decision_b, "score", 0.0), 4),
                            "entities": decision_b.details.get("shared_canonical_entities", 0),
                            "decision": decision_b.outcome.value,
                            "reason": f"MAYBE (below reflection threshold {REFLECTION_THRESHOLD})",
                            "latency_ms": round(latency_b, 2),
                            "details": decision_b.details,
                        },
                        "reflection": {"triggered": False},
                        "overall_decision": "FAIL",
                    }
                    trace = PipelineTraceModel(
                        id=uuid.uuid4(),
                        story_id=story.id,
                        article_id=article.id,
                        stage="article_clustering",
                        started_at=start_time_a,
                        completed_at=_now(),
                        latency_ms=latency_a + latency_b,
                        decision="FAIL",
                        reason=json.dumps(trace_data),
                    )
                    session.add(trace)
                    continue

                # Send to LLM Reflection
                logger.info(
                    "Article %s scored MAYBE (%.2f) for story %s. Sending to reflection.",
                    article_id,
                    decision_b.score,
                    story_id,
                )
                from app.core.metrics import newsiq_reflection_triggered_total

                newsiq_reflection_triggered_total.labels(reason_type="borderline_similarity").inc()
                newsiq_reflection_requests_total.labels(outcome="requested").inc()

                lock_id = uuid_to_advisory_lock_id(story_id)
                await session.execute(text(f"SELECT pg_advisory_xact_lock({lock_id})"))

                stmt_first_art = (
                    select(Article)
                    .join(StoryArticle)
                    .where(StoryArticle.story_id == story.id)
                    .limit(1)
                )
                res_first_art = await session.execute(stmt_first_art)
                first_art = res_first_art.scalar_one_or_none()

                first_evt = None
                if first_art:
                    stmt_evt = (
                        select(ArticleEvent).where(ArticleEvent.article_id == first_art.id).limit(1)
                    )
                    res_evt = await session.execute(stmt_evt)
                    first_evt = res_evt.scalar_one_or_none()

                if first_art and first_evt and article_event:
                    category_slug = story.category.slug if story.category else ""
                    start_time_ref = _now()
                    reflection_metadata: dict[str, Any] = {}

                    should_merge = await self._verify_merge_with_agents(
                        article_a=article,
                        event_a=article_event,
                        article_b=first_art,
                        event_b=first_evt,
                        similarity_score=decision_b.score,
                        category_slug=category_slug,
                        kg_nodes=story.knowledge_graph.get("nodes", [])
                        if story.knowledge_graph
                        else [],
                        metadata=reflection_metadata,
                    )
                    latency_ref = (_now() - start_time_ref).total_seconds() * 1000.0

                    trace_data = {
                        "stage_a": {
                            "score": round(stage_a_decision.score, 4),
                            "decision": stage_a_decision.outcome.value,
                            "reason": stage_a_decision.reason,
                            "latency_ms": round(latency_a, 2),
                            "details": stage_a_decision.details,
                        },
                        "stage_b": {
                            "triggered": True,
                            "cosine": round(getattr(decision_b, "score", 0.0), 4),
                            "entities": decision_b.details.get("shared_canonical_entities", 0),
                            "decision": decision_b.outcome.value,
                            "reason": decision_b.reason,
                            "latency_ms": round(latency_b, 2),
                            "details": decision_b.details,
                        },
                        "reflection": {
                            "triggered": True,
                            "trigger_reason": {
                                "cosine": round(getattr(decision_b, "score", 0.0), 4),
                                "entities": decision_b.details.get("shared_canonical_entities", 0),
                            },
                            "latency_ms": round(latency_ref, 2),
                            "details": reflection_metadata,
                        },
                        "overall_decision": "PASS" if should_merge else "FAIL",
                    }
                    trace = PipelineTraceModel(
                        id=uuid.uuid4(),
                        story_id=story.id,
                        article_id=article.id,
                        stage="article_clustering",
                        started_at=start_time_a,
                        completed_at=_now(),
                        latency_ms=latency_a + latency_b + latency_ref,
                        decision="PASS" if should_merge else "FAIL",
                        reason=json.dumps(trace_data),
                    )
                    session.add(trace)

                    if should_merge:
                        logger.info(
                            "Reflection passed for article %s into story %s", article_id, story_id
                        )
                        return await self.merge_article_into_existing_story(
                            article, story_id, session
                        )
                    else:
                        logger.info(
                            "Reflection rejected merge of article %s into story %s",
                            article_id,
                            story_id,
                        )
                else:
                    logger.warning("Missing event data for reflection on story %s", story_id)
                    trace_data = {
                        "stage_a": {
                            "score": round(stage_a_decision.score, 4),
                            "decision": stage_a_decision.outcome.value,
                            "reason": stage_a_decision.reason,
                            "latency_ms": round(latency_a, 2),
                            "details": stage_a_decision.details,
                        },
                        "stage_b": {
                            "triggered": True,
                            "cosine": round(getattr(decision_b, "score", 0.0), 4),
                            "entities": decision_b.details.get("shared_canonical_entities", 0),
                            "decision": decision_b.outcome.value,
                            "reason": decision_b.reason,
                            "latency_ms": round(latency_b, 2),
                            "details": decision_b.details,
                        },
                        "reflection": {
                            "triggered": True,
                            "error": "Missing event data for reflection",
                        },
                        "overall_decision": "FAIL",
                    }
                    trace = PipelineTraceModel(
                        id=uuid.uuid4(),
                        story_id=story.id,
                        article_id=article.id,
                        stage="article_clustering",
                        started_at=start_time_a,
                        completed_at=_now(),
                        latency_ms=latency_a + latency_b,
                        decision="FAIL",
                        reason=json.dumps(trace_data),
                    )
                    session.add(trace)

            else:
                logger.info(
                    "Article %s rejected for story %s at Stage B: %s",
                    article_id,
                    story.id,
                    decision_b.reason,
                )
                trace_data = {
                    "stage_a": {
                        "score": round(stage_a_decision.score, 4),
                        "decision": stage_a_decision.outcome.value,
                        "reason": stage_a_decision.reason,
                        "latency_ms": round(latency_a, 2),
                        "details": stage_a_decision.details,
                    },
                    "stage_b": {
                        "triggered": True,
                        "cosine": round(getattr(decision_b, "score", 0.0), 4),
                        "entities": decision_b.details.get("shared_canonical_entities", 0),
                        "decision": decision_b.outcome.value,
                        "reason": decision_b.reason,
                        "latency_ms": round(latency_b, 2),
                        "details": decision_b.details,
                    },
                    "reflection": {"triggered": False},
                    "overall_decision": "FAIL",
                }
                trace = PipelineTraceModel(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    article_id=article.id,
                    stage="article_clustering",
                    started_at=start_time_a,
                    completed_at=_now(),
                    latency_ms=latency_a + latency_b,
                    decision="FAIL",
                    reason=json.dumps(trace_data),
                )
                session.add(trace)

        return False

    async def run_batch_clustering(
        self, session: AsyncSession, max_age_hours: int | None = None
    ) -> int:
        """Run HDBSCAN clustering on unclustered articles.

        Concurrency is guarded by a Postgres advisory lock held on a DEDICATED
        connection. It cannot live on `session`: pg_advisory_lock is
        session-scoped (per database connection), and AsyncSession returns its
        connection to the pool on every commit — so the lock would be stranded
        on a pooled connection while the matching pg_advisory_unlock ran on a
        different one and silently returned false, permanently blocking every
        later run. Holding it on a connection we own for the whole call, and
        closing that connection in a context manager, makes release
        unconditional: Postgres drops all advisory locks when the owning
        connection closes, even if the process dies.

        pg_try_advisory_lock (non-blocking) is used so a concurrent run skips
        rather than piling up waiters on a 10-minute Celery task.
        """
        GLOBAL_CLUSTERING_LOCK_ID = 888888888

        async with engine.connect() as lock_conn:
            acquired = await lock_conn.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"),
                {"lock_id": GLOBAL_CLUSTERING_LOCK_ID},
            )
            if not acquired.scalar():
                logger.info(
                    "run_batch_clustering: advisory lock %d already held — skipping this run.",
                    GLOBAL_CLUSTERING_LOCK_ID,
                )
                return 0

            # End the implicit transaction that executing the lock query opened.
            # Session-level advisory locks survive COMMIT — only disconnect or an
            # explicit unlock releases them — but an OPEN transaction idling for
            # the duration of clustering (minutes of LLM calls) gets the backend
            # killed by idle_in_transaction_session_timeout (30s in production).
            # That kill both crashed the run with "connection is closed" AND
            # silently released the lock mid-run, letting a concurrent run start.
            await lock_conn.commit()

            try:
                return await self._run_batch_clustering_locked(session, max_age_hours)
            finally:
                try:
                    await session.rollback()
                except Exception as e:
                    logger.warning("Failed to rollback session in finally block: %s", e)
                try:
                    await lock_conn.execute(
                        text("SELECT pg_advisory_unlock(:lock_id)"),
                        {"lock_id": GLOBAL_CLUSTERING_LOCK_ID},
                    )
                except Exception as e:
                    logger.warning("Failed to release pg_advisory_unlock: %s", e)

    async def _run_batch_clustering_locked(
        self, session: AsyncSession, max_age_hours: int | None = None
    ) -> int:
        """Internal method running batch clustering under global lock."""
        # Ensure all canonical categories exist
        await self._ensure_all_categories(session)

        # ── Eligible-article selection ────────────────────────────────────────
        # Select fully-processed articles that are not yet part of any story.
        #
        # This previously read `articles JOIN discovery_queue WHERE state =
        # 'discovery_ready'`. Nothing has written to discovery_queue since its
        # producer (discovery_manager.py) was deleted in commit 44ffae4, so the
        # join matched zero rows on every run and batch clustering — the only
        # automated story creator — returned 0 forever. In production the table
        # held 0 rows against 15 941 articles.
        #
        # Reading the articles table directly removes the dependency on that
        # orphaned queue entirely. NOT EXISTS against story_articles is the
        # authoritative "unclustered" test and needs no separate state machine
        # to be kept in sync.
        _BATCH_LIMIT = 200

        from datetime import timedelta

        from app.core.config import settings

        # Shared with embedding and event extraction so the three stages agree
        # on eligibility. max_age_hours overrides it for one-off backfills of
        # articles that were processed before the bound existed.
        age_hours = (
            max_age_hours if max_age_hours is not None else settings.PIPELINE_MAX_ARTICLE_AGE_HOURS
        )
        age_cutoff = _now() - timedelta(hours=age_hours)

        stmt = (
            select(Article)
            .where(
                Article.embedding_status == "completed",
                Article.event_extraction_status == "completed",
                Article.created_at >= age_cutoff,
                ~select(StoryArticle.article_id)
                .where(StoryArticle.article_id == Article.id)
                .exists(),
            )
            .order_by(Article.published_at.desc().nulls_last())
            .limit(_BATCH_LIMIT)
        )
        res = await session.execute(stmt)
        unclustered_articles = list(res.scalars().all())

        # Record before the early return, so "starved" is distinguishable from
        # "never ran" — the ambiguity that hid BUG-01 for 41 days.
        newsiq_clustering_eligible_articles.set(len(unclustered_articles))

        if not unclustered_articles:
            logger.info(
                "Batch clustering: no eligible articles "
                "(embedded + event-extracted, unclustered, newer than %dh).",
                age_hours,
            )
            return 0

        logger.info(
            "Running batch clustering on %d unclustered articles.", len(unclustered_articles)
        )

        verified_clusters: list[list[Article]] = []

        if len(unclustered_articles) == 1:
            verified_clusters.append([unclustered_articles[0]])
        else:
            # Retrieve vectors for all these articles
            article_ids = [str(a.id) for a in unclustered_articles]
            vectors = []
            valid_articles = []

            try:
                points = await vector_service.client.retrieve(
                    collection_name="articles", ids=article_ids, with_vectors=True
                )
                points_dict = {uuid.UUID(str(p.id)): p.vector for p in points if p.vector}

                for art in unclustered_articles:
                    if art.id in points_dict:
                        vectors.append(points_dict[art.id])
                        valid_articles.append(art)
            except Exception as e:
                logger.error("Failed to fetch vectors for batch clustering: %s", e)
                return 0

            if len(valid_articles) == 0:
                return 0
            elif len(valid_articles) == 1:
                verified_clusters.append([valid_articles[0]])
            else:
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
                        # Outlier: keep as its own single-article cluster to allow synthesis
                        verified_clusters.append([valid_articles[idx]])
                        continue
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append(valid_articles[idx])

                # Batch fetch ArticleEvents and ArticleEntities for all valid articles to resolve N+1
                valid_article_ids = [art.id for art in valid_articles]

                # Fetch ArticleEvents
                evts_stmt = select(ArticleEvent).where(
                    ArticleEvent.article_id.in_(valid_article_ids)
                )
                evts_res = await session.execute(evts_stmt)
                art_evt_map = {}
                for evt in evts_res.scalars().all():
                    if evt.article_id not in art_evt_map:
                        art_evt_map[evt.article_id] = evt

                # Fetch ArticleEntities
                ents_stmt = select(
                    ArticleEntity.article_id, ArticleEntity.canonical_entity_id
                ).where(
                    ArticleEntity.article_id.in_(valid_article_ids),
                    ArticleEntity.canonical_entity_id.isnot(None),
                )
                ents_res = await session.execute(ents_stmt)
                art_ent_map: dict[uuid.UUID, set[uuid.UUID]] = {}
                for row in ents_res.all():
                    art_id, ent_id = row[0], row[1]
                    if art_id not in art_ent_map:
                        art_ent_map[art_id] = set()
                    art_ent_map[art_id].add(ent_id)

                # All batch reads are done. Close the read transaction before the
                # verification loop below: _verify_merge_with_agents makes
                # sequential LLM calls (minutes in aggregate) during which an open
                # transaction would sit idle and be killed by Postgres's
                # idle_in_transaction_session_timeout (30s in production), failing
                # every later statement with "connection is closed". Loaded ORM
                # objects stay usable because the session factory sets
                # expire_on_commit=False.
                await session.commit()

                # Verify and split clusters using multi-signal similarity + entity overlap
                clustering_audit: list[dict] = []
                for label, art_list in clusters.items():
                    sub_clusters: list[list[Article]] = []
                    for art in art_list:
                        matched_sub = None
                        art_evt = art_evt_map.get(art.id)
                        art_entity_ids = art_ent_map.get(art.id, set())

                        if art_evt:
                            for sub in sub_clusters:
                                # Compare art_evt with all articles in sub-cluster
                                total_sim = 0.0
                                total_entity_sim = 0.0
                                for sub_art in sub:
                                    sub_evt = art_evt_map.get(sub_art.id)
                                    if sub_evt:
                                        total_sim += self._compute_event_similarity_direct(
                                            art_evt, sub_evt
                                        )
                                    else:
                                        total_sim += 0.0

                                    # Entity overlap for this pair
                                    if art_entity_ids:
                                        sub_entity_ids = art_ent_map.get(sub_art.id, set())
                                        if sub_entity_ids or art_entity_ids:
                                            union = art_entity_ids | sub_entity_ids
                                            intersection = art_entity_ids & sub_entity_ids
                                            total_entity_sim += (
                                                len(intersection) / len(union) if union else 0.0
                                            )
                                        else:
                                            total_entity_sim += 0.0

                                avg_sim = total_sim / len(sub)
                                avg_entity_sim = (
                                    total_entity_sim / len(sub) if art_entity_ids else 0.0
                                )
                                # Combined: event similarity (90%) + entity overlap (10%)
                                combined_sim = avg_sim + (0.10 * avg_entity_sim)

                                should_merge = False
                                if combined_sim >= AUTO_MERGE_THRESHOLD:
                                    should_merge = True
                                elif combined_sim >= AGENT_REVIEW_THRESHOLD:
                                    sub_evt = art_evt_map.get(sub[0].id)
                                    if sub_evt:
                                        should_merge = await self._verify_merge_with_agents(
                                            article_a=art,
                                            event_a=art_evt,
                                            article_b=sub[0],
                                            event_b=sub_evt,
                                            similarity_score=combined_sim,
                                        )

                                if should_merge:
                                    matched_sub = sub
                                    clustering_audit.append(
                                        {
                                            "decision": "merge",
                                            "article_id": str(art.id),
                                            "sub_cluster_size": len(sub),
                                            "event_sim": round(avg_sim, 4),
                                            "entity_sim": round(avg_entity_sim, 4),
                                            "combined_sim": round(combined_sim, 4),
                                        }
                                    )
                                    break

                        if matched_sub is not None:
                            matched_sub.append(art)
                        else:
                            sub_clusters.append([art])
                            if art_evt:
                                clustering_audit.append(
                                    {
                                        "decision": "new_sub_cluster",
                                        "article_id": str(art.id),
                                        "reason": "no matching sub-cluster above threshold",
                                    }
                                )

                    # Keep all sub-clusters (even size 1)
                    for sub in sub_clusters:
                        verified_clusters.append(sub)

        # ── Step 3: Fingerprint-based pre-grouping ───────────────────────────
        # Articles sharing an identical event_fingerprint describe the same
        # event, so clusters that share any fingerprint must end up as one.
        #
        # This is a transitive relation and needs union-find. The previous
        # implementation took only the FIRST matching cluster index: when a
        # cluster bridged two already-registered groups it merged into one of
        # them, left the other unmerged, and then re-pointed the bridging
        # fingerprints at the winner — leaving fingerprint_map inconsistent
        # with actual membership and silently producing duplicate stories for
        # the same event.
        #
        # Fingerprints are fetched in one batch query rather than one per
        # article inside a nested loop (previously up to 200 round-trips).
        all_cluster_article_ids = [art.id for cluster in verified_clusters for art in cluster]
        fp_by_article: dict[uuid.UUID, str] = {}
        if all_cluster_article_ids:
            fp_rows = await session.execute(
                select(ArticleEvent.article_id, ArticleEvent.event_fingerprint).where(
                    ArticleEvent.article_id.in_(all_cluster_article_ids),
                    ArticleEvent.is_primary.is_(True),
                    ArticleEvent.event_fingerprint.isnot(None),
                )
            )
            for art_id, fp in fp_rows.all():
                fp_by_article.setdefault(art_id, fp)

        parent: dict[int, int] = {i: i for i in range(len(verified_clusters))}

        def _find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]  # path compression
                i = parent[i]
            return i

        def _union(a: int, b: int) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        fingerprint_owner: dict[str, int] = {}
        for idx, cluster in enumerate(verified_clusters):
            for art in cluster:
                fp = fp_by_article.get(art.id)
                if not fp:
                    continue
                if fp in fingerprint_owner:
                    _union(fingerprint_owner[fp], idx)
                else:
                    fingerprint_owner[fp] = idx

        grouped: dict[int, list[Article]] = {}
        for idx, cluster in enumerate(verified_clusters):
            grouped.setdefault(_find(idx), []).extend(cluster)

        verified_clusters = list(grouped.values())

        stories_created = 0
        synthesis_failed = 0
        # Minimum number of articles required to run full LLM synthesis.
        # Single-article clusters are still persisted (so the article is tracked)
        # but synthesis is deferred until more articles join via incremental merge.
        _MIN_SYNTHESIS_ARTICLES = 2

        for art_list in verified_clusters:
            logger.info("Creating story for cluster with %d articles.", len(art_list))
            newsiq_discovery_clusters_total.inc()
            newsiq_story_article_count.observe(len(art_list))

            story_id = uuid.uuid4()

            # ── Step A: persist the cluster atomically ────────────────────────
            # Only fast, purely transactional work belongs inside the savepoint.
            # Synthesis must NOT run here: it issues its own session.commit()
            # calls, and committing while a SAVEPOINT is open raises
            # "InvalidRequestError: Can't operate on closed transaction inside
            # context manager", which the handler below then swallowed — leaving
            # a half-committed story behind while reporting zero stories created.
            try:
                async with session.begin_nested():
                    now = _now()
                    story = Story(
                        id=story_id,
                        story_status="pending",
                        # Set explicitly rather than relying on the column default,
                        # because candidate retrieval filters on this value.
                        lifecycle_state=StoryLifecycleState.EMERGING,
                        first_seen_at=min(
                            (a.published_at for a in art_list if a.published_at), default=now
                        ),
                        trend_score=1.0,
                        created_at=now,
                        updated_at=now,
                        canonical_event_id=event_identity_service.generate_temporary_id(),
                    )
                    session.add(story)

                    # Seed the Stage B anchor at creation. Without a centroid the
                    # story can never match an incoming article, so it would sit
                    # at its initial size forever.
                    await self.refresh_story_centroid(
                        story, session, article_ids=[a.id for a in art_list]
                    )

                    # Initialize metrics
                    metrics = StoryMetric(
                        story_id=story_id, views=0, bookmarks=0, shares=0, clicks=0
                    )
                    session.add(metrics)

                    # Link articles. Membership in story_articles is now the sole
                    # record of "clustered" — there is no parallel queue state to
                    # keep in sync, and therefore no way for the two to diverge.
                    for art in art_list:
                        session.add(StoryArticle(story_id=story_id, article_id=art.id))

                    from app.services.story_evolution_service import record_story_evolution

                    await record_story_evolution(
                        db=session,
                        story_id=story_id,
                        event_type="created",
                        after_state={"article_count": len(art_list)},
                        notes=f"Created via batch clustering with {len(art_list)} articles.",
                    )

                # Make the cluster durable before the slow LLM work starts, so a
                # synthesis failure can never cost us the grouping decision.
                await session.commit()
                stories_created += 1
            except Exception as e:
                logger.error("Failed to persist story cluster %s: %s", story_id, e)
                try:
                    await session.rollback()
                except Exception as rb_err:
                    logger.warning("Rollback after cluster persist failure failed: %s", rb_err)
                try:
                    from app.core.failure_recorder import record_pipeline_failure

                    await record_pipeline_failure(
                        stage=PipelineStage.CLUSTERING_BATCH,
                        exception=e,
                        story_id=story_id,
                        input_payload={"article_count": len(art_list)},
                    )
                except Exception as rec_err:
                    logger.error(
                        "Failed to record pipeline failure for story %s: %s", story_id, rec_err
                    )
                continue

            # ── Step B: synthesis, outside any savepoint ──────────────────────
            # Runs in its own transaction(s) and is safely retryable: the story
            # and its article links are already durable, so a failure here leaves
            # an unsynthesised story rather than losing the cluster. This is the
            # same state single-article clusters are deliberately left in.
            if len(art_list) < _MIN_SYNTHESIS_ARTICLES:
                logger.info(
                    "Cluster for story %s has only %d article(s) — deferring synthesis "
                    "until more articles join via incremental merge.",
                    story_id,
                    len(art_list),
                )
                continue

            try:
                await self.generate_story_content(story, art_list, session)
                await self.compute_trending_score(story, session)
            except Exception as e:
                synthesis_failed += 1
                logger.error(
                    "Synthesis failed for story %s (cluster is persisted and retryable): %s",
                    story_id,
                    e,
                )
                try:
                    await session.rollback()
                except Exception as rb_err:
                    logger.warning("Rollback after synthesis failure failed: %s", rb_err)
                try:
                    from app.core.failure_recorder import record_pipeline_failure

                    await record_pipeline_failure(
                        stage="story_synthesis",
                        exception=e,
                        story_id=story_id,
                        input_payload={"article_count": len(art_list)},
                    )
                except Exception as rec_err:
                    logger.error(
                        "Failed to record pipeline failure for story %s: %s", story_id, rec_err
                    )

        await session.commit()

        logger.info(
            "Batch clustering finished",
            extra={
                "eligible_articles": len(unclustered_articles),
                "clusters_formed": len(verified_clusters),
                "stories_created": stories_created,
                "synthesis_failed": synthesis_failed,
            },
        )
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
        from app.models.models import StoryMetric

        stmt_metrics = select(StoryMetric).where(StoryMetric.story_id == story.id)
        res_metrics = await session.execute(stmt_metrics)
        m = res_metrics.scalar_one_or_none()
        if m:
            raw = (m.views or 0) * 1 + (m.bookmarks or 0) * 3 + (m.shares or 0) * 5
            engagement_score = min(raw / 500.0, 1.0)

        # ── Weighted composite ────────────────────────────────────────────────
        score = (0.40 * source_score) + (0.35 * recency_score) + (0.25 * engagement_score)

        story.trend_score = score
        await session.commit()

        logger.debug(
            "Trending score for story %s: %.4f "
            "(source=%.2f, recency=%.2f, engagement=%.2f, hours=%.1f)",
            story.id,
            score,
            source_score,
            recency_score,
            engagement_score,
            hours_elapsed,
        )
        return score


clustering_service = ClusteringService()
