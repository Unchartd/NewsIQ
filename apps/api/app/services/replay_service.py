"""Service layer for replaying the intelligence pipeline on existing stories."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.trace import PipelineRun, PipelineStage, StageSpan
from app.models.models import (
    Article,
    ArticleEvent,
    Source,
    Story,
    StoryArticle,
    StoryContradiction,
    StoryDifference,
    StoryEntity,
    StorySourceCoverage,
    StoryTag,
    StoryTimelineEvent,
)

logger = logging.getLogger(__name__)


class ReplayService:
  """Orchestrates pipeline execution replays for debug/telemetry profiling."""

  async def replay_full_story(self, story_id: uuid.UUID, db: AsyncSession) -> None:
    """Regenerate the entire story intelligence pipeline from original articles."""
    logger.info("Starting full story pipeline replay for story %s", story_id)

    # 1. Fetch story and associated articles
    story_result = await db.execute(
        select(Story)
        .where(Story.id == story_id)
        .options(
            selectinload(Story.articles).selectinload(StoryArticle.article)
        )
    )
    story = story_result.scalar_one_or_none()
    if not story:
      raise ValueError(f"Story {story_id} not found")

    articles = [sa.article for sa in story.articles]
    if not articles:
      logger.warning("No articles found in story %s cluster. Replay aborted.", story_id)
      return

    # 2. Run the complete pipeline inside a PipelineRun context
    async with PipelineRun(trigger="manual", pipeline_type="incremental", is_replay=True, parent_run_id=str(story_id)) as run:
      # We delegate to the clustering service generate method, but wrap it in StageSpans
      # to ensure telemetry is captured for each sub-stage during the replay.
      from app.services.clustering_service import clustering_service

      async with StageSpan(run, stage=PipelineStage.DIFFERENCE_ENGINE, story_id=str(story_id)) as span:
        await clustering_service.generate_story_content(story, articles, db)
        span.set_metadata({"articles_replayed": len(articles)})

  async def replay_story_stage(
      self, story_id: uuid.UUID, stage_name: str, db: AsyncSession
  ) -> None:
    """Replay a specific stage of the story pipeline."""
    logger.info("Starting story stage replay for story %s, stage %s", story_id, stage_name)

    # Fetch story and articles
    story_result = await db.execute(
        select(Story)
        .where(Story.id == story_id)
        .options(
            selectinload(Story.articles).selectinload(StoryArticle.article)
        )
    )
    story = story_result.scalar_one_or_none()
    if not story:
      raise ValueError(f"Story {story_id} not found")

    articles = [sa.article for sa in story.articles]
    if not articles:
      logger.warning("No articles found in story %s. Stage replay aborted.", story_id)
      return

    async with PipelineRun(trigger="manual", pipeline_type="incremental", is_replay=True, parent_run_id=str(story_id)) as run:
      # Resolve stage name to canonical stage enum
      if stage_name == "entity_extraction":
        async with StageSpan(run, stage=PipelineStage.ENTITY_EXTRACTION, story_id=str(story_id)) as span:
          await self._replay_entity_extraction(story, articles, db)
          span.set_metadata({"stage": "entity_extraction", "articles": len(articles)})

      elif stage_name == "contradiction_detection":
        async with StageSpan(run, stage=PipelineStage.CONTRADICTION_DETECTION, story_id=str(story_id)) as span:
          from app.services.contradiction_service import contradiction_service
          # Clear old contradictions first
          await db.execute(delete(StoryContradiction).where(StoryContradiction.story_id == story_id))
          await db.flush()
          await contradiction_service.detect_and_save_contradictions(story_id, db)
          span.set_metadata({"stage": "contradiction_detection"})

      elif stage_name == "timeline_generation":
        async with StageSpan(run, stage=PipelineStage.TIMELINE_GENERATION, story_id=str(story_id)) as span:
          await self._replay_timeline_generation(story, articles, db)
          span.set_metadata({"stage": "timeline_generation"})

      elif stage_name == "summary_generation":
        async with StageSpan(run, stage=PipelineStage.SUMMARY_GENERATION, story_id=str(story_id)) as span:
          await self._replay_summary_generation(story, articles, db)
          span.set_metadata({"stage": "summary_generation"})

      else:
        raise ValueError(f"Unsupported replay stage: {stage_name}")

  async def _replay_entity_extraction(
      self, story: Story, articles: list[Article], session: AsyncSession
  ) -> None:
    """Internal helper to execute and persist entity extraction during replay."""
    from app.services import entity_linker, ner_service_v2

    # Clear existing entities and tags
    await session.execute(delete(StoryEntity).where(StoryEntity.story_id == story.id))
    await session.execute(delete(StoryTag).where(StoryTag.story_id == story.id))
    await session.flush()

    full_text_corpus = ""
    for art in articles:
      full_text_corpus += f"{(art.title or '')}\n{(art.description or '')}\n{(art.content or '')}\n\n"

    entities = await ner_service_v2.extract_entities(full_text_corpus)
    grouped_entities = entity_linker.group_entities_locally(entities)

    tags_added = set()
    for rep, grouped_mentions in list(grouped_entities.items())[:15]:
      etype = grouped_mentions[0]["type"]
      try:
        canonical_ent = await entity_linker.link_entity(
            name=rep,
            entity_type=etype,
            context=full_text_corpus,
            session=session,
        )
        canonical_entity_id = canonical_ent.id
      except Exception:
        canonical_ent = None
        canonical_entity_id = None

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

      tag = rep.lower().strip()
      if tag and len(tag) < 30 and tag not in tags_added:
        tags_added.add(tag)

    for tag in list(tags_added)[:5]:
      session.add(StoryTag(id=uuid.uuid4(), story_id=story.id, tag_name=tag))

    await session.commit()

  async def _replay_timeline_generation(
      self, story: Story, articles: list[Article], session: AsyncSession
  ) -> None:
    """Internal helper to rebuild story timeline events during replay."""
    # Clear existing events
    await session.execute(delete(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id))
    await session.flush()

    article_source_map = {}
    for art in articles:
      stmt = select(Source).where(Source.id == art.source_id)
      res = await session.execute(stmt)
      source = res.scalar_one_or_none()
      article_source_map[art.id] = source.name if source else "Unknown Source"

    article_ids = [art.id for art in articles]
    stmt = select(ArticleEvent).where(ArticleEvent.article_id.in_(article_ids))
    res = await session.execute(stmt)
    article_events = list(res.scalars().all())

    timeline_entries = []
    for evt in article_events:
      t = evt.event_time or evt.created_at or datetime.now(UTC).replace(tzinfo=None)
      src_name = article_source_map.get(evt.article_id, "Unknown Source")
      evt_type = (evt.event_type_canonical or evt.event_type or "Event").replace("_", " ").title()

      details = []
      if evt.actors:
        details.append(f"Actors: {', '.join(evt.actors)}")
      if evt.targets:
        details.append(f"Targets: {', '.join(evt.targets)}")
      if evt.location:
        details.append(f"Location: {evt.location}")

      details_str = f" ({'; '.join(details)})" if details else ""
      desc = f"{evt_type} reported by {src_name}{details_str}."

      timeline_entries.append({
          "event_time": t.replace(tzinfo=None) if t.tzinfo else t,
          "event_time_raw": evt.event_time_raw or t.strftime("%Y-%m-%d %H:%M:%S UTC"),
          "description": desc,
      })

    timeline_entries.sort(key=lambda x: x["event_time"])

    for entry in timeline_entries:
      tl_event = StoryTimelineEvent(
          id=uuid.uuid4(),
          story_id=story.id,
          event_time=entry["event_time"],
          event_time_raw=entry["event_time_raw"],
          description=entry["description"],
          created_at=datetime.now(UTC).replace(tzinfo=None),
      )
      session.add(tl_event)

    await session.commit()

  async def _replay_summary_generation(
      self, story: Story, articles: list[Article], session: AsyncSession
  ) -> None:
    """Internal helper to regenerate AI summaries from the story knowledge graph."""
    from app.services.ai_service import ai_service

    # Load contradictions and timeline events to feed summary generator
    stmt_timeline = select(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id)
    res_timeline = await session.execute(stmt_timeline)
    timeline_objects = res_timeline.scalars().all()

    stmt_contras = select(StoryContradiction).where(StoryContradiction.story_id == story.id)
    res_contras = await session.execute(stmt_contras)
    contradictions = res_contras.scalars().all()

    timeline_list = [
        {"date": t.event_time_raw or "Unknown", "description": t.description}
        for t in timeline_objects
    ]

    contradictions_list = [
        {
            "fact_type": c.fact_type,
            "description": c.description,
            "confidence": float(c.confidence),
            "source_attribution": c.source_attribution,
        }
        for c in contradictions
    ]

    # Re-run synthesis using current system prompt templates
    summary_res = await ai_service.summarize_story_from_kg(
        kg=story.knowledge_graph or {},
        contradictions=contradictions_list,
        timeline=timeline_list,
        source_comparisons=[],
    )

    story.headline = summary_res.headline
    story.one_line_summary = summary_res.one_line_summary
    story.short_summary = summary_res.short_summary
    story.detailed_summary = summary_res.detailed_summary
    story.key_facts = [f for f in summary_res.key_facts if f] if summary_res.key_facts else []

    await session.commit()


replay_service = ReplayService()
