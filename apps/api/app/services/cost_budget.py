import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Default in-memory cache for fallback when Redis is unavailable
_memory_cost_cache: dict[str, float] = {}


class CostBudgetManager:
    """Manages LLM cost budget and tracks per-story expenditures."""

    def get_budget_limit(self, category_slug: str = "world") -> float:
        """Get the cost budget limit for a category."""
        default_limit = getattr(settings, "STORY_COST_BUDGET_DEFAULT", 0.005)
        high_stakes_limit = getattr(settings, "STORY_COST_BUDGET_HIGH_STAKES", 0.015)

        if category_slug in ("world", "politics", "business", "health"):
            return high_stakes_limit
        return default_limit

    async def add_story_cost(self, story_id: str, cost: float) -> float:
        """Add cost to a story tracker, returning the new total cost."""
        if not story_id:
            return 0.0

        from app.services.cache_service import cache_service

        key = f"story_cost:{story_id}"

        # Try incrementing via cache_service public API if active
        if cache_service.is_active:
            try:
                new_cost = await cache_service.incr_by_float(key, cost, ttl=3600)
                return new_cost
            except Exception as e:
                logger.warning(
                    "Failed to increment cost via cache_service for story %s: %s", story_id, e
                )

        # Fallback to memory cache
        current = _memory_cost_cache.get(story_id, 0.0)
        new_cost = current + cost
        _memory_cost_cache[story_id] = new_cost
        return new_cost

    async def get_story_cost(self, story_id: str) -> float:
        """Get the accumulated cost of a story."""
        if not story_id:
            return 0.0

        from app.services.cache_service import cache_service

        key = f"story_cost:{story_id}"

        if cache_service.is_active:
            try:
                val = await cache_service.get_raw(key)
                if val is not None:
                    return float(val)
            except Exception:
                pass

        return _memory_cost_cache.get(story_id, 0.0)

    async def is_budget_exceeded(self, story_id: str, category_slug: str = "world") -> bool:
        """Check if a story has exceeded its budget limit."""
        if not story_id:
            return False

        cost = await self.get_story_cost(story_id)
        limit = self.get_budget_limit(category_slug)
        is_exceeded = cost > limit
        if is_exceeded:
            logger.warning(
                "Cost budget exceeded for story %s. Current: $%f, Limit: $%f",
                story_id,
                cost,
                limit,
            )
        return is_exceeded

    async def is_stage_budget_exceeded(
        self, story_id: str, stage: str, category_slug: str = "world"
    ) -> bool:
        """Check if the current accumulated cost exceeds the stage-specific threshold."""
        if not story_id:
            return False

        cost = await self.get_story_cost(story_id)
        limit = self.get_budget_limit(category_slug)
        threshold_pct = STAGE_BUDGET_THRESHOLDS.get(stage, 1.0)

        is_exceeded = cost > (limit * threshold_pct)
        if is_exceeded:
            logger.warning(
                "Stage budget exceeded for story %s, stage %s. Current: $%f, Limit: $%f, Threshold: %d%%",
                story_id,
                stage,
                cost,
                limit,
                int(threshold_pct * 100),
            )
        return is_exceeded


# Stage-aware budget thresholds as a percentage of the total story cost budget
STAGE_BUDGET_THRESHOLDS = {
    "summary_reflection": 0.50,  # Skip reflection if spent > 50% of budget
    "source_comparison": 0.80,  # Fallback to deterministic comparison if spent > 80%
    "contradiction_detection": 0.70,  # Fallback to cheaper models if spent > 70%
    "summary_generation": 1.00,  # Fallback to cheaper models if spent > 100% (never skip)
}

cost_budget_manager = CostBudgetManager()
