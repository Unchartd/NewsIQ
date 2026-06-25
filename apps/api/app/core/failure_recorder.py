import logging
import traceback
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.trace import _to_uuid
from app.models.observability_models import LLMTraceModel, PipelineFailureModel

logger = logging.getLogger(__name__)


def classify_error(exc: Exception, stage: str) -> tuple[str, str, str | None]:
    """Classify the exception and stage into category, subtype/code, and clean error code.

    Returns:
        (category, subtype, error_code)
    """
    exc_type = exc.__class__.__name__
    exc_msg = str(exc)
    msg_lower = exc_msg.lower()

    # 1. Agent Errors
    if stage in ("summary_reflection", "reflection_agent"):
        return "agent_error", "REFLECTION_FAILURE", "REFLECTION_FAILED"
    elif stage in ("cluster_verification", "clustering_verification"):
        return "agent_error", "CLUSTER_VERIFICATION_FAILURE", "VERIFICATION_FAILED"
    elif stage in ("judge_arbitration", "judge_agent"):
        return "agent_error", "JUDGE_AGENT_FAILURE", "JUDGE_FAILED"
    elif stage in ("entity_disambiguation", "entity_disambiguation_agent"):
        return "agent_error", "ENTITY_DISAMBIGUATION_FAILURE", "DISAMBIGUATION_FAILED"

    # 2. LLM Errors (from Gateway or containing LLM-related issues)
    llm_keywords = [
        "quota",
        "rate limit",
        "rate_limit",
        "429",
        "resource_exhausted",
        "context length",
        "token limit",
        "invalid api key",
        "authentication",
        "unauthorized",
        "api_key",
        "model_not_found",
        "gemini",
        "openai",
        "groq",
        "cerebras",
        "nvidia",
        "providers failed",
    ]
    is_llm = (
        any(kw in msg_lower for kw in llm_keywords)
        or "llm" in exc_type.lower()
        or "openai" in exc_type.lower()
    )

    if is_llm:
        if (
            "quota" in msg_lower
            or "resource_exhausted" in msg_lower
            or "billing" in msg_lower
            or "exhausted" in msg_lower
        ):
            return "llm_error", "QUOTA_EXCEEDED", "RESOURCE_EXHAUSTED"
        elif (
            "rate" in msg_lower
            or "429" in msg_lower
            or "too many requests" in msg_lower
            or "cooling down" in msg_lower
        ):
            return "llm_error", "RATE_LIMITED", "RATE_LIMIT_EXCEEDED"
        elif "timeout" in msg_lower or "timed out" in msg_lower:
            return "llm_error", "TIMEOUT", "LLM_TIMEOUT"
        elif (
            "context length" in msg_lower
            or "token limit" in msg_lower
            or "context window" in msg_lower
        ):
            return "llm_error", "CONTEXT_LENGTH_EXCEEDED", "CONTEXT_LENGTH_EXCEEDED"
        elif "json" in msg_lower or "parse" in msg_lower or "decode" in msg_lower:
            return "llm_error", "MALFORMED_JSON", "MALFORMED_JSON"
        elif "safety" in msg_lower or "block" in msg_lower or "harmful" in msg_lower:
            return "llm_error", "SAFETY_FILTER_BLOCK", "SAFETY_FILTER_BLOCK"
        elif (
            "503" in msg_lower
            or "unavailable" in msg_lower
            or "server error" in msg_lower
            or "502" in msg_lower
        ):
            return "llm_error", "PROVIDER_UNAVAILABLE", "PROVIDER_UNAVAILABLE"
        elif (
            "auth" in msg_lower
            or "api key" in msg_lower
            or "unauthorized" in msg_lower
            or "401" in msg_lower
        ):
            return "llm_error", "AUTHENTICATION_ERROR", "AUTHENTICATION_ERROR"
        elif "model not found" in msg_lower or "does not exist" in msg_lower:
            return "llm_error", "MODEL_UNAVAILABLE", "MODEL_UNAVAILABLE"
        return "llm_error", "UNKNOWN_LLM_ERROR", "UNKNOWN_PROVIDER_ERROR"

    # 3. Data Errors
    if "empty article" in msg_lower:
        return "data_error", "EMPTY_ARTICLE", "EMPTY_ARTICLE"
    elif "html" in msg_lower or "beautifulsoup" in msg_lower:
        return "data_error", "INVALID_HTML", "INVALID_HTML"
    elif stage == "event_extraction" and ("extraction" in msg_lower or "event" in msg_lower):
        return "data_error", "EXTRACTION_FAILURE", "EXTRACTION_FAILED"
    elif "fingerprint" in msg_lower or "malformed event" in msg_lower:
        return "data_error", "MALFORMED_EVENT", "MALFORMED_EVENT"
    elif "missing entities" in msg_lower:
        return "data_error", "MISSING_ENTITIES", "MISSING_ENTITIES"
    elif "timeline" in msg_lower or "corrupt timeline" in msg_lower:
        return "data_error", "CORRUPT_TIMELINE", "CORRUPT_TIMELINE"

    # 4. System Errors (Default fallback)
    if (
        "sqlalchemy" in exc_type.lower()
        or "asyncpg" in exc_type.lower()
        or "psycopg" in exc_type.lower()
        or "database" in msg_lower
        or "cursor" in msg_lower
    ):
        return "system_error", "DATABASE_ERROR", "DB_FAILURE"
    elif "redis" in msg_lower or "aioredis" in msg_lower:
        return "system_error", "REDIS_FAILURE", "REDIS_FAILURE"
    elif "qdrant" in msg_lower or "vector" in msg_lower:
        return "system_error", "QDRANT_FAILURE", "QDRANT_FAILURE"
    elif "celery" in msg_lower or "kombu" in msg_lower:
        return "system_error", "CELERY_FAILURE", "CELERY_FAILURE"
    elif "validation" in msg_lower or "pydantic" in msg_lower or "json" in msg_lower:
        return "system_error", "SERIALIZATION_ERROR", "SERIALIZATION_ERROR"
    elif "timeout" in msg_lower or "timeouterror" in msg_lower:
        return "system_error", "TIMEOUT", "TIMEOUT"
    elif (
        "http" in msg_lower
        or "network" in msg_lower
        or "connection" in msg_lower
        or "socket" in msg_lower
    ):
        return "system_error", "NETWORK_ISSUE", "NETWORK_ISSUE"
    elif "memory" in msg_lower or "oom" in msg_lower:
        return "system_error", "MEMORY_ISSUE", "OOM"

    return "system_error", "SYSTEM_ERROR", "UNKNOWN_SYSTEM_ERROR"


