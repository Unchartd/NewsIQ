
import pytest

from app.services.cost_budget import cost_budget_manager
from app.services.model_router import model_router


def test_model_router_selection():
    """Verify that model router returns correct models based on complexity and budget state."""
    # 1. Standard selection
    m = model_router.select(stage="event_extraction", complexity="standard")
    assert m == "gemini-2.5-flash-lite"

    # 2. Complex selection
    m = model_router.select(stage="event_extraction", complexity="complex")
    assert m == "gemini-2.5-flash"

    # 3. Budget exceeded selection
    m = model_router.select(stage="event_extraction", budget_exceeded=True)
    assert m == "gemini-2.5-flash-lite"

    # 4. Skip reflection on budget exceeded
    m = model_router.select(stage="summary_reflection", budget_exceeded=True)
    assert m == "skip"


@pytest.mark.asyncio
async def test_cost_budget_manager_tracking():
    """Verify that CostBudgetManager tracks cost in Redis or fallback memory."""
    story_id = "test-story-id"

    # Check default limit
    limit = cost_budget_manager.get_budget_limit("world")
    assert limit == 0.015  # high stakes default

    # Clear cost in both Redis and memory
    from app.services.cache_service import cache_service
    if cache_service._redis:
        try:
            await cache_service._redis.delete(f"story_cost:{story_id}")
        except Exception:
            pass
    from app.services.cost_budget import _memory_cost_cache
    _memory_cost_cache[story_id] = 0.0

    # Add cost
    new_cost = await cost_budget_manager.add_story_cost(story_id, 0.005)
    assert new_cost == 0.005
    assert not await cost_budget_manager.is_budget_exceeded(story_id, "world")

    # Exceed limit
    await cost_budget_manager.add_story_cost(story_id, 0.012)
    assert await cost_budget_manager.is_budget_exceeded(story_id, "world")
