"""Distributed tracing primitives for the NewsIQ pipeline.

Provides run_id, trace_id, and span_id propagation using contextvars,
which works across async code and Celery prefork workers.

Usage:
    async with PipelineRun(trigger="celery_beat") as run:
        async with StageSpan(run, stage="ingestion") as span:
            # ... do work ...
            span.set_metadata({"articles_count": 5})

Every log, metric, and DB record created within these contexts
automatically inherits the trace context via structlog bindings.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import select

from app.core.langfuse_client import langfuse_client

logger = logging.getLogger(__name__)

# ── Context Variables ─────────────────────────────────────────────────────────
# These propagate trace IDs across async boundaries and Celery workers.

run_id_ctx: ContextVar[str] = ContextVar("run_id", default="")
trace_id_ctx: ContextVar[str] = ContextVar("trace_id", default="")
span_id_ctx: ContextVar[str] = ContextVar("span_id", default="")
stage_ctx: ContextVar[str] = ContextVar("stage", default="")
story_id_ctx: ContextVar[str] = ContextVar("story_id", default="")
article_id_ctx: ContextVar[str] = ContextVar("article_id", default="")
active_pipeline_run_ctx: ContextVar[PipelineRun | None] = ContextVar(
    "active_pipeline_run", default=None
)
sequence_number_ctx: ContextVar[int] = ContextVar("sequence_number", default=0)
parent_llm_trace_id_ctx: ContextVar[str] = ContextVar("parent_llm_trace_id", default="")


def get_next_sequence_number() -> int:
    """Increment and return the sequence number for this execution context."""
    seq = sequence_number_ctx.get(0) + 1
    sequence_number_ctx.set(seq)
    return seq


async def emit_pipeline_event(event: dict[str, Any]) -> None:
    """Publish an observability event to a Redis Stream."""
    import json

    import redis.asyncio as aioredis

    from app.core.config import settings

    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.xadd("newsiq:pipeline:stream", {"event": json.dumps(event, default=str)})
        await r.aclose()
    except Exception as exc:
        logger.warning("Failed to emit pipeline event: %s", exc)


def save_artifact(
    name: str, payload: Any, tier: int, run_id: str, span_id: str, success: bool = True
) -> str | None:
    """Save an execution artifact to disk according to tiered policies.

    Tiers:
      - Tier 1 (Always Save): Similarity matrices, final prompts, final responses.
      - Tier 2 (Save on Failure Only): HTML, Markdown, Intermediate JSON.
      - Tier 3 (Never Save): Embeddings, large vectors, temporary buffers.
    """
    if tier == 3:
        return None

    if tier == 2 and success:
        return None

    import json
    import os

    from app.core.config import settings

    try:
        # Create artifacts directory
        artifacts_dir = os.path.join(
            settings.LOCAL_STORAGE_PATH, "observability_artifacts", run_id, span_id
        )
        os.makedirs(artifacts_dir, exist_ok=True)

        filename = f"{name}.json" if not isinstance(payload, (str, bytes)) else f"{name}.txt"
        file_path = os.path.join(artifacts_dir, filename)

        if isinstance(payload, bytes):
            with open(file_path, "wb") as f:
                f.write(payload)
        elif isinstance(payload, str):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(payload)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, default=str)

        # Return local path relative to storage root
        return os.path.relpath(file_path, settings.LOCAL_STORAGE_PATH).replace("\\", "/")
    except Exception as e:
        logger.warning("Failed to save artifact %s: %s", name, e)
        return None


def _to_uuid(val: Any) -> uuid.UUID | None:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except ValueError:
        return None


class StageStatus(StrEnum):
    """Status of a pipeline stage execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class PipelineStage(StrEnum):
    """Canonical pipeline stage names."""

    INGESTION_RSS = "ingestion_rss"
    INGESTION_GNEWS = "ingestion_gnews"
    DISCOVERY_SEARCH = "discovery_search"
    CRAWLING = "crawling"
    DEDUPLICATION = "deduplication"
    EMBEDDING = "embedding"
    EVENT_EXTRACTION = "event_extraction"
    ENTITY_EXTRACTION = "entity_extraction"
    ENTITY_LINKING = "entity_linking"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    CLUSTERING_INCREMENTAL = "clustering_incremental"
    CLUSTERING_BATCH = "clustering_batch"
    CONTRADICTION_DETECTION = "contradiction_detection"
    SOURCE_COMPARISON = "source_comparison"
    TIMELINE_GENERATION = "timeline_generation"
    SUMMARY_GENERATION = "summary_generation"
    DIFFERENCE_ENGINE = "difference_engine"
    INDEXING = "indexing"
    CACHE_INVALIDATION = "cache_invalidation"

    # Orchestration and Lifecycle Stages
    SYNTHESIS_ORCHESTRATOR = "synthesis_orchestrator"
    PUBLISHER = "publisher"
    FEEDBACK_AGENT = "feedback_agent"


# ── Trace Context Snapshot ────────────────────────────────────────────────────


