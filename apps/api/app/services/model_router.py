import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelRouter:
    """Centralized LLM model router.

    Determines the correct model for a given stage and complexity level,
    taking into account cost budget status.
    """

    def select(
        self, stage: str, complexity: str = "standard", budget_exceeded: bool = False
    ) -> str:
        """Select the model for a stage, respecting complexity and budget limits."""
        routing_table = getattr(settings, "MODEL_ROUTING_TABLE", {})

        # Default fallback table
        default_table = {
            "event_extraction": {
                "standard": "gemini-2.5-flash-lite",
                "complex": "gemini-2.5-flash",
                "budget_exceeded": "gemini-2.5-flash-lite",
            },
            "entity_linking": {
                "standard": "gemini-2.5-flash-lite",
                "complex": "gemini-2.5-flash",
                "budget_exceeded": "gemini-2.5-flash-lite",
            },
            "contradiction_detection": {
                "standard": "gemini-2.5-flash-lite",
                "complex": "gemini-2.5-flash",
                "budget_exceeded": "gemini-2.5-flash-lite",
            },
            "source_comparison": {
                "standard": "gemini-2.5-flash-lite",
                "complex": "gemini-2.5-flash",
                "budget_exceeded": "gemini-2.5-flash-lite",
            },
            "summary_generation": {
                "standard": "gemini-2.5-flash",
                "complex": "gemini-2.5-pro",
                "budget_exceeded": "gemini-2.5-flash",
            },
            "summary_reflection": {
                "standard": "gemini-2.5-flash-lite",
                "complex": "gemini-2.5-flash",
                "budget_exceeded": "skip",
            },
            "cluster_verification": {
                "standard": "gemini-2.5-flash-lite",
                "complex": "gemini-2.5-flash",
                "budget_exceeded": "gemini-2.5-flash-lite",
            },
        }

        stage_table = routing_table.get(stage, default_table.get(stage, {}))
        if not stage_table:
            return getattr(settings, "SUMMARIZATION_MODEL", "gemini-2.5-flash")

        if budget_exceeded:
            model = stage_table.get("budget_exceeded", stage_table.get("standard"))
        else:
            model = stage_table.get(complexity, stage_table.get("standard"))

        logger.debug(
            "Routed stage '%s' (complexity: %s, budget_exceeded: %s) to model: %s",
            stage,
            complexity,
            budget_exceeded,
            model,
        )
        return model


model_router = ModelRouter()
