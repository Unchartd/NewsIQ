import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.feedback_agent import evaluate_story_quality
from app.core.config import settings
from app.models.models import (
    Article,
    ArticleEvent,
    Category,
    Source,
    Story,
    StoryContradiction,
    StoryDifference,
    StoryEntity,
    StorySourceCoverage,
    StoryTimelineEvent,
    StoryVersion,
    SynthesisArtifact,
)
from app.models.observability_models import PipelineTraceModel
from app.services.ai_service import AIService, StorySummaryResponse
from app.services.cache_service import cache_service
from app.services.contradiction_service import contradiction_service
from app.services.knowledge_graph import build_story_knowledge_graph
from app.services.pipeline_cache import pipeline_cache
from app.services.source_comparison_service import source_comparison_service

logger = logging.getLogger(__name__)


def _now() -> datetime:
    """Return current UTC time (timezone-naive)."""
    return datetime.now(UTC).replace(tzinfo=None)


class TimelineCompiler:
    """Isolate timeline compilation from DB actions and external LLM/agent flows."""

    @staticmethod
    def compile(article_events: list[ArticleEvent], article_source_map: dict) -> list[dict]:
        """Compile structured timeline entries sorted chronologically."""
        timeline_entries = []
        for evt in article_events:
            t = evt.event_time or evt.created_at or _now()
            if t.tzinfo is not None:
                t = t.astimezone(UTC).replace(tzinfo=None)

            src_name = article_source_map.get(evt.article_id, "Unknown Source")
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
            desc = f"{evt_type} reported by {src_name}{details_str}."

            timeline_entries.append(
                {
                    "event_time": t,
                    "event_time_raw": evt.event_time_raw or t.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "description": desc,
                }
            )

        # Sort chronologically
        timeline_entries.sort(key=lambda x: cast(datetime, x["event_time"]))
        return timeline_entries