def get_trace_context() -> dict[str, str]:
    """Return a snapshot of the current trace context for log binding."""
    return {
        "run_id": run_id_ctx.get(""),
        "trace_id": trace_id_ctx.get(""),
        "span_id": span_id_ctx.get(""),
        "stage": stage_ctx.get(""),
        "story_id": story_id_ctx.get(""),
        "article_id": article_id_ctx.get(""),
    }


def bind_story_context(story_id: str) -> None:
    """Bind a story_id to the current trace context."""
    story_id_ctx.set(str(story_id))


def bind_article_context(article_id: str) -> None:
    """Bind an article_id to the current trace context."""
    article_id_ctx.set(str(article_id))


# ── Span Data ─────────────────────────────────────────────────────────────────


@dataclass
class SpanData:
    """Captured data from a completed stage span."""

    span_id: str
    run_id: str
    trace_id: str
    stage: str
    status: StageStatus
    started_at: datetime
    completed_at: datetime | None = None
    latency_ms: float = 0.0
    retry_count: int = 0
    error: str | None = None
    error_type: str | None = None
    error_traceback: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    story_id: str | None = None
    article_id: str | None = None


# ── PipelineRun Context Manager ──────────────────────────────────────────────


class PipelineRun:
    """Top-level context for a pipeline execution (batch or incremental).

    Generates a unique run_id and trace_id, sets them in contextvars,
    and persists the PipelineRun record to the database on exit.
    """

    def __init__(
        self,
        trigger: str = "manual",
        pipeline_type: str = "batch",
        parent_run_id: str | None = None,
        is_replay: bool = False,
        run_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.id = run_id or str(uuid.uuid4())
        self.trace_id = trace_id or str(uuid.uuid4())
        self.trigger = trigger
        self.pipeline_type = pipeline_type
        self.parent_run_id = parent_run_id
        self.is_replay = is_replay
        self.started_at = datetime.now(UTC).replace(tzinfo=None)
        self.completed_at: datetime | None = None
        self.status = StageStatus.PENDING
        self.stages: list[SpanData] = []
        self.error: str | None = None
        self._tokens: dict[str, int] = {}
        self._run_id_token: Any = None
        self._trace_id_token: Any = None
        self._active_run_token: Any = None

    async def __aenter__(self) -> PipelineRun:
        self._run_id_token = run_id_ctx.set(self.id)
        self._trace_id_token = trace_id_ctx.set(self.trace_id)
        self._active_run_token = active_pipeline_run_ctx.set(self)
        self.status = StageStatus.RUNNING

        # Create Langfuse trace
        try:
            langfuse_client.trace(
                name=f"pipeline:{self.pipeline_type}",
                id=self.trace_id,
                metadata={
                    "trigger": self.trigger,
                    "pipeline_type": self.pipeline_type,
                    "is_replay": self.is_replay,
                    "parent_run_id": self.parent_run_id,
                },
            )
        except Exception:
            pass

        # Persist initial status (running)
        try:
            await self._persist()
        except Exception:
            pass

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.completed_at = datetime.now(UTC).replace(tzinfo=None)
        if exc_type:
            self.status = StageStatus.FAILED
            self.error = str(exc_val)
        else:
            self.status = StageStatus.SUCCESS

        # Reset context vars
        if self._run_id_token:
            run_id_ctx.reset(self._run_id_token)
        if self._trace_id_token:
            trace_id_ctx.reset(self._trace_id_token)
        if self._active_run_token:
            active_pipeline_run_ctx.reset(self._active_run_token)

        # Persist the final run status asynchronously
        try:
            await self._persist()
        except Exception:
            pass  # Non-fatal — don't break the pipeline

        return False  # Don't suppress exceptions

    def _get_git_sha(self) -> str:
        import subprocess

        try:
            return (
                subprocess.check_output(["git", "rev-parse", "--short", "HEAD"])
                .decode("utf-8")
                .strip()
            )
        except Exception:
            return "unknown"

    def _get_alembic_revision(self) -> str:
        import os

        try:
            # Check directory relative to current cwd or project layout
            for path in ["alembic/versions", "apps/api/alembic/versions"]:
                if os.path.exists(path):
                    files = [
                        f for f in os.listdir(path) if f.endswith(".py") and not f.startswith("__")
                    ]
                    if files:
                        files.sort(key=lambda x: os.path.getmtime(os.path.join(path, x)))
                        return files[-1].split("_")[0]
            return "unknown"
        except Exception:
            return "unknown"

    async def _persist(self) -> None:
        """Persist/Upsert the PipelineRun and all StageRuns to the database."""
        import os

        from app.core.config import settings
        from app.core.database import async_session_factory
        from app.models.observability_models import PipelineRunModel, StageRunModel

        async with async_session_factory() as session:
            stmt = select(PipelineRunModel).where(PipelineRunModel.id == _to_uuid(self.id))
            res = await session.execute(stmt)
            run = res.scalar_one_or_none()

            if not run:
                env_metadata = {
                    "versions": {
                        "git_sha": self._get_git_sha(),
                        "docker_image": os.environ.get("DOCKER_IMAGE_NAME", "newsiq-api:latest"),
                        "alembic_revision": self._get_alembic_revision(),
                        "config_version": settings.APP_VERSION,
                    }
                }
                run = PipelineRunModel(
                    id=_to_uuid(self.id),
                    trace_id=_to_uuid(self.trace_id),
                    trigger=self.trigger,
                    pipeline_type=self.pipeline_type,
                    parent_run_id=_to_uuid(self.parent_run_id),
                    is_replay=self.is_replay,
                    status=self.status.value,
                    started_at=self.started_at,
                    completed_at=self.completed_at,
                    total_latency_ms=(
                        (self.completed_at - self.started_at).total_seconds() * 1000
                        if self.completed_at
                        else 0
                    ),
                    error=self.error,
                    metadata_payload=env_metadata,
                )
                session.add(run)
            else:
                run.status = self.status.value
                run.completed_at = self.completed_at
                if self.completed_at:
                    run.total_latency_ms = (
                        self.completed_at - self.started_at
                    ).total_seconds() * 1000
                run.error = self.error

            for span in self.stages:
                stage_stmt = select(StageRunModel).where(StageRunModel.id == _to_uuid(span.span_id))
                stage_res = await session.execute(stage_stmt)
                stage_run = stage_res.scalar_one_or_none()

                if not stage_run:
                    stage_run = StageRunModel(
                        id=_to_uuid(span.span_id),
                        run_id=_to_uuid(span.run_id),
                        trace_id=_to_uuid(span.trace_id),
                        stage=span.stage,
                        status=span.status.value,
                        started_at=span.started_at,
                        completed_at=span.completed_at,
                        latency_ms=span.latency_ms,
                        retry_count=span.retry_count,
                        error=span.error,
                        error_type=span.error_type,
                        story_id=_to_uuid(span.story_id),
                        article_id=_to_uuid(span.article_id),
                        metadata_payload=span.metadata,
                    )
                    session.add(stage_run)
                else:
                    stage_run.status = span.status.value
                    stage_run.completed_at = span.completed_at
                    stage_run.latency_ms = span.latency_ms
                    stage_run.retry_count = span.retry_count
                    stage_run.error = span.error
                    stage_run.error_type = span.error_type
                    stage_run.metadata_payload = span.metadata

            await session.commit()

            if settings.OTEL_EXPORTER_ENABLED:
                try:
                    from app.workers.tasks import export_run_to_otel_task

                    export_run_to_otel_task.delay(run_id=str(self.id))
                except Exception as e:
                    logger.debug(f"Failed to dispatch OTel export Celery task: {e}")


async def publish_pipeline_event(data: dict[str, Any]) -> None:
    """Broadcast pipeline status transitions to Redis using Streams."""
    await emit_pipeline_event(data)


# ── StageSpan Context Manager ────────────────────────────────────────────────


class StageSpan:
    """Context manager for a single pipeline stage within a PipelineRun.

    Tracks timing, status, errors, retries, and metadata.
    Automatically sets span_id and stage in contextvars.
    """

    def __init__(
        self,
        pipeline_run: PipelineRun | None = None,
        stage: str | PipelineStage = "",
        story_id: str | None = None,
        article_id: str | None = None,
    ) -> None:
        self.span_id = str(uuid.uuid4())

        # Look up active run if not explicitly provided
        if pipeline_run is None:
            pipeline_run = active_pipeline_run_ctx.get(None)
        if pipeline_run is None:
            # Create a fallback/orphan run so we have trace IDs
            pipeline_run = PipelineRun(trigger="orphan", pipeline_type="incremental")

        self.pipeline_run = pipeline_run
        self.stage = stage.value if isinstance(stage, PipelineStage) else stage
        self.story_id = story_id
        self.article_id = article_id
        self.status = StageStatus.PENDING
        self.started_at = datetime.now(UTC).replace(tzinfo=None)
        self.completed_at: datetime | None = None
        self.latency_ms: float = 0.0
        self.retry_count: int = 0
        self.error: str | None = None
        self.error_type: str | None = None
        self.error_traceback: str | None = None
        self.metadata: dict[str, Any] = {}
        self._start_time: float = 0.0
        self._span_token: Any = None
        self._stage_token: Any = None
        self._story_token: Any = None
        self._article_token: Any = None
        self.input_payload: dict[str, Any] | None = None
        self.output_payload: dict[str, Any] | None = None

    def set_input_payload(self, payload: dict[str, Any]) -> None:
        """Set the raw input payload for failure replay observability."""
        self.input_payload = payload

    def set_output_payload(self, payload: dict[str, Any]) -> None:
        """Set the raw output payload for failure replay observability."""
        self.output_payload = payload

    async def __aenter__(self) -> StageSpan:
        self._span_token = span_id_ctx.set(self.span_id)
        self._stage_token = stage_ctx.set(self.stage)
        if self.story_id:
            self._story_token = story_id_ctx.set(self.story_id)
        if self.article_id:
            self._article_token = article_id_ctx.set(self.article_id)
        self.status = StageStatus.RUNNING
        self._start_time = time.perf_counter()

        # Create Langfuse span
        try:
            self.lf_span = langfuse_client.span(
                trace_id=self.pipeline_run.trace_id,
                name=self.stage,
                id=self.span_id,
                metadata={
                    "story_id": self.story_id,
                    "article_id": self.article_id,
                },
            )
        except Exception:
            self.lf_span = None

        # Publish start event to Redis
        try:
            await publish_pipeline_event(
                {
                    "run_id": self.pipeline_run.id,
                    "trace_id": self.pipeline_run.trace_id,
                    "stage": self.stage,
                    "status": "running",
                    "started_at": self.started_at.isoformat() if self.started_at else None,
                }
            )
        except Exception:
            pass

        # Persist stage run status in DB
        try:
            await self._persist_db_status()
        except Exception:
            pass

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        elapsed = time.perf_counter() - self._start_time
        self.latency_ms = round(elapsed * 1000, 2)
        self.completed_at = datetime.now(UTC).replace(tzinfo=None)

        if exc_type:
            self.status = StageStatus.FAILED
            self.error = str(exc_val)
            self.error_type = exc_type.__name__
            self.error_traceback = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            self.metadata["error_traceback"] = self.error_traceback

            # Record Pipeline Failure
            try:
                from app.core.failure_recorder import record_pipeline_failure

                provider = self.metadata.get("provider")
                model = self.metadata.get("model")
                await record_pipeline_failure(
                    stage=self.stage,
                    exception=exc_val,
                    trace_id=_to_uuid(self.pipeline_run.trace_id) if self.pipeline_run else None,
                    run_id=_to_uuid(self.pipeline_run.id) if self.pipeline_run else None,
                    story_id=_to_uuid(self.story_id),
                    article_id=_to_uuid(self.article_id),
                    provider=provider,
                    model=model,
                    input_payload=self.input_payload,
                    output_payload=self.output_payload,
                    retry_count=self.retry_count,
                    latency=self.latency_ms / 1000.0,
                )
            except Exception as rec_err:
                logger.error("Failed to record stage failure in pipeline_failures: %s", rec_err)
        else:
            if self.status == StageStatus.RUNNING:
                self.status = StageStatus.SUCCESS

        # Record Prometheus metrics
        try:
            from app.core.metrics import newsiq_failure_rate, newsiq_latency_seconds

            newsiq_latency_seconds.labels(stage=self.stage).observe(elapsed)
            if exc_type:
                newsiq_failure_rate.labels(stage=self.stage, error_type=self.error_type).inc()
        except Exception:
            pass

        # End Langfuse span
        if getattr(self, "lf_span", None):
            try:
                self.lf_span.end(
                    level="ERROR" if self.status == StageStatus.FAILED else "DEFAULT",
                    status_message=self.error,
                    metadata=self.metadata,
                )
            except Exception:
                pass

        # Publish complete event to Redis
        try:
            await publish_pipeline_event(
                {
                    "run_id": self.pipeline_run.id,
                    "trace_id": self.pipeline_run.trace_id,
                    "stage": self.stage,
                    "status": self.status.value,
                    "latency_ms": self.latency_ms,
                    "error": self.error,
                    "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                }
            )
        except Exception:
            pass

        # Create SpanData and register with pipeline run
        span_data = SpanData(
            span_id=self.span_id,
            run_id=self.pipeline_run.id,
            trace_id=self.pipeline_run.trace_id,
            stage=self.stage,
            status=self.status,
            started_at=self.started_at,
            completed_at=self.completed_at,
            latency_ms=self.latency_ms,
            retry_count=self.retry_count,
            error=self.error,
            error_type=self.error_type,
            error_traceback=self.error_traceback,
            metadata=self.metadata,
            story_id=self.story_id or story_id_ctx.get(""),
            article_id=self.article_id or article_id_ctx.get(""),
        )
        self.pipeline_run.stages.append(span_data)

        # Persist stage run status in DB
        try:
            await self._persist_db_status()
        except Exception:
            pass

        # Reset context vars
        if self._span_token:
            span_id_ctx.reset(self._span_token)
        if self._stage_token:
            stage_ctx.reset(self._stage_token)
        if self._story_token:
            story_id_ctx.reset(self._story_token)
        if self._article_token:
            article_id_ctx.reset(self._article_token)

        return False  # Don't suppress exceptions

    async def _persist_db_status(self) -> None:
        """Persist/update this stage run record in the database."""
        # Ensure the pipeline run parent is in DB
        if self.pipeline_run:
            try:
                await self.pipeline_run._persist()
            except Exception:
                pass

        from app.core.database import async_session_factory
        from app.models.observability_models import StageRunModel

        async with async_session_factory() as session:
            stmt = select(StageRunModel).where(StageRunModel.id == _to_uuid(self.span_id))
            res = await session.execute(stmt)
            stage_run = res.scalar_one_or_none()

            if not stage_run:
                stage_run = StageRunModel(
                    id=_to_uuid(self.span_id),
                    run_id=_to_uuid(self.pipeline_run.id) if self.pipeline_run else None,
                    trace_id=_to_uuid(self.pipeline_run.trace_id) if self.pipeline_run else None,
                    stage=self.stage,
                    status=self.status.value,
                    started_at=self.started_at,
                    completed_at=self.completed_at,
                    latency_ms=self.latency_ms,
                    retry_count=self.retry_count,
                    error=self.error,
                    error_type=self.error_type,
                    story_id=_to_uuid(self.story_id or story_id_ctx.get("")),
                    article_id=_to_uuid(self.article_id or article_id_ctx.get("")),
                    metadata_payload=self.metadata,
                )
                session.add(stage_run)
            else:
                stage_run.status = self.status.value
                stage_run.completed_at = self.completed_at
                stage_run.latency_ms = self.latency_ms
                stage_run.retry_count = self.retry_count
                stage_run.error = self.error
                stage_run.error_type = self.error_type
                stage_run.metadata_payload = self.metadata

            await session.commit()

    def set_metadata(self, data: dict[str, Any]) -> None:
        """Add metadata to this span (e.g., articles_count, model_used)."""
        self.metadata.update(data)

    def increment_retry(self) -> None:
        """Record a retry attempt."""
        self.retry_count += 1

    def mark_skipped(self) -> None:
        """Mark this stage as skipped (e.g., no pending articles)."""
        self.status = StageStatus.SKIPPED


# ── Pipeline Trace Collector & Stage Trace ───────────────────────────────────


def _get_system_resources() -> dict[str, float]:
    res = {"cpu_percent": 0.0, "memory_mb": 0.0}
    try:
        import psutil

        res["cpu_percent"] = psutil.cpu_percent()
        res["memory_mb"] = psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    return res


def _get_db_pool_status() -> int:
    try:
        from app.core.database import engine

        pool = engine.pool
        if hasattr(pool, "checkedout") and callable(pool.checkedout):
            return int(pool.checkedout())
        return 0
    except Exception:
        return 0


async def _get_redis_status() -> int:
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        r = aioredis.from_url(settings.REDIS_URL)
        info = await r.info("clients")
        clients = int(info.get("connected_clients", 0))
        await r.aclose()
        return clients
    except Exception:
        return 0


class StageTrace:
    """OTel-aligned context manager for tracking metrics, lineage, resources, and artifacts in a stage."""

    def __init__(
        self, stage_name: str, story_id: str | None = None, article_id: str | None = None
    ) -> None:
        self.stage = stage_name
        self.span_id = str(uuid.uuid4())
        self.run_id = run_id_ctx.get("")
        self.trace_id = trace_id_ctx.get("")
        self.story_id = story_id or story_id_ctx.get("")
        self.article_id = article_id or article_id_ctx.get("")

        if not self.run_id:
            self.run_id = str(uuid.uuid4())
            self.trace_id = str(uuid.uuid4())

        self.status = "RUNNING"
        self.started_at = datetime.now(UTC).replace(tzinfo=None)
        self.completed_at: datetime | None = None
        self.latency_ms: float = 0.0
        self.retry_count: int = 0
        self.errors: list[Any] = []
        self.warnings: list[str] = []
        self.metrics_data: dict[str, Any] = {}
        self.input_data: dict[str, Any] = {}
        self.output_data: dict[str, Any] = {}
        self.artifacts_data: dict[str, Any] = {}
        self.lineage_data: list[Any] = []
        self.resources_start: dict[str, Any] = {}
        self.resources_end: dict[str, Any] = {}
        self.resources_history: list[Any] = []
        self.metadata: dict[str, Any] = {}
        self._sampling_task: asyncio.Task[None] | None = None
        self._start_time: float = 0.0
        self._span_token: Token[str] | None = None
        self._stage_token: Token[str] | None = None

    async def _resource_sampling_loop(self, interval_seconds: float = 5.0) -> None:
        import asyncio

        try:
            while self.status == "RUNNING":
                await asyncio.sleep(interval_seconds)
                if self.status != "RUNNING":
                    break
                sample: dict[str, Any] = _get_system_resources()
                sample["db_connections"] = _get_db_pool_status()
                sample["redis_clients"] = await _get_redis_status()
                sample["timestamp"] = datetime.now(UTC).replace(tzinfo=None).isoformat()
                self.resources_history.append(sample)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def __aenter__(self) -> StageTrace:
        self._start_time = time.perf_counter()
        self._span_token = span_id_ctx.set(self.span_id)
        self._stage_token = stage_ctx.set(self.stage)

        # Profile resource start snapshot
        self.resources_start = _get_system_resources()
        self.resources_start["db_connections"] = _get_db_pool_status()
        self.resources_start["redis_clients"] = await _get_redis_status()

        # Start background resource sampling loop
        import asyncio

        self._sampling_task = asyncio.create_task(self._resource_sampling_loop(5.0))

        # Emit StageStarted event
        await self._emit_event("StageStarted")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.completed_at = datetime.now(UTC).replace(tzinfo=None)
        self.latency_ms = round((time.perf_counter() - self._start_time) * 1000, 2)

        # Stop resource sampling loop
        if self._sampling_task:
            self._sampling_task.cancel()
            try:
                await self._sampling_task
            except BaseException:
                pass

        # Reset context variables
        if self._span_token is not None:
            span_id_ctx.reset(self._span_token)
        if self._stage_token is not None:
            stage_ctx.reset(self._stage_token)

        # Profile resource end snapshot
        self.resources_end = _get_system_resources()
        self.resources_end["db_connections"] = _get_db_pool_status()
        self.resources_end["redis_clients"] = await _get_redis_status()

        if self.resources_history:
            self.metadata["resources_history"] = self.resources_history

        if exc_type:
            self.status = "FAILED"
            self.errors.append(str(exc_val))
            await self._save_failure_artifacts()
            await self._emit_event("StageFailed", error=str(exc_val))
        else:
            if self.status == "RUNNING":
                self.status = "COMPLETED"
            await self._emit_event("StageCompleted")

        # Persist to database
        await self._persist_db()
        return False  # Don't suppress exceptions

    def input(self, **kwargs) -> None:
        """Add stage input snapshot with sampling limits."""
        sampled: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, list):
                count = len(v)
                sample = []
                if count <= 20:
                    sample = [str(x.id) if hasattr(x, "id") else str(x) for x in v]
                else:
                    first_10 = [str(x.id) if hasattr(x, "id") else str(x) for x in v[:10]]
                    last_10 = [str(x.id) if hasattr(x, "id") else str(x) for x in v[-10:]]
                    sample = first_10 + ["..."] + last_10
                sampled[k] = {
                    "total_count": count,
                    "sample": sample,
                    "checksum": self._compute_checksum(v),
                }
            else:
                sampled[k] = str(v.id) if hasattr(v, "id") else str(v)
        self.input_data.update(sampled)

    def output(self, **kwargs) -> None:
        """Add stage output snapshot with sampling."""
        sampled: dict[str, Any] = {}
        for k, v in kwargs.items():
            if isinstance(v, list):
                count = len(v)
                sample = []
                if count <= 20:
                    sample = [str(x.id) if hasattr(x, "id") else str(x) for x in v]
                else:
                    first_10 = [str(x.id) if hasattr(x, "id") else str(x) for x in v[:10]]
                    last_10 = [str(x.id) if hasattr(x, "id") else str(x) for x in v[-10:]]
                    sample = first_10 + ["..."] + last_10
                sampled[k] = {"total_count": count, "sample": sample}
            else:
                sampled[k] = str(v.id) if hasattr(v, "id") else str(v)
        self.output_data.update(sampled)

    def metric(self, name: str, value: Any) -> None:
        """Record stage execution metrics."""
        self.metrics_data[name] = value

    def warn(self, message: str) -> None:
        """Record execution warnings."""
        self.warnings.append(message)

    def lineage(self, node_id: str, node_type: str, transition: str) -> None:
        """Record data lineage transition logs."""
        self.lineage_data.append(
            {
                "node_id": node_id,
                "type": node_type,
                "transition": transition,
                "created_at": datetime.now(UTC).isoformat() + "Z",
                "produced_by": self.stage,
            }
        )

    def artifact(self, name: str, payload: Any, tier: int = 1) -> None:
        """Save tiered large execution payloads to filesystem."""
        path = save_artifact(
            name=name,
            payload=payload,
            tier=tier,
            run_id=self.run_id,
            span_id=self.span_id,
            success=(self.status != "FAILED"),
        )
        if path:
            self.artifacts_data[name] = path

    def mark_skipped(self, reason: str = "no_pending_items") -> None:
        """Mark stage status as skipped with reason details."""
        self.status = "SKIPPED"
        self.warnings.append(f"Stage skipped: {reason}")

    async def _emit_event(self, event_type: str, error: str | None = None) -> None:
        seq = get_next_sequence_number()
        event = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "sequence_number": seq,
            "timestamp": datetime.now(UTC).isoformat() + "Z",
            "event_type": event_type,
            "stage": self.stage,
            "status": self.status,
            "duration_ms": self.latency_ms,
            "metrics": self.metrics_data,
            "input": self.input_data,
            "output": self.output_data,
            "artifacts": self.artifacts_data,
            "warnings": self.warnings,
            "errors": self.errors + ([error] if error else []),
            "lineage": self.lineage_data,
            "resources": {"start": self.resources_start, "end": self.resources_end},
        }
        await emit_pipeline_event(event)

    async def _save_failure_artifacts(self) -> None:
        if self.input_data:
            self.artifact("failure_input_context", self.input_data, tier=2)

    def _compute_checksum(self, data: Any) -> str:
        import hashlib

        try:
            return hashlib.sha256(str(data).encode("utf-8")).hexdigest()
        except Exception:
            return ""

    async def _persist_db(self) -> None:
        from app.core.database import async_session_factory
        from app.models.observability_models import StageRunModel

        async with async_session_factory() as session:
            stmt = select(StageRunModel).where(StageRunModel.id == _to_uuid(self.span_id))
            res = await session.execute(stmt)
            stage_run = res.scalar_one_or_none()

            metadata_payload = {
                "input": self.input_data,
                "output": self.output_data,
                "metrics": self.metrics_data,
                "warnings": self.warnings,
                "errors": self.errors,
                "lineage": self.lineage_data,
                "artifacts": self.artifacts_data,
                "resources": {"start": self.resources_start, "end": self.resources_end},
            }

            if not stage_run:
                stage_run = StageRunModel(
                    id=_to_uuid(self.span_id),
                    run_id=_to_uuid(self.run_id),
                    trace_id=_to_uuid(self.trace_id),
                    stage=self.stage,
                    status=self.status.lower(),
                    started_at=self.started_at,
                    completed_at=self.completed_at,
                    latency_ms=self.latency_ms,
                    retry_count=self.retry_count,
                    error=self.errors[0] if self.errors else None,
                    error_type="Exception" if self.errors else None,
                    story_id=_to_uuid(self.story_id),
                    article_id=_to_uuid(self.article_id),
                    metadata_payload=metadata_payload,
                )
                session.add(stage_run)
            else:
                stage_run.status = self.status.lower()
                stage_run.completed_at = self.completed_at
                stage_run.latency_ms = self.latency_ms
                stage_run.retry_count = self.retry_count
                stage_run.error = self.errors[0] if self.errors else None
                stage_run.metadata_payload = metadata_payload

            await session.commit()