async def record_pipeline_failure(
    stage: str,
    exception: Exception,
    trace_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    story_id: uuid.UUID | None = None,
    article_id: uuid.UUID | None = None,
    provider: str | None = None,
    model: str | None = None,
    input_payload: dict[str, Any] | None = None,
    output_payload: dict[str, Any] | None = None,
    raw_response: str | None = None,
    retry_count: int = 0,
    latency: float = 0.0,
    error_code: str | None = None,
) -> uuid.UUID:
    """Record a pipeline failure into the database, performing auto-enrichment via LLM traces."""
    from app.core.trace import article_id_ctx, run_id_ctx, story_id_ctx, trace_id_ctx

    # Fallback to context variables if not provided
    tid = trace_id or _to_uuid(trace_id_ctx.get(None))
    rid = run_id or _to_uuid(run_id_ctx.get(None))
    sid = story_id or _to_uuid(story_id_ctx.get(None))
    aid = article_id or _to_uuid(article_id_ctx.get(None))

    category, subtype, resolved_err_code = classify_error(exception, stage)
    final_err_code = error_code or resolved_err_code

    # Format stack trace
    tb = exception.__traceback__
    stack = "".join(traceback.format_exception(type(exception), exception, tb))

    failure_id = uuid.uuid4()

    async with async_session_factory() as session:
        # Try to enrich failure using the latest LLM trace matching this trace/stage
        resolved_provider = provider
        resolved_model = model
        resolved_raw_resp = raw_response
        resolved_input = input_payload
        resolved_retries = retry_count

        if tid:
            try:
                stmt = (
                    select(LLMTraceModel)
                    .where(LLMTraceModel.trace_id == tid)
                    .order_by(LLMTraceModel.created_at.desc())
                    .limit(1)
                )
                res = await session.execute(stmt)
                latest_trace = res.scalar_one_or_none()
                if latest_trace:
                    if not resolved_provider:
                        resolved_provider = latest_trace.provider
                    if not resolved_model:
                        resolved_model = latest_trace.model
                    if not resolved_raw_resp:
                        resolved_raw_resp = latest_trace.response_text
                    if not resolved_input:
                        resolved_input = {
                            "system_prompt": latest_trace.system_prompt,
                            "user_prompt": latest_trace.user_prompt,
                            "temperature": latest_trace.temperature,
                        }
                    # Aggregate total retries seen in traces
                    resolved_retries = max(resolved_retries, latest_trace.retry_count)
            except Exception as enrich_err:
                logger.warning("Failed to enrich failure with LLM trace: %s", enrich_err)

        failure = PipelineFailureModel(
            id=failure_id,
            trace_id=tid,
            run_id=rid,
            story_id=sid,
            article_id=aid,
            stage=stage,
            provider=resolved_provider,
            model=resolved_model,
            status="failed",
            input_payload=resolved_input,
            output_payload=output_payload,
            raw_response=resolved_raw_resp,
            exception=f"{exception.__class__.__name__}: {str(exception)}",
            stack_trace=stack,
            error_category=category,
            error_code=final_err_code,
            retry_count=resolved_retries,
            latency=latency,
            timestamp=datetime.now(UTC).replace(tzinfo=None),
            resolved=False,
            resolution_notes=None,
        )
        session.add(failure)
        await session.commit()
        logger.info(
            "Recorded pipeline failure id=%s stage=%s category=%s", failure_id, stage, category
        )

    return failure_id
