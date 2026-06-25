import logging

from agno.agent import Agent

from app.agents.gateway_model import GatewayModel
from app.core.config import settings

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Manages central lazy instantiation of Agno agents, injecting tracing context variables dynamically."""

    def get_agent(
        self,
        name: str,
        story_id: str = "",
        article_id: str = "",
    ) -> Agent:
        """Instantiate or configure the target Agent, binding dynamic context details to its GatewayModel."""
        model_id = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"

        if name == "cluster_verification":
            from app.agents.cluster_verification_agent import cluster_verification_agent

            agent = cluster_verification_agent
            agent.model = GatewayModel(
                id=model_id, stage="cluster_verification", story_id=story_id, article_id=article_id
            )
            return agent

        elif name == "entity_disambiguation":
            from app.agents.entity_disambiguation_agent import entity_disambiguation_agent

            agent = entity_disambiguation_agent
            agent.model = GatewayModel(
                id=model_id, stage="entity_disambiguation", story_id=story_id, article_id=article_id
            )
            return agent

        elif name == "contradiction":
            from app.agents.contradiction_agent import contradiction_agent

            agent = contradiction_agent
            agent.model = GatewayModel(
                id=model_id,
                stage="contradiction_detection",
                story_id=story_id,
                article_id=article_id,
            )
            return agent

        elif name == "reflection":
            from app.agents.reflection_agent import reflection_agent

            agent = reflection_agent
            agent.model = GatewayModel(
                id=model_id, stage="summary_reflection", story_id=story_id, article_id=article_id
            )
            return agent

        elif name == "judge":
            from app.agents.judge_agent import judge_agent

            agent = judge_agent
            agent.model = GatewayModel(
                id=model_id, stage="judge_arbitration", story_id=story_id, article_id=article_id
            )
            return agent

        else:
            raise ValueError(f"Unknown agent name: {name}")


# Singleton Instance
agent_registry = AgentRegistry()
