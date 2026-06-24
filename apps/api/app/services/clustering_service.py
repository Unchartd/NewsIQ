"""Service for clustering articles into stories using HDBSCAN and incremental vector match."""

import logging
import uuid
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

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
    StoryMetric,
    StorySourceCoverage,
    StoryTag,
    StoryTimelineEvent,
)
from app.services.ai_service import CATEGORY_SLUGS, ai_service
from app.services.ner_service_v2 import ner_service_v2
from app.services.vector_service import vector_service
from app.services.entity_linker import entity_linker
from app.services.knowledge_graph import build_story_knowledge_graph
from app.services.contradiction_service import contradiction_service
from app.services.source_comparison_service import source_comparison_service
from app.core.trace import StageSpan, PipelineStage

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80  # Cosine similarity threshold for real-time merge


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def uuid_to_advisory_lock_id(u: uuid.UUID) -> int:
    """Fold a 128-bit UUID into a signed 64-bit integer lock ID."""
    val = u.int
    upper = val >> 64
    lower = val & 0xffffffffffffffff
    lock_id = (upper ^ lower) & 0xffffffffffffffff
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
        await session.execute(
            delete(StoryDifference).where(StoryDifference.story_id == story.id)
        )
        await session.execute(
            delete(StoryEntity).where(StoryEntity.story_id == story.id)
        )
        await session.execute(
            delete(StoryTag).where(StoryTag.story_id == story.id)
        )
        await session.execute(
            delete(StoryContradiction).where(StoryContradiction.story_id == story.id)
        )
        await session.flush()

        # 2. Prepare article details, fetch sources and article events
        full_text_corpus = ""
        source_countries = []
        seen_sources = set()
        sources_list = []
        article_source_map = {}
        for art in articles:
            stmt = select(Source).where(Source.id == art.source_id)
            res = await session.execute(stmt)
            source = res.scalar_one_or_none()
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

        article_ids = [art.id for art in articles]
        stmt = select(ArticleEvent).where(ArticleEvent.article_id.in_(article_ids))
        res = await session.execute(stmt)
        article_events = list(res.scalars().all())

        # 3. Save Timeline Events (Sorted by parsed event time with UTC normalization)
        saved_timeline_objects = []
        timeline_entries = []
        async with StageSpan(stage=PipelineStage.TIMELINE_GENERATION, story_id=str(story.id)) as span:
            for evt in article_events:
                t = evt.event_time or evt.created_at or _now()
                if t.tzinfo is not None:
                    t = t.astimezone(UTC).replace(tzinfo=None)

                src_name = article_source_map.get(evt.article_id, "Unknown Source")
                evt_type = (evt.event_type_canonical or evt.event_type or "Event").replace("_", " ").title()

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
                desc = f"{evt_type} reported by {src_name}{details_str}."

                timeline_entries.append({
                    "event_time": t,
                    "event_time_raw": evt.event_time_raw or t.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "description": desc,
                })

            # Sort timeline entries chronologically
            timeline_entries.sort(key=lambda x: x["event_time"])

            for entry in timeline_entries:
                tl_event = StoryTimelineEvent(
                    id=uuid.uuid4(),
                    story_id=story.id,
                    event_time=entry["event_time"],
                    event_time_raw=entry["event_time_raw"],
                    description=entry["description"],
                    created_at=_now(),
                )
                session.add(tl_event)
                saved_timeline_objects.append(tl_event)
            
            span.set_metadata({
                "inputs": {"article_events_count": len(article_events)},
                "outputs": {"timeline_events_count": len(saved_timeline_objects)}
            })

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
                entities = [
                    {"type": e.entity_type, "value": e.entity_value}
                    for e in pre_entities
                ]
                logger.info(
                    "Using %d pre-extracted article entities for story %s.",
                    len(entities), story.id,
                )
            else:
                # Fallback: run NER v2 on full corpus (for old articles without pre-extraction)
                entities = await ner_service_v2.extract_entities(full_text_corpus)

            span.set_metadata({
                "inputs": {"corpus_length": len(full_text_corpus), "pre_extracted": bool(pre_entities)},
                "outputs": {"entities_extracted": len(entities)}
            })

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
                
            span.set_metadata({
                "inputs": {"entities_to_link": len(entities)},
                "outputs": {
                    "canonical_entities_linked": len(saved_story_entities),
                    "tags": list(tags_added)
                }
            })

        # 6. Run Contradiction & Source Comparison Engines
        saved_contras = []
        async with StageSpan(stage=PipelineStage.CONTRADICTION_DETECTION, story_id=str(story.id)) as span:
            try:
                saved_contras = await contradiction_service.detect_and_save_contradictions(story.id, session)
                logger.info("Contradiction detection successfully run for story %s.", story.id)
            except Exception as e:
                logger.error("Failed to detect contradictions for story %s: %s", story.id, e)
            
            span.set_metadata({
                "inputs": {"story_id": str(story.id)},
                "outputs": {"contradictions_count": len(saved_contras)}
            })

        saved_coverage = []
        saved_differences = []
        async with StageSpan(stage=PipelineStage.SOURCE_COMPARISON, story_id=str(story.id)) as span:
            try:
                saved_coverage, saved_differences = await source_comparison_service.compare_sources_and_save(story.id, session)
                logger.info("Source comparison successfully run for story %s.", story.id)
            except Exception as e:
                logger.error("Failed to run source comparison for story %s: %s", story.id, e)
            
            span.set_metadata({
                "inputs": {"story_id": str(story.id)},
                "outputs": {"differences_count": len(saved_differences)}
            })

        # 5. Build and Serialize Knowledge Graph
        kg_dict = {}
        async with StageSpan(stage=PipelineStage.KNOWLEDGE_GRAPH, story_id=str(story.id)) as span:
            try:
                kg = build_story_knowledge_graph(
                    articles=articles,
                    article_events=article_events,
                    story_entities=saved_story_entities,
                    sources=sources_list,
                )
                kg_dict = kg.to_dict()
                story.knowledge_graph = kg_dict
                logger.info("Knowledge Graph successfully generated and assigned for story %s.", story.id)
            except Exception as e:
                logger.error("Failed to generate knowledge graph for story %s: %s", story.id, e)
            
            span.set_metadata({
                "inputs": {"articles_count": len(articles)},
                "outputs": {"nodes_count": len(kg_dict.get("nodes", [])), "edges_count": len(kg_dict.get("edges", []))}
            })

        # Serialize inputs for KG-grounded summarization
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
                "date": t.event_time_raw or (t.event_time.isoformat() if t.event_time else "Unknown"),
                "description": t.description,
            }
            for t in saved_timeline_objects
        ]

        source_comparisons_list = []
        for diff in saved_differences:
            cov = next((c for c in saved_coverage if c.source_id == diff.source_id), None)
            focus = cov.focus_area if cov else "General coverage"
            src_name = article_source_map.get(
                next((art.id for art in articles if art.source_id == diff.source_id), None),
                "Unknown Source"
            )
            source_comparisons_list.append({
                "source_name": src_name,
                "focus_area": focus,
                "unique_information": diff.unique_information or "",
                "missing_information": diff.missing_information or "",
                "contradictions": diff.contradictions or "",
            })

        # 7. Call Summary Engine (KG-grounded summarization)
        cat_slug = "world"
        async with StageSpan(stage=PipelineStage.SUMMARY_GENERATION, story_id=str(story.id)) as span:
            try:
                summary_res = await ai_service.summarize_story_from_kg(
                    kg=kg_dict,
                    contradictions=contradictions_list,
                    timeline=timeline_list,
                    source_comparisons=source_comparisons_list,
                )

                # Update main story details
                story.headline = summary_res.headline
                story.one_line_summary = summary_res.one_line_summary
                story.short_summary = summary_res.short_summary
                story.detailed_summary = summary_res.detailed_summary
                story.key_facts = [f for f in summary_res.key_facts if f] if summary_res.key_facts else []

                # Resolve and assign category
                cat_slug = summary_res.category if summary_res.category in CATEGORY_SLUGS else "world"

                # Summary Reflection Verification
                is_trending_or_high_stakes = (
                    len(articles) >= 3 
                    or cat_slug in ("world", "politics", "business")
                )
                if is_trending_or_high_stakes:
                    try:
                        from app.agents.reflection_agent import reflect_on_summary
                        reflection = await reflect_on_summary(
                            summary_text=story.detailed_summary or "",
                            timeline=timeline_list,
                            kg_nodes=kg_dict.get("nodes", []),
                            source_coverage=source_comparisons_list
                        )
                        logger.info("Summary Reflection result for story %s: %s", story.id, reflection.model_dump())

                        if reflection.has_hallucinations or reflection.contradicts_graph:
                            logger.warning(
                                "Reflection Agent detected issues/hallucinations for story %s. Regenerating summary.",
                                story.id
                            )
                            # Regenerate summary
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
                            story.key_facts = [f for f in summary_res.key_facts if f] if summary_res.key_facts else []
                    except Exception as reflection_exc:
                        logger.error("Reflection verification failed for story %s: %s", story.id, reflection_exc)

                cat_id = await self.get_or_create_category(
                    cat_slug, cat_slug.replace("-", " ").title(), session
                )
                story.category_id = cat_id
                story.story_status = "active"
                logger.info("Story summaries successfully synthesized and updated for story %s.", story.id)
            except Exception as e:
                logger.error("Failed to summarize story from KG %s: %s", story.id, e)
                story.headline = story.headline or "Factual Synthesis"
                story.one_line_summary = story.one_line_summary or "Factual Synthesis of events."
                story.short_summary = story.short_summary or "Factual Synthesis of events."
                story.detailed_summary = story.detailed_summary or "Factual Synthesis of events."
                story.key_facts = story.key_facts or []

            span.set_metadata({
                "inputs": {
                    "kg_nodes": len(kg_dict.get("nodes", [])),
                    "contradictions_count": len(contradictions_list),
                    "timeline_count": len(timeline_list),
                },
                "outputs": {
                    "headline": story.headline,
                    "category": cat_slug,
                    "one_line_summary": story.one_line_summary,
                    "short_summary": story.short_summary,
                    "key_facts": story.key_facts
                }
            })

        if commit:
            await session.commit()
        else:
            await session.flush()

        # 8. Index in Meilisearch and invalidate caches for this story
        async with StageSpan(stage=PipelineStage.INDEXING, story_id=str(story.id)) as span:
            await self._index_and_invalidate(story, cat_slug, list(tags_added))
            span.set_metadata({
                "inputs": {"story_id": str(story.id), "category": cat_slug, "tags": list(tags_added)},
                "outputs": {"indexed": True}
            })

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
        # Acquire transaction-bound advisory lock on story_id
        lock_id = uuid_to_advisory_lock_id(story_id)
        await session.execute(
            text(f"SELECT pg_advisory_xact_lock({lock_id})")
        )

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
        await session.flush()

        # Retrieve the story and all associated articles to update summaries with eagerly loaded relations
        stmt = select(Story).options(
            selectinload(Story.category),
            selectinload(Story.metrics)
        ).where(Story.id == story_id)
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

    def _compute_event_similarity_direct(self, evt1: ArticleEvent, evt2: ArticleEvent) -> float:
        """Directly compare two ArticleEvent objects and compute similarity score."""
        from app.services.event_taxonomy import get_parent_type

        # 1. Event Type Similarity (15%)
        type_sim = 0.0
        if evt1.event_type_canonical and evt2.event_type_canonical:
            if evt1.event_type_canonical == evt2.event_type_canonical:
                type_sim = 1.0
            elif get_parent_type(evt1.event_type_canonical) == get_parent_type(evt2.event_type_canonical):
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

    async def compute_story_similarity(
        self, article_event: ArticleEvent, story: Story, session: AsyncSession
    ) -> float:
        """Compute the average similarity between a new event and all events inside a story (including entity overlap)."""
        # Fetch events of all articles in the story
        stmt = select(ArticleEvent).join(StoryArticle, StoryArticle.article_id == ArticleEvent.article_id).where(StoryArticle.story_id == story.id)
        res = await session.execute(stmt)
        story_events = list(res.scalars().all())

        if not story_events:
            return 1.0  # Default to match if story has no events yet

        total_sim = 0.0
        for sevt in story_events:
            total_sim += self._compute_event_similarity_direct(article_event, sevt)

        avg_sim = total_sim / len(story_events)

        # Entity overlap (10%)
        art_ent_stmt = select(ArticleEntity.canonical_entity_id).where(
            ArticleEntity.article_id == article_event.article_id,
            ArticleEntity.canonical_entity_id.isnot(None),
        )
        art_ent_res = await session.execute(art_ent_stmt)
        art_entity_ids = set(row[0] for row in art_ent_res.all())

        stmt_story_art = select(StoryArticle.article_id).where(StoryArticle.story_id == story.id)
        res_story_art = await session.execute(stmt_story_art)
        story_article_ids = list(res_story_art.scalars().all())

        total_entity_sim = 0.0
        if story_article_ids:
            for sub_art_id in story_article_ids:
                if art_entity_ids:
                    sub_ent_stmt = select(ArticleEntity.canonical_entity_id).where(
                        ArticleEntity.article_id == sub_art_id,
                        ArticleEntity.canonical_entity_id.isnot(None),
                    )
                    sub_ent_res = await session.execute(sub_ent_stmt)
                    sub_entity_ids = set(row[0] for row in sub_ent_res.all())
                    if sub_entity_ids or art_entity_ids:
                        union = art_entity_ids | sub_entity_ids
                        intersection = art_entity_ids & sub_entity_ids
                        total_entity_sim += len(intersection) / len(union) if union else 0.0

        avg_entity_sim = total_entity_sim / len(story_events) if (story_events and art_entity_ids) else 0.0
        return avg_sim + (0.10 * avg_entity_sim)

    async def _verify_merge_with_agents(
        self,
        article_a: Article,
        event_a: ArticleEvent,
        article_b: Article,
        event_b: ArticleEvent,
        similarity_score: float,
        category_slug: str = "",
        kg_nodes: list = None,
    ) -> bool:
        """Call Agno agents to verify if two articles describe the same event, using Judge Agent if needed."""
        from app.agents.cluster_verification_agent import verify_cluster_decision
        from app.core.config import settings

        art_a_evt_dict = {
            "type": event_a.event_type_canonical,
            "actors": event_a.actors,
            "targets": event_a.targets,
            "location": event_a.location,
            "time": str(event_a.event_time) if event_a.event_time else ""
        }
        art_b_evt_dict = {
            "type": event_b.event_type_canonical,
            "actors": event_b.actors,
            "targets": event_b.targets,
            "location": event_b.location,
            "time": str(event_b.event_time) if event_b.event_time else ""
        }

        text_to_check = ((article_a.title or "") + " " + (article_b.title or "")).lower()
        high_stakes = category_slug in ("world", "politics", "business") or any(
            w in text_to_check for w in ("war", "election", "finance", "military", "police", "arrest", "attack")
        )

        if high_stakes and settings.OPENAI_API_KEY:
            try:
                from agno.agent import Agent
                from agno.models.openai import OpenAIChat
                from app.agents.cluster_verification_agent import cluster_verification_agent
                from app.agents.base_agent import run_agent_with_observability
                from app.agents.judge_agent import resolve_disagreement

                openai_agent = Agent(
                    name="OpenAI Verification Agent",
                    model=OpenAIChat(id="gpt-4o-mini"),
                    instructions=cluster_verification_agent.instructions,
                    output_schema=cluster_verification_agent.output_schema
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
                Knowledge Graph Context: {kg_nodes or 'None'}

                Determine if they represent the same event.
                """

                # Run Gemini and OpenAI agents
                gemini_ver = await verify_cluster_decision(
                    article_a_title=article_a.title or "",
                    article_a_event=art_a_evt_dict,
                    article_b_title=article_b.title or "",
                    article_b_event=art_b_evt_dict,
                    similarity_score=similarity_score,
                    kg_nodes=kg_nodes
                )

                run_output_oa = await run_agent_with_observability(
                    agent=openai_agent,
                    prompt=prompt,
                    stage="cluster_verification"
                )
                openai_ver = run_output_oa.content

                if gemini_ver.same_event != openai_ver.same_event:
                    judgment = await resolve_disagreement(
                        task_description="Verify if two articles describe the same event",
                        provider_a_name="gemini",
                        provider_a_output=gemini_ver.model_dump(),
                        provider_b_name="openai",
                        provider_b_output=openai_ver.model_dump(),
                        context=f"Article A: {article_a.title}\nArticle B: {article_b.title}"
                    )
                    logger.info(
                        "Judge Agent resolved disagreement between Gemini (%s) and OpenAI (%s) to: %s (explanation: %s)",
                        gemini_ver.same_event, openai_ver.same_event, judgment.final_decision, judgment.explanation
                    )
                    return judgment.final_decision
                else:
                    return gemini_ver.same_event
            except Exception as e:
                logger.error("Dual-agent verification failed, falling back to Gemini only: %s", e)

        # Primary Gemini-only path (default)
        try:
            gemini_ver = await verify_cluster_decision(
                article_a_title=article_a.title or "",
                article_a_event=art_a_evt_dict,
                article_b_title=article_b.title or "",
                article_b_event=art_b_evt_dict,
                similarity_score=similarity_score,
                kg_nodes=kg_nodes
            )
            return gemini_ver.same_event
        except Exception as e:
            logger.error("Gemini cluster verification agent failed, falling back to True/False based on threshold: %s", e)
            return similarity_score >= 0.80

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

        # Fetch the article's event for multi-signal verification
        stmt = select(ArticleEvent).where(ArticleEvent.article_id == article_id).limit(1)
        res = await session.execute(stmt)
        article_event = res.scalar_one_or_none()

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
                # Acquire transaction-bound advisory lock on story_id
                lock_id = uuid_to_advisory_lock_id(story_id)
                await session.execute(
                    text(f"SELECT pg_advisory_xact_lock({lock_id})")
                )

                # Check if already merged in another concurrent task
                stmt_chk = select(StoryArticle).where(
                    StoryArticle.story_id == story_id, StoryArticle.article_id == article_id
                )
                res_chk = await session.execute(stmt_chk)
                if res_chk.scalar_one_or_none():
                    return False

                # Retrieve the story with eagerly loaded relations to avoid lazy-load MissingGreenlet errors
                stmt_story = select(Story).options(
                    selectinload(Story.category),
                    selectinload(Story.metrics)
                ).where(Story.id == story_id)
                res_story = await session.execute(stmt_story)
                story = res_story.scalar_one_or_none()

                if story and article_event:
                    # Gated merge using multi-signal similarity + Agno Agent verification
                    score = await self.compute_story_similarity(article_event, story, session)

                    should_merge = False
                    if score >= 0.90:
                        should_merge = True
                        logger.info("Auto-merging article %s into story %s (similarity: %.2f >= 0.90)", article_id, story_id, score)
                    elif score >= 0.70:
                        # Fetch Article B (first article of the story) to compare events
                        stmt_first_art = select(Article).join(StoryArticle).where(StoryArticle.story_id == story.id).limit(1)
                        res_first_art = await session.execute(stmt_first_art)
                        first_art = res_first_art.scalar_one_or_none()

                        first_evt = None
                        if first_art:
                            stmt_evt = select(ArticleEvent).where(ArticleEvent.article_id == first_art.id).limit(1)
                            res_evt = await session.execute(stmt_evt)
                            first_evt = res_evt.scalar_one_or_none()

                        if first_art and first_evt:
                            category_slug = story.category.slug if story.category else ""
                            should_merge = await self._verify_merge_with_agents(
                                article_a=article,
                                event_a=article_event,
                                article_b=first_art,
                                event_b=first_evt,
                                similarity_score=score,
                                category_slug=category_slug,
                                kg_nodes=story.knowledge_graph.get("nodes", []) if story.knowledge_graph else []
                            )
                        else:
                            should_merge = score >= 0.80  # fallback

                    if not should_merge:
                        logger.info(
                            "Rejecting merge of article %s into story %s. Multi-signal similarity: %.2f (< 0.70 or verification failed)",
                            article_id,
                            story_id,
                            score,
                        )
                        continue  # Try next candidate match
                else:
                    logger.warning(
                        "Rejecting merge of article %s into story %s due to missing event or story metadata.",
                        article_id,
                        story_id,
                    )
                    continue

                return await self.merge_article_into_existing_story(article, story_id, session)

        return False

    async def run_batch_clustering(self, session: AsyncSession) -> int:
        """Run HDBSCAN clustering on unclustered articles."""
        GLOBAL_CLUSTERING_LOCK_ID = 888888888
        await session.execute(
            text(f"SELECT pg_advisory_lock({GLOBAL_CLUSTERING_LOCK_ID})")
        )
        try:
            return await self._run_batch_clustering_locked(session)
        finally:
            await session.execute(
                text(f"SELECT pg_advisory_unlock({GLOBAL_CLUSTERING_LOCK_ID})")
            )

    async def _run_batch_clustering_locked(self, session: AsyncSession) -> int:
        """Internal method running batch clustering under global lock."""
        # Ensure all canonical categories exist
        await self._ensure_all_categories(session)

        # Select articles where embedding is completed and they are not in story_articles
        subquery = select(StoryArticle.article_id)
        stmt = select(Article).where(
            Article.embedding_status == "completed", ~Article.id.in_(subquery)
        )
        res = await session.execute(stmt)
        unclustered_articles = list(res.scalars().all())

        if len(unclustered_articles) < 1:
            logger.info("No unclustered articles to run batch clustering.")
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
                points_dict = {uuid.UUID(p.id): p.vector for p in points if p.vector}

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

                # Verify and split clusters using multi-signal similarity + entity overlap
                clustering_audit: list[dict] = []
                for label, art_list in clusters.items():
                    sub_clusters: list[list[Article]] = []
                    for art in art_list:
                        matched_sub = None
                        stmt = select(ArticleEvent).where(ArticleEvent.article_id == art.id).limit(1)
                        res = await session.execute(stmt)
                        art_evt = res.scalar_one_or_none()

                        # Get canonical entity IDs for this article
                        art_ent_stmt = select(ArticleEntity.canonical_entity_id).where(
                            ArticleEntity.article_id == art.id,
                            ArticleEntity.canonical_entity_id.isnot(None),
                        )
                        art_ent_res = await session.execute(art_ent_stmt)
                        art_entity_ids = set(row[0] for row in art_ent_res.all())

                        if art_evt:
                            for sub in sub_clusters:
                                # Compare art_evt with all articles in sub-cluster
                                total_sim = 0.0
                                total_entity_sim = 0.0
                                for sub_art in sub:
                                    stmt_sub = select(ArticleEvent).where(ArticleEvent.article_id == sub_art.id).limit(1)
                                    res_sub = await session.execute(stmt_sub)
                                    sub_evt = res_sub.scalar_one_or_none()
                                    if sub_evt:
                                        total_sim += self._compute_event_similarity_direct(art_evt, sub_evt)
                                    else:
                                        total_sim += 0.0

                                    # Entity overlap for this pair
                                    if art_entity_ids:
                                        sub_ent_stmt = select(ArticleEntity.canonical_entity_id).where(
                                            ArticleEntity.article_id == sub_art.id,
                                            ArticleEntity.canonical_entity_id.isnot(None),
                                        )
                                        sub_ent_res = await session.execute(sub_ent_stmt)
                                        sub_entity_ids = set(row[0] for row in sub_ent_res.all())
                                        if sub_entity_ids or art_entity_ids:
                                            union = art_entity_ids | sub_entity_ids
                                            intersection = art_entity_ids & sub_entity_ids
                                            total_entity_sim += len(intersection) / len(union) if union else 0.0
                                        else:
                                            total_entity_sim += 0.0

                                avg_sim = total_sim / len(sub)
                                avg_entity_sim = total_entity_sim / len(sub) if art_entity_ids else 0.0
                                # Combined: event similarity (90%) + entity overlap (10%)
                                combined_sim = avg_sim + (0.10 * avg_entity_sim)

                                should_merge = False
                                if combined_sim >= 0.90:
                                    should_merge = True
                                elif combined_sim >= 0.70:
                                    stmt_sub_evt = select(ArticleEvent).where(ArticleEvent.article_id == sub[0].id).limit(1)
                                    res_sub_evt = await session.execute(stmt_sub_evt)
                                    sub_evt = res_sub_evt.scalar_one_or_none()
                                    if sub_evt:
                                        should_merge = await self._verify_merge_with_agents(
                                            article_a=art,
                                            event_a=art_evt,
                                            article_b=sub[0],
                                            event_b=sub_evt,
                                            similarity_score=combined_sim
                                        )

                                if should_merge:
                                    matched_sub = sub
                                    clustering_audit.append({
                                        "decision": "merge",
                                        "article_id": str(art.id),
                                        "sub_cluster_size": len(sub),
                                        "event_sim": round(avg_sim, 4),
                                        "entity_sim": round(avg_entity_sim, 4),
                                        "combined_sim": round(combined_sim, 4),
                                    })
                                    break

                        if matched_sub is not None:
                            matched_sub.append(art)
                        else:
                            sub_clusters.append([art])
                            if art_evt:
                                clustering_audit.append({
                                    "decision": "new_sub_cluster",
                                    "article_id": str(art.id),
                                    "reason": "no matching sub-cluster above threshold",
                                })


                    # Keep all sub-clusters (even size 1)
                    for sub in sub_clusters:
                        verified_clusters.append(sub)

        # ── Step 3: Fingerprint-based pre-grouping ───────────────────────────
        # Articles sharing identical event_fingerprint describe the same event.
        # Merge them into the same cluster if they ended up in different ones.
        fingerprint_map: dict[str, int] = {}  # fingerprint → cluster index
        merged_clusters: list[list[Article]] = []
        for cluster in verified_clusters:
            # Get fingerprints for articles in this cluster
            cluster_fps: set[str] = set()
            for art in cluster:
                fp_stmt = select(ArticleEvent.event_fingerprint).where(
                    ArticleEvent.article_id == art.id,
                    ArticleEvent.is_primary == True,  # noqa: E712
                    ArticleEvent.event_fingerprint.isnot(None),
                )
                fp_res = await session.execute(fp_stmt)
                fp = fp_res.scalars().first()
                if fp:
                    cluster_fps.add(fp)

            # Check if any fingerprint already has a cluster
            target_idx: int | None = None
            for fp in cluster_fps:
                if fp in fingerprint_map:
                    target_idx = fingerprint_map[fp]
                    break

            if target_idx is not None:
                # Merge into existing cluster
                merged_clusters[target_idx].extend(cluster)
                for fp in cluster_fps:
                    fingerprint_map[fp] = target_idx
            else:
                # New cluster
                idx = len(merged_clusters)
                merged_clusters.append(cluster)
                for fp in cluster_fps:
                    fingerprint_map[fp] = idx

        verified_clusters = merged_clusters

        stories_created = 0

        for art_list in verified_clusters:
            logger.info("Creating story for cluster with %d articles.", len(art_list))

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
            story.id, score, source_score, recency_score, engagement_score, hours_elapsed,
        )
        return score


clustering_service = ClusteringService()

