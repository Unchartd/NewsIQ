from unittest.mock import patch

import pytest

from app.services.cost_budget import cost_budget_manager


@pytest.mark.asyncio
async def test_cost_budget_manager_limits():
    # Verify defaults
    assert cost_budget_manager.get_budget_limit("world") == 0.015
    assert cost_budget_manager.get_budget_limit("politics") == 0.015
    assert cost_budget_manager.get_budget_limit("technology") == 0.005


@pytest.mark.asyncio
async def test_stage_aware_budget_enforcement():
    story_id = "test-stage-story-id"
    category = "world"
    cost_budget_manager.get_budget_limit(category)  # $0.015

    from app.services.cache_service import cache_service

    with patch.object(cache_service, "_redis", None):
        # Mock Redis to force in-memory storage fallback
        from app.services.cost_budget import _memory_cost_cache

        _memory_cost_cache[story_id] = 0.0

        # 1. Under all budgets
        await cost_budget_manager.add_story_cost(story_id, 0.002)  # $0.002 total
        assert not await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "summary_reflection", category
        )
        assert not await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "source_comparison", category
        )

        # 2. Exceeds reflection budget (50% of $0.015 = $0.0075)
        await cost_budget_manager.add_story_cost(story_id, 0.006)  # $0.008 total
        assert await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "summary_reflection", category
        )
        assert not await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "source_comparison", category
        )

        # 3. Exceeds comparison budget (80% of $0.015 = $0.012)
        await cost_budget_manager.add_story_cost(story_id, 0.005)  # $0.013 total
        assert await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "summary_reflection", category
        )
        assert await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "source_comparison", category
        )
        assert not await cost_budget_manager.is_stage_budget_exceeded(
            story_id, "summary_generation", category
        )
