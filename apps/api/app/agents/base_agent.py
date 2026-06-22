import structlog
from typing import Any, TypeVar
from agno.agent import Agent, RunOutput
from app.core.config import settings
from app.agents.gateway_model import GatewayModel

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
    from app.agents.agent_metrics import newsiq_agent_runs_total, newsiq_agent_runs_latency_seconds

    # Bind dynamic run context variables to the GatewayModel
    if isinstance(agent.model, GatewayModel):
        agent.model.stage = stage
        agent.model.story_id = story_id
        agent.model.article_id = article_id

    start_time = time.time()
    status = "success"
    try:
        run_output: RunOutput = await agent.arun(prompt)
        return run_output
    except Exception as e:
        status = "error"
        raise e
    finally:
        latency = time.time() - start_time
        newsiq_agent_runs_total.labels(agent_name=agent.name or "unknown", status=status).inc()
        newsiq_agent_runs_latency_seconds.labels(agent_name=agent.name or "unknown").observe(latency)