def compute_payload_hash(payload: Any) -> str:
    """Generate a SHA-256 hash of a JSON-serializable payload."""
    serialized = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class StorySynthesisOrchestrator:
    """Orchestrates multi-stage news story synthesis with pointer-based artifact storage."""

    def __init__(self, ai_service: AIService | None = None) -> None:
        from app.services.ai_service import ai_service as global_ai_service

        self.ai_service = ai_service or global_ai_service

    async def get_or_create_artifact(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        artifact_type: str,
        payload: Any,
    ) -> uuid.UUID:
        """Fetch or create a deduplicated synthesis artifact based on its content hash."""
        content_hash = compute_payload_hash(payload)

        # Check for existing artifact with same story, type, and hash
        stmt = select(SynthesisArtifact).where(
            SynthesisArtifact.story_id == story_id,
            SynthesisArtifact.artifact_type == artifact_type,
            SynthesisArtifact.content_hash == content_hash,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing.id

        # Insert new artifact
        artifact = SynthesisArtifact(
            id=uuid.uuid4(),
            story_id=story_id,
            artifact_type=artifact_type,
            content_hash=content_hash,
            payload=payload,
            created_at=_now(),
        )
        session.add(artifact)
        await session.flush()
        return artifact.id

    async def check_budget_limit(self, story_id: uuid.UUID) -> bool:
        """Check if the per-story daily synthesis budget ($0.10) has been exceeded in Redis."""
        if not cache_service.is_active:
            return True  # Bypass check if Redis is down

        from datetime import date

        day_str = date.today().isoformat()
        key = f"newsiq:budget:story:{story_id}:{day_str}"

        try:
            val = await cache_service.get_raw(key)
            if val is not None and float(val) >= 0.10:
                logger.warning("Daily synthesis budget ($0.10) exceeded for story %s.", story_id)
                return False
        except Exception as e:
            logger.warning("Failed to check story budget in Redis: %s", e)

        return True

    async def record_cost(self, story_id: uuid.UUID, cost: float) -> None:
        """Increment daily cost for the story in Redis."""
        if not cache_service.is_active or cost <= 0:
            return

        from datetime import date

        day_str = date.today().isoformat()
        key = f"newsiq:budget:story:{story_id}:{day_str}"

        try:
            await cache_service.incr_by_float(key, cost, ttl=86400)
            # Track overall budget through main budget manager too
            from app.services.cost_budget import cost_budget_manager

            await cost_budget_manager.add_story_cost(str(story_id), cost)
        except Exception as e:
            logger.warning("Failed to update story daily cost in Redis: %s", e)

    async def record_trace(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        stage: str,
        started_at: datetime,
        completed_at: datetime,
        cost_usd: float,
        cache_hit: bool,
        model: str | None,
        prompt_version: str | None,
        decision: str | None,
        reason: str | None,
    ) -> None:
        """Save a rich telemetry trace of a stage run to the database."""
        latency_ms = (completed_at - started_at).total_seconds() * 1000.0
        trace = PipelineTraceModel(
            id=uuid.uuid4(),
            story_id=story_id,
            stage=stage,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            cache_hit=cache_hit,
            model=model,
            prompt_version=prompt_version,
            decision=decision,
            reason=reason,
            created_at=completed_at,
        )
        session.add(trace)
        await session.flush()

        # Update Story Metric counters if prometheus is enabled
        try:
            from app.core.metrics import newsiq_story_stages_total

            status = "success" if decision != "error" else "failed"
            newsiq_story_stages_total.labels(stage=stage, status=status).inc()
        except Exception as e:
            # Metrics emission is best-effort and must not interrupt synthesis flow.
            logger.debug("Failed to emit story stage metric for stage '%s': %s", stage, e)

    async def run_knowledge_graph_stage(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        articles: list[Article],
        article_events: list[ArticleEvent],
        story_entities: list[StoryEntity],
        sources_list: list[Source],
    ) -> tuple[uuid.UUID, dict]:
        """Stage 1: Build/fetch Story Knowledge Graph (deterministic/no LLM)."""
        started_at = _now()

        kg = build_story_knowledge_graph(
            articles=articles,
            article_events=article_events,
            story_entities=story_entities,
            sources=sources_list,
        )
        kg_dict = kg.to_dict()

        artifact_id = await self.get_or_create_artifact(
            session=session, story_id=story_id, artifact_type="knowledge_graph", payload=kg_dict
        )

        await self.record_trace(
            session=session,
            story_id=story_id,
            stage="knowledge_graph",
            started_at=started_at,
            completed_at=_now(),
            cost_usd=0.0,
            cache_hit=False,
            model=None,
            prompt_version=None,
            decision="success",
            reason=f"Compiled KG with {len(kg_dict.get('nodes', []))} nodes, {len(kg_dict.get('edges', []))} edges.",
        )
        return artifact_id, kg_dict

    async def run_contradiction_stage(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        story_input_hash: str,
        articles: list[Article],
        article_events: list[ArticleEvent],
        article_source_map: dict,
    ) -> tuple[uuid.UUID, list[dict]]:
        """Stage 2: Hybrid contradiction detection (cached)."""
        started_at = _now()

        from app.services.prompt_registry import prompt_registry

        prompt_tmpl = prompt_registry.get("contradiction_detection")
        model = prompt_tmpl.model if prompt_tmpl else "gemini-2.5-flash-lite"
        prompt_version = prompt_tmpl.version if prompt_tmpl else "1.0.0"

        # Check Cache
        cached_res = await pipeline_cache.get_stage_result(
            stage="contradictions",
            content_hash=story_input_hash,
            model=model,
            prompt_version=prompt_version,
            temperature=0.1,
        )
        cache_hit = False
        if cached_res is not None:
            contras_payload = cached_res
            cache_hit = True
            logger.info("Stage-level cache HIT for contradictions in story %s", story_id)
        else:
            # Call contradiction service (we expunge the database additions to manage state immutably)
            contras = await contradiction_service.detect_and_save_contradictions(
                story_id=story_id,
                session=session,
                articles=articles,
                article_events=article_events,
                article_source_map=article_source_map,
            )

            # Build payload & expunge objects so they don't commit until PublisherStage
            contras_payload = []
            for c in contras:
                contras_payload.append(
                    {
                        "fact_type": c.fact_type,
                        "description": c.description,
                        "confidence": float(c.confidence) if c.confidence else 1.0,
                        "source_attribution": c.source_attribution,
                    }
                )
                session.expunge(c)

            await pipeline_cache.set_stage_result(
                stage="contradictions",
                content_hash=story_input_hash,
                result_data=contras_payload,
                model=model,
                prompt_version=prompt_version,
                temperature=0.1,
            )

        artifact_id = await self.get_or_create_artifact(
            session=session,
            story_id=story_id,
            artifact_type="contradictions",
            payload=contras_payload,
        )

        # Calculate cost
        # (Assuming contradiction_service tracks cost internally or we project cost/token usage)
        cost = (
            0.0 if cache_hit else 0.0001 * len(contras_payload)
        )  # Simple fallback cost projection
        await self.record_cost(story_id, cost)

        await self.record_trace(
            session=session,
            story_id=story_id,
            stage="contradiction_detection",
            started_at=started_at,
            completed_at=_now(),
            cost_usd=cost,
            cache_hit=cache_hit,
            model=model,
            prompt_version=prompt_version,
            decision="success",
            reason=f"Detected {len(contras_payload)} contradictions.",
        )
        return artifact_id, contras_payload

    async def run_source_comparison_stage(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        story_input_hash: str,
        articles: list[Article],
        article_events: list[ArticleEvent],
        article_source_map: dict,
        sources_list: list[Source],
        precomputed_contradictions: list[dict],
    ) -> tuple[uuid.UUID, dict]:
        """Stage 3: Publisher coverage and angle differences (cached)."""
        started_at = _now()
        from app.services.prompt_registry import prompt_registry

        prompt_tmpl = prompt_registry.get("source_comparison")
        model = prompt_tmpl.model if prompt_tmpl else "gemini-2.5-flash-lite"
        prompt_version = prompt_tmpl.version if prompt_tmpl else "1.0.0"

        # Check Cache
        cached_res = await pipeline_cache.get_stage_result(
            stage="source_comparison",
            content_hash=story_input_hash,
            model=model,
            prompt_version=prompt_version,
            temperature=0.1,
        )
        cache_hit = False
        if cached_res is not None:
            payload = cached_res
            cache_hit = True
            logger.info("Stage-level cache HIT for source comparison in story %s", story_id)
        else:
            # Re-materialize contradiction objects temporarily for comparison service signature
            temp_contras = []
            for cp in precomputed_contradictions:
                temp_contras.append(
                    StoryContradiction(
                        story_id=story_id,
                        fact_type=cp["fact_type"],
                        description=cp["description"],
                        confidence=cp["confidence"],
                        source_attribution=cp["source_attribution"],
                    )
                )

            cov_list, diff_list = await source_comparison_service.compare_sources_and_save(
                story_id=story_id,
                session=session,
                articles=articles,
                article_events=article_events,
                article_source_map=article_source_map,
                sources_list=sources_list,
                precomputed_contradictions=temp_contras,
            )

            # Expunge and serialize
            cov_serialized = [
                {"source_id": str(c.source_id), "focus_area": c.focus_area} for c in cov_list
            ]
            diff_serialized = [
                {
                    "source_id": str(d.source_id),
                    "unique_information": d.unique_information,
                    "missing_information": d.missing_information,
                    "contradictions": d.contradictions,
                }
                for d in diff_list
            ]

            for c in cov_list:
                session.expunge(c)
            for d in diff_list:
                session.expunge(d)

            payload = {"coverage": cov_serialized, "differences": diff_serialized}

            await pipeline_cache.set_stage_result(
                stage="source_comparison",
                content_hash=story_input_hash,
                result_data=payload,
                model=model,
                prompt_version=prompt_version,
                temperature=0.1,
            )

        artifact_id = await self.get_or_create_artifact(
            session=session, story_id=story_id, artifact_type="source_comparison", payload=payload
        )

        cost = 0.0 if cache_hit else 0.0015  # Fallback source comparison cost projection
        await self.record_cost(story_id, cost)

        await self.record_trace(
            session=session,
            story_id=story_id,
            stage="source_comparison",
            started_at=started_at,
            completed_at=_now(),
            cost_usd=cost,
            cache_hit=cache_hit,
            model=model,
            prompt_version=prompt_version,
            decision="success",
            reason=f"Compared {len(payload.get('coverage', []))} source focus areas and differences.",
        )
        return artifact_id, payload

    async def run_timeline_stage(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        article_events: list[ArticleEvent],
        article_source_map: dict,
    ) -> tuple[uuid.UUID, list[dict]]:
        """Stage 4: Deterministic timeline creation sorted chronologically."""
        started_at = _now()

        compiled_entries = TimelineCompiler.compile(article_events, article_source_map)
        timeline_entries = [
            {
                "event_time": entry["event_time"].isoformat(),
                "event_time_raw": entry["event_time_raw"],
                "description": entry["description"],
            }
            for entry in compiled_entries
        ]

        artifact_id = await self.get_or_create_artifact(
            session=session, story_id=story_id, artifact_type="timeline", payload=timeline_entries
        )

        await self.record_trace(
            session=session,
            story_id=story_id,
            stage="timeline",
            started_at=started_at,
            completed_at=_now(),
            cost_usd=0.0,
            cache_hit=False,
            model=None,
            prompt_version=None,
            decision="success",
            reason=f"Compiled timeline with {len(timeline_entries)} events.",
        )
        return artifact_id, timeline_entries

    async def run_summary_stage(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        story_input_hash: str,
        kg: dict,
        contradictions: list[dict],
        timeline: list[dict],
        source_comparisons: list[dict],
        corrections: list[str] = None,
        existing_summary_payload: dict = None,
    ) -> tuple[uuid.UUID, dict]:
        """Stage 5: Narrative summarization, supporting section-level regeneration corrections."""
        started_at = _now()

        from app.services.prompt_registry import prompt_registry

        prompt_tmpl = prompt_registry.get("summary_generation")
        model = prompt_tmpl.model if prompt_tmpl else "gemini-2.5-pro"
        prompt_version = prompt_tmpl.version if prompt_tmpl else "1.0.0"

        # Adapt prompt if we are doing targeted section refinement
        if corrections and existing_summary_payload:
            logger.info("Performing section-level refinement for story %s", story_id)

            # Formulate refinement prompt
            refine_prompt = f"""
            You are an expert news editor. Your task is to update/correct an existing story summary based on feedback corrections.
            Please preserve the existing text and only modify/update the affected parts (e.g. key_facts, timeline, short_summary).

            Existing Summary Data:
            {existing_summary_payload}

            Feedback Corrections:
            {corrections}

            Knowledge Graph Ground Truth:
            {kg}

            Respond with ONLY a valid JSON object matching this exact schema:
            {{
              "headline": "<neutral headline>",
              "one_line_summary": "<1-sentence summary>",
              "short_summary": "<1-paragraph summary>",
              "detailed_summary": "<multi-paragraph detailed summary>",
              "key_facts": ["fact1", "fact2", "fact3"],
              "category": "<one of: politics, world, business, technology, sports, entertainment, lifestyle, travel, education, health, science, weather>"
            }}
            """

            from app.ai.gateway import ai_gateway

            response = await ai_gateway.execute_request(
                model=model,
                stage="summary_refinement",
                messages=[{"role": "user", "content": refine_prompt}],
                temperature=0.1,
                story_id=str(story_id),
            )

            summary_dict = json.loads(response.content)
            cache_hit = False
            cost = response.cost_usd or 0.002

        else:
            # Regular cached summarization
            # Check cache
            cached_sum = await pipeline_cache.get_stage_result(
                stage="summary_generation",
                content_hash=story_input_hash,
                model=model,
                prompt_version=prompt_version,
                temperature=0.1,
            )

            if cached_sum is not None:
                summary_dict = cached_sum
                cache_hit = True
                cost = 0.0
            else:
                # Direct summarization call
                summary_res: StorySummaryResponse = await self.ai_service.summarize_story_from_kg(
                    kg=kg,
                    contradictions=contradictions,
                    timeline=timeline,
                    source_comparisons=source_comparisons,
                )
                summary_dict = {
                    "headline": summary_res.headline,
                    "one_line_summary": summary_res.one_line_summary,
                    "short_summary": summary_res.short_summary,
                    "detailed_summary": summary_res.detailed_summary,
                    "key_facts": summary_res.key_facts,
                    "category": summary_res.category,
                }

                await pipeline_cache.set_stage_result(
                    stage="summary_generation",
                    content_hash=story_input_hash,
                    result_data=summary_dict,
                    model=model,
                    prompt_version=prompt_version,
                    temperature=0.1,
                )
                cache_hit = False
                cost = 0.003  # Average cost of Gemini 2.5 Pro summarization

        artifact_id = await self.get_or_create_artifact(
            session=session, story_id=story_id, artifact_type="summary", payload=summary_dict
        )

        await self.record_cost(story_id, cost)
        await self.record_trace(
            session=session,
            story_id=story_id,
            stage="summary_generation",
            started_at=started_at,
            completed_at=_now(),
            cost_usd=cost,
            cache_hit=cache_hit,
            model=model,
            prompt_version=prompt_version,
            decision="success",
            reason="Generated summaries and headline."
            if not corrections
            else "Refined summaries based on QA feedback.",
        )
        return artifact_id, summary_dict

    async def run_publisher_stage(
        self,
        session: AsyncSession,
        story: Story,
        articles: list[Article],
        summary_payload: dict,
        timeline_payload: list[dict],
        contradictions_payload: list[dict],
        source_comp_payload: dict,
        story_version_id: uuid.UUID,
    ) -> None:
        """Stage 7: Atomically map the active artifact payloads into DB tables."""
        started_at = _now()

        # Clear existing tables inside the single transaction
        await session.execute(
            delete(StoryTimelineEvent).where(StoryTimelineEvent.story_id == story.id)
        )
        await session.execute(
            delete(StorySourceCoverage).where(StorySourceCoverage.story_id == story.id)
        )
        await session.execute(delete(StoryDifference).where(StoryDifference.story_id == story.id))
        await session.execute(
            delete(StoryContradiction).where(StoryContradiction.story_id == story.id)
        )
        await session.flush()

        # 1. Update Story fields
        story.headline = summary_payload.get("headline", story.headline)
        story.one_line_summary = summary_payload.get("one_line_summary", story.one_line_summary)
        story.short_summary = summary_payload.get("short_summary", story.short_summary)
        story.detailed_summary = summary_payload.get("detailed_summary", story.detailed_summary)
        story.key_facts = summary_payload.get("key_facts", story.key_facts)
        story.current_version_id = story_version_id

        # Update category if matching Category exists in DB
        cat_slug = summary_payload.get("category", "world")
        cat_stmt = select(Category).where(Category.slug == cat_slug)
        cat_res = await session.execute(cat_stmt)
        cat_obj = cat_res.scalar_one_or_none()
        if cat_obj:
            story.category_id = cat_obj.id

        # 2. Populate StoryTimelineEvent table
        for entry in timeline_payload:
            t = datetime.fromisoformat(entry["event_time"])
            tl_event = StoryTimelineEvent(
                id=uuid.uuid4(),
                story_id=story.id,
                event_time=t,
                event_time_raw=entry["event_time_raw"],
                description=entry["description"],
                created_at=_now(),
            )
            session.add(tl_event)

        # 3. Populate StoryContradiction table
        for entry in contradictions_payload:
            contra = StoryContradiction(
                id=uuid.uuid4(),
                story_id=story.id,
                fact_type=entry["fact_type"],
                description=entry["description"],
                confidence=entry["confidence"],
                source_attribution=entry["source_attribution"],
            )
            session.add(contra)

        # 4. Populate StorySourceCoverage & Differences tables
        for cov_entry in source_comp_payload.get("coverage", []):
            cov = StorySourceCoverage(
                id=uuid.uuid4(),
                story_id=story.id,
                source_id=uuid.UUID(cov_entry["source_id"]),
                focus_area=cov_entry["focus_area"],
                created_at=_now(),
            )
            session.add(cov)

        for diff_entry in source_comp_payload.get("differences", []):
            diff = StoryDifference(
                id=uuid.uuid4(),
                story_id=story.id,
                source_id=uuid.UUID(diff_entry["source_id"]),
                unique_information=diff_entry["unique_information"],
                missing_information=diff_entry["missing_information"],
                contradictions=diff_entry["contradictions"],
                created_at=_now(),
            )
            session.add(diff)

        story.story_status = "active"
        await session.flush()

        await self.record_trace(
            session=session,
            story_id=story.id,
            stage="publisher",
            started_at=started_at,
            completed_at=_now(),
            cost_usd=0.0,
            cache_hit=False,
            model=None,
            prompt_version=None,
            decision="publish",
            reason=f"Successfully promoted and published StoryVersion {story_version_id}",
        )

    async def synthesize_story(
        self,
        session: AsyncSession,
        story_id: uuid.UUID,
        trigger: str = "new_article",
        articles_override: list[Article] = None,
        story_override: Story = None,
    ) -> None:
        """Coordinates multi-stage story synthesis inside database transaction context."""

        # 0. Check daily budget gate
        budget_ok = await self.check_budget_limit(story_id)
        if not budget_ok:
            # Skip and log trace
            await self.record_trace(
                session=session,
                story_id=story_id,
                stage="synthesis_orchestrator",
                started_at=_now(),
                completed_at=_now(),
                cost_usd=0.0,
                cache_hit=False,
                model=None,
                prompt_version=None,
                decision="skip",
                reason="Daily synthesis budget threshold exceeded.",
            )
            return

        # Fetch active story and articles
        if story_override is not None:
            story = story_override
        else:
            story_stmt = select(Story).where(Story.id == story_id)
            story_res = await session.execute(story_stmt)
            story = story_res.scalar_one_or_none()

        if not story:
            logger.error("Story %s not found for synthesis.", story_id)
            return

        # Use overrides or load from story association
        if articles_override is not None:
            articles = articles_override
        else:
            # Load active articles
            from app.models.models import StoryArticle

            stmt = select(Article).join(StoryArticle).where(StoryArticle.story_id == story_id)
            art_res = await session.execute(stmt)
            articles = list(art_res.scalars().all())

        if not articles:
            logger.warning("No articles associated with story %s. Skipping synthesis.", story_id)
            return

        # Precompute input hash for the article cluster to detect skips/caching
        article_inputs = [f"{art.id}:{art.title or ''}:{art.description or ''}" for art in articles]
        article_inputs.sort()
        story_input_hash = pipeline_cache.composite_hash(*article_inputs)

        # ── Incremental Updates Guard ──
        guard_key = f"story_synthesis_hash:{story.id}"
        is_guard_hit = False
        if story.headline:
            try:
                existing_hash = await cache_service.get_raw(guard_key)
                if existing_hash == story_input_hash:
                    is_guard_hit = True
            except Exception as e:
                logger.warning("Failed to check updates guard: %s", e)

        if is_guard_hit and trigger not in ("manual_regenerate", "replay", "admin_override"):
            logger.info("Incremental updates guard hit. Skipping synthesis for story %s.", story_id)
            return

        # Gather supporting models
        article_ids = [art.id for art in articles]
        evt_stmt = select(ArticleEvent).where(ArticleEvent.article_id.in_(article_ids))
        evt_res = await session.execute(evt_stmt)
        article_events = list(evt_res.scalars().all())

        entity_stmt = select(StoryEntity).where(StoryEntity.story_id == story_id)
        ent_res = await session.execute(entity_stmt)
        story_entities = list(ent_res.scalars().all())

        # Collect distinct sources and names
        source_ids = list({art.source_id for art in articles if art.source_id is not None})
        if source_ids:
            src_res = await session.execute(select(Source).where(Source.id.in_(source_ids)))
            sources_list = list(src_res.scalars().all())
            source_by_id = {src.id: src for src in sources_list}
        else:
            sources_list = []
            source_by_id = {}

        article_source_map = {}
        for art in articles:
            src = source_by_id.get(art.source_id)
            article_source_map[art.id] = src.name if src else "Unknown Source"

        category_slug = story.category.slug if story.category else "world"

        # ── multi-stage execution pipeline ──
        # Stage 1: KG Construction
        kg_artifact_id, kg_dict = await self.run_knowledge_graph_stage(
            session, story_id, articles, article_events, story_entities, sources_list
        )

        # Stage 2: Contradiction Detection
        contras_artifact_id, contras_payload = await self.run_contradiction_stage(
            session, story_id, story_input_hash, articles, article_events, article_source_map
        )

        # Stage 3: Source Comparison
        source_comp_artifact_id, source_comp_payload = await self.run_source_comparison_stage(
            session,
            story_id,
            story_input_hash,
            articles,
            article_events,
            article_source_map,
            sources_list,
            contras_payload,
        )

        # Stage 4: Timeline
        timeline_artifact_id, timeline_payload = await self.run_timeline_stage(
            session, story_id, article_events, article_source_map
        )

        # Stage 5: Summary Generation (First Pass)
        summary_artifact_id, summary_payload = await self.run_summary_stage(
            session,
            story_id,
            story_input_hash,
            kg_dict,
            contras_payload,
            timeline_payload,
            source_comp_payload.get("differences", []),
        )

        # Stage 6: Quality check & Feedback loop
        # We start with regeneration_count = 0
        regeneration_count = 0
        summary_text = f"Headline: {summary_payload.get('headline')}\nSummaries: {summary_payload.get('one_line_summary')} - {summary_payload.get('short_summary')}\nKey facts: {summary_payload.get('key_facts')}"

        feedback_report = await evaluate_story_quality(
            story=story,
            articles=articles,
            kg=kg_dict,
            contradictions=contras_payload,
            timeline=timeline_payload,
            summary_text=summary_text,
            category_slug=category_slug,
            regeneration_count=regeneration_count,
        )

        # If action requires regeneration, re-execute SummaryStage once with corrections
        if feedback_report.action == "regenerate_summary":
            regeneration_count += 1
            logger.info(
                "FeedbackAgent requested summary regeneration. Corrections: %s",
                feedback_report.targeted_corrections,
            )

            # Rerun Stage 5 summary with section-level corrections
            summary_artifact_id, summary_payload = await self.run_summary_stage(
                session=session,
                story_id=story_id,
                story_input_hash=story_input_hash,
                kg=kg_dict,
                contradictions=contras_payload,
                timeline=timeline_payload,
                source_comparisons=source_comp_payload.get("differences", []),
                corrections=feedback_report.targeted_corrections,
                existing_summary_payload=summary_payload,
            )

            # Re-evaluate
            summary_text = f"Headline: {summary_payload.get('headline')}\nSummaries: {summary_payload.get('one_line_summary')} - {summary_payload.get('short_summary')}\nKey facts: {summary_payload.get('key_facts')}"
            feedback_report = await evaluate_story_quality(
                story=story,
                articles=articles,
                kg=kg_dict,
                contradictions=contras_payload,
                timeline=timeline_payload,
                summary_text=summary_text,
                category_slug=category_slug,
                regeneration_count=regeneration_count,
            )

        # Retrieve next version number
        ver_stmt = (
            select(text("COALESCE(MAX(version_number), 0) + 1"))
            .select_from(text("story_versions"))
            .where(text("story_id = :sid"))
            .params(sid=story_id)
        )
        ver_res = await session.execute(ver_stmt)
        next_ver = ver_res.scalar() or 1

        # Fetch costs trace summary
        trace_stmt = (
            select(text("COALESCE(SUM(cost_usd), 0.0)"))
            .select_from(text("pipeline_traces"))
            .where(text("story_id = :sid"))
            .params(sid=story_id)
        )
        trace_res = await session.execute(trace_stmt)
        accumulated_cost = float(trace_res.scalar() or 0.0)

        # Create StoryVersion snapshot referencing the artifacts
        story_version = StoryVersion(
            id=uuid.uuid4(),
            story_id=story_id,
            version_number=next_ver,
            pipeline_version=getattr(settings, "PIPELINE_VERSION", "1.0.0"),
            summary_artifact_id=summary_artifact_id,
            timeline_artifact_id=timeline_artifact_id,
            kg_artifact_id=kg_artifact_id,
            source_comparison_artifact_id=source_comp_artifact_id,
            contradiction_artifact_id=contras_artifact_id,
            llm_cost_usd=accumulated_cost,
            trigger=trigger,
            created_at=_now(),
        )
        session.add(story_version)
        await session.flush()

        # Record decision trace for version creation
        await self.record_trace(
            session=session,
            story_id=story_id,
            stage="feedback_agent",
            started_at=_now(),
            completed_at=_now(),
            cost_usd=0.0,
            cache_hit=False,
            model=None,
            prompt_version=None,
            decision=feedback_report.action,
            reason=f"Version {next_ver} review completed. Explanation: {feedback_report.explanation}",
        )

        # If publishable, run stage 7: Publisher
        if feedback_report.action in ("publish", "regenerate_summary"):
            await self.run_publisher_stage(
                session=session,
                story=story,
                articles=articles,
                summary_payload=summary_payload,
                timeline_payload=timeline_payload,
                contradictions_payload=contras_payload,
                source_comp_payload=source_comp_payload,
                story_version_id=story_version.id,
            )
        else:
            # Mark story review status as failed or pending review
            story.story_status = "failed"
            logger.info(
                "Story %s was not published. Status: %s. Action: %s.",
                story_id,
                story.story_status,
                feedback_report.action,
            )

        # Update guard hash
        try:
            await cache_service.set_raw(guard_key, story_input_hash, ttl=604800)
        except Exception as e:
            logger.warning("Failed to update guard key in Redis: %s", e)


story_synthesis_orchestrator = StorySynthesisOrchestrator()
