from typing import Any, TypeVar

import structlog
from agno.agent import Agent, RunOutput

from app.agents.gateway_model import GatewayModel
from app.core.config import settings

logger = structlog.get_logger(__name__)

T = TypeVar("T")


def get_default_model() -> GatewayModel:
    """Return default GatewayModel based on settings."""
    model_id = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"
    return GatewayModel(id=model_id, stage="agent_execution")


async def run_agent_with_observability(
    agent: Agent,
    prompt: Any,
    stage: str,
    story_id: str = "",
    article_id: str = "",
) -> RunOutput:
    """Execute an Agno agent by routing calls through the gateway with trace correlation."""
    import time

    from app.agents.agent_metrics import newsiq_agent_runs_latency_seconds, newsiq_agent_runs_total
    from app.services.cost_budget import cost_budget_manager

    # Bind dynamic run context variables and route model dynamically
    from app.services.model_router import model_router

    budget_exceeded = False
    if story_id:
        budget_exceeded = await cost_budget_manager.is_budget_exceeded(story_id)

    routed_model_id = model_router.select(stage=stage, complexity="standard", budget_exceeded=budget_exceeded)

    if routed_model_id == "skip":
        class MockRunOutput:
            def __init__(self, content):
                self.content = content

        if stage == "summary_reflection":
            from app.agents.reflection_agent import ReflectionSchema
            default_content = ReflectionSchema(
                has_hallucinations=False,
                invented_facts=[],
                omitted_critical_facts=[],
                contradicts_graph=False,
                explanation="Reflection skipped due to cost budget limits."
            )
        else:
            default_content = None

        logger.info("Stage '%s' skipped via model routing.", stage)
        return MockRunOutput(content=default_content)

    agent.model = GatewayModel(id=routed_model_id, stage=stage)

    if isinstance(agent.model, GatewayModel):
        agent.model.story_id = story_id
        agent.model.article_id = article_id

    start_time = time.time()
    status = "success"
    try:
        run_output: RunOutput = await agent.arun(prompt)
        return run_output
    except Exception as e:
        status = "error"
        try:
            from app.core.failure_recorder import record_pipeline_failure
            from app.core.trace import _to_uuid, run_id_ctx, trace_id_ctx

            provider = getattr(agent.model, "provider", None)
            model_id = getattr(agent.model, "id", None)

            await record_pipeline_failure(
                stage=stage,
                exception=e,
                trace_id=_to_uuid(trace_id_ctx.get("")),
                run_id=_to_uuid(run_id_ctx.get("")),
                story_id=_to_uuid(story_id) if story_id else None,
                article_id=_to_uuid(article_id) if article_id else None,
                provider=provider,
                model=model_id,
                input_payload={"prompt": prompt},
                latency=time.time() - start_time,
            )
        except Exception as rec_err:
            logger.error("Failed to record agent failure: %s", rec_err)
        raise e
    finally:
        latency = time.time() - start_time
        newsiq_agent_runs_total.labels(agent_name=agent.name or "unknown", status=status).inc()
        newsiq_agent_runs_latency_seconds.labels(agent_name=agent.name or "unknown").observe(
            latency
        )