class PipelineTraceCollector:
    """Centralized manager to spawn instrumented stage contexts."""

    @classmethod
    def stage(
        cls, name: str, story_id: str | None = None, article_id: str | None = None
    ) -> StageTrace:
        return StageTrace(name, story_id=story_id, article_id=article_id)


@dataclass
class LLMCallData:
    """Data captured from a single LLM API call."""

    call_id: str = ""
    provider: str = ""  # "gemini", "openai", "anthropic"
    model: str = ""
    stage: str = ""
    system_prompt: str = ""
    user_prompt: str = ""
    response_text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    temperature: float = 0.0
    status: str = "success"
    error: str | None = None
    retry_count: int = 0
    run_id: str = ""
    stage_run_id: str = ""
    parent_llm_trace_id: str = ""
    trace_id: str = ""
    story_id: str = ""
    article_id: str = ""


# ── LLM Cost Calculator ─────────────────────────────────────────────────────

# Pricing per million tokens (as of 2026-06 — update as needed)
LLM_PRICING: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "text-embedding-004": {"input": 0.00, "output": 0.00},  # Free
    "gemini-embedding-001": {"input": 0.00, "output": 0.00},  # Free
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.00},
}


def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost in USD for an LLM call."""
    pricing = LLM_PRICING.get(model, {"input": 0.0, "output": 0.0})
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return round(input_cost + output_cost, 8)


@asynccontextmanager
async def track_llm_call(
    provider: str,
    model: str,
    stage: str,
    system_prompt: str = "",
    user_prompt: str = "",
    temperature: float = 0.0,
    story_id: str = "",
    article_id: str = "",
):
    """Context manager to track an individual LLM API call.

    Captures timing, tokens, cost, and persists to LLMTrace table.
    """
    call = LLMCallData(
        call_id=str(uuid.uuid4()),
        provider=provider,
        model=model,
        stage=stage,
        system_prompt=system_prompt[:10000],  # Truncate for storage
        user_prompt=user_prompt[:10000],
        temperature=temperature,
        run_id=run_id_ctx.get(""),
        stage_run_id=span_id_ctx.get(""),
        parent_llm_trace_id=parent_llm_trace_id_ctx.get(""),
        trace_id=trace_id_ctx.get(""),
        story_id=story_id or story_id_ctx.get(""),
        article_id=article_id or article_id_ctx.get(""),
    )

    # Create Langfuse generation
    lf_generation = None
    if call.trace_id:
        try:
            lf_generation = langfuse_client.generation(
                trace_id=call.trace_id,
                span_id=span_id_ctx.get("") or None,
                model=call.model,
                name=f"{call.stage}:{call.model}",
                input={"system_prompt": call.system_prompt, "user_prompt": call.user_prompt},
                model_parameters={"temperature": call.temperature},
                metadata={
                    "provider": call.provider,
                    "story_id": call.story_id,
                    "article_id": call.article_id,
                },
            )
        except Exception:
            lf_generation = None

    parent_token = parent_llm_trace_id_ctx.set(call.call_id)
    start = time.perf_counter()
    try:
        yield call
        call.status = "success"
    except Exception as exc:
        call.status = "error"
        call.error = str(exc)
        raise
    finally:
        parent_llm_trace_id_ctx.reset(parent_token)
        call.latency_ms = round((time.perf_counter() - start) * 1000, 2)
        call.total_tokens = call.input_tokens + call.output_tokens
        call.cost_usd = calculate_llm_cost(call.model, call.input_tokens, call.output_tokens)

        # End Langfuse generation
        if lf_generation:
            try:
                lf_generation.end(
                    output=call.response_text or call.error,
                    usage={"input": call.input_tokens, "output": call.output_tokens},
                    level="ERROR" if call.status == "error" else "DEFAULT",
                    status_message=call.error,
                )
            except Exception:
                pass

        # Record Prometheus metrics
        try:
            from app.core.metrics import (
                newsiq_llm_cost_dollars,
                newsiq_provider_calls_total,
                newsiq_token_usage_total,
            )

            newsiq_token_usage_total.labels(
                provider=call.provider,
                model=call.model,
                stage=call.stage,
                token_type="input",
            ).inc(call.input_tokens)
            newsiq_token_usage_total.labels(
                provider=call.provider,
                model=call.model,
                stage=call.stage,
                token_type="output",
            ).inc(call.output_tokens)
            newsiq_llm_cost_dollars.labels(
                provider=call.provider, model=call.model, stage=call.stage
            ).inc(call.cost_usd)
            newsiq_provider_calls_total.labels(
                provider=call.provider,
                model=call.model,
                stage=call.stage,
                status=call.status,
            ).inc()
        except Exception:
            pass

        # Persist asynchronously (best-effort)
        try:
            await _persist_llm_call(call)
        except Exception:
            pass


async def _persist_llm_call(call: LLMCallData) -> None:
    """Persist an LLM call record to the database."""
    import hashlib

    from sqlalchemy import func, select, update

    from app.core.config import settings
    from app.core.database import async_session_factory
    from app.models.observability_models import LLMTraceModel, PromptVersionModel

    async with async_session_factory() as session:
        # Find active prompt version for this stage
        stmt = select(PromptVersionModel).where(
            PromptVersionModel.stage == call.stage, PromptVersionModel.is_active
        )
        res = await session.execute(stmt)
        pv = res.scalar_one_or_none()

        if not pv:
            # Create a default fallback/auto-captured prompt version for this stage
            sys_prompt = call.system_prompt or ""
            user_tmpl = call.user_prompt or ""
            if len(user_tmpl) > 1000:
                user_tmpl = user_tmpl[:1000] + "\n... [Dynamic Context] ..."

            combined = f"stage:{call.stage}\nsys:{sys_prompt}\nuser:{user_tmpl}"
            prompt_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

            # Check if this prompt hash already exists in DB
            stmt_hash = select(PromptVersionModel).where(
                PromptVersionModel.prompt_hash == prompt_hash
            )
            res_hash = await session.execute(stmt_hash)
            pv = res_hash.scalar_one_or_none()

            if not pv:
                # Find current max version for this stage
                stmt_max = select(func.max(PromptVersionModel.version)).where(
                    PromptVersionModel.stage == call.stage
                )
                res_max = await session.execute(stmt_max)
                max_v = res_max.scalar() or 0
                new_v = max_v + 1

                # Deactivate older prompt versions
                await session.execute(
                    update(PromptVersionModel)
                    .where(PromptVersionModel.stage == call.stage)
                    .values(is_active=False)
                )

                pv = PromptVersionModel(
                    id=uuid.uuid4(),
                    prompt_hash=prompt_hash,
                    stage=call.stage,
                    system_prompt=sys_prompt or None,
                    user_prompt_template=user_tmpl or None,
                    version=new_v,
                    description=f"Auto-captured prompt for {call.stage}",
                    is_active=True,
                )
                session.add(pv)
                await session.flush()

        # Decide whether to save prompt text based on settings & status
        save_prompts = (
            call.status == "error" or settings.DEBUG or getattr(call, "sample_prompt", False)
        )

        trace = LLMTraceModel(
            id=uuid.UUID(call.call_id),
            run_id=uuid.UUID(call.run_id) if call.run_id else None,
            stage_run_id=uuid.UUID(call.stage_run_id) if call.stage_run_id else None,
            parent_llm_trace_id=uuid.UUID(call.parent_llm_trace_id)
            if call.parent_llm_trace_id
            else None,
            trace_id=uuid.UUID(call.trace_id) if call.trace_id else None,
            provider=call.provider,
            model=call.model,
            stage=call.stage,
            system_prompt=call.system_prompt if save_prompts else None,
            user_prompt=call.user_prompt if save_prompts else None,
            response_text=call.response_text[:50000]
            if (save_prompts or call.status == "error")
            else None,
            input_tokens=call.input_tokens,
            output_tokens=call.output_tokens,
            total_tokens=call.total_tokens,
            latency_ms=call.latency_ms,
            cost_usd=call.cost_usd,
            temperature=call.temperature,
            status=call.status,
            error=call.error,
            retry_count=call.retry_count,
            story_id=uuid.UUID(call.story_id) if call.story_id else None,
            article_id=uuid.UUID(call.article_id) if call.article_id else None,
            prompt_version_id=pv.id if pv else None,
        )
        session.add(trace)
        await session.commit()
