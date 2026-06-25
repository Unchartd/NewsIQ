import logging
from typing import Any

from app.agents.agent_registry import agent_registry

logger = logging.getLogger(__name__)


async def route_agent_task(
    agent_name: str,
    task_input: Any,
    story_id: str = "",
    article_id: str = "",
) -> Any:
    """Route an agent execution task to the corresponding Agno agent, passing dynamic context details."""
    logger.info(
        "Routing agent task: %s (story_id=%s, article_id=%s)", agent_name, story_id, article_id
    )

    from app.agents.base_agent import run_agent_with_observability

    # Retrieve agent instance from registry
    agent = agent_registry.get_agent(agent_name, story_id=story_id, article_id=article_id)

    # Execute the agent asynchronously with central observability instrumentation
    run_output = await run_agent_with_observability(
        agent=agent, prompt=task_input, stage=agent_name, story_id=story_id, article_id=article_id
    )

    return run_output.content
