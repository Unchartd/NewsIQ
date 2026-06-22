# Agent Registry and Router

All Agno AI Agents in NewsIQ are configured centrally in a registry and executed dynamically through a dispatch router. This decouples the core pipelines from individual agent definitions and prompts.

## Agent Registry

The agent registry is defined in [agent_registry.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/agents/agent_registry.py). It registers agents lazily to avoid unnecessary initializations during startup.

Every agent in the registry is configured with:
1. **Model**: A custom `GatewayModel` subclass of Agno's `Model` class.
2. **System Prompts**: Curated system prompts focusing on precision.
3. **Output Schema**: A Pydantic schema enforcing structured responses.

```python
from app.agents.gateway_model import GatewayModel
from agno.agent import Agent

def get_cluster_verification_agent() -> Agent:
    return Agent(
        model=GatewayModel(id="gemini-2.5-flash-lite", stage="cluster_verification"),
        description="Verify if two articles describe the same event.",
        response_format=ClusterVerificationSchema,
        structured_outputs=True
    )
```

## Agent Router

The router in [agent_router.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/agents/agent_router.py) acts as a single endpoint to dispatch tasks to the registered agents. This design allows pipelines to simply request task execution without direct imports of agent scripts.

```python
async def route_agent_task(task_name: str, payload: dict) -> Any:
    """Dispatches execution to the target agent based on the task name."""
    if task_name == "cluster_verification":
        return await verify_cluster_decision(**payload)
    elif task_name == "entity_disambiguation":
        return await disambiguate_entity(**payload)
    elif task_name == "contradiction_check":
        return await check_contradiction(**payload)
    elif task_name == "reflection":
        return await reflect_on_summary(**payload)
    elif task_name == "judge":
        return await resolve_disagreement(**payload)
    else:
        raise ValueError(f"Unknown agent task: {task_name}")
```

## Key Advantages

* **Prompt Centralization**: Prompts are stored and versioned inside the agent classes, facilitating systematic prompt engineering.
* **Gateway-Enforced Execution**: By wrapping every agent in `GatewayModel`, we ensure they cannot bypass rate limits, key rotation, or fallback chains.
* **Unified Metrics**: Agent runs are instrumented with Prometheus counters in [agent_metrics.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/agents/agent_metrics.py) to track executions, latencies, and output distributions.
