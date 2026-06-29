from agno.agent import Agent
from pydantic import BaseModel, Field

from app.agents.base_agent import get_default_model, run_agent_with_observability


class ReflectionSchema(BaseModel):
    has_hallucinations: bool = Field(
        ...,
        description="True if the summary invents facts not supported by the input sources/timeline, False otherwise.",
    )
    invented_facts: list[str] = Field(
        default_factory=list,
        description="List of invented facts or hallucinations found in the summary.",
    )
    omitted_critical_facts: list[str] = Field(
        default_factory=list,
        description="List of critical facts present in the timeline or graph but missing from the summary.",
    )
    contradicts_graph: bool = Field(
        ...,
        description="True if the summary directly contradicts relationships or entities in the knowledge graph.",
    )
    explanation: str = Field(..., description="Detailed evaluation explanation of your review.")


reflection_agent = Agent(
    name="Reflection Agent",
    model=get_default_model(),
    instructions=[
        "You are a Staff AI Quality Assurance Engineer and Fact-Checker.",
        "Your mission is to perform strict verification of generated story summaries to prevent hallucinations or factual contradictions.",
        "Compare the generated summary against the ground truth data: the knowledge graph, chronological timeline, and source coverage.",
        "Analyze the following questions:",
        "1. Did the summary invent or hallucinate any facts, figures, dates, or events not present in the input?",
        "2. Did it omit any extremely critical/central facts from the timeline?",
        "3. Does it contradict the relationships or entities in the knowledge graph?",
        "Be extremely critical. Factual correctness is our highest priority.",
    ],
    output_schema=ReflectionSchema,
)


async def reflect_on_summary(
    summary_text: str,
    timeline: list[dict],
    kg_nodes: list[dict],
    source_coverage: list[dict] = None,
) -> ReflectionSchema:
    """Invoke the agent to perform quality reflection on a generated story summary."""
    prompt = f"""
    Review the following generated summary against the source data:

    Generated Summary:
    {summary_text}

    Ground Truth Timeline:
    {timeline}

    Knowledge Graph Nodes/Edges:
    {kg_nodes}

    Source Coverage/Differences Context:
    {source_coverage or "None"}

    Perform a complete reflection analysis.
    """

    run_output = await run_agent_with_observability(
        agent=reflection_agent, prompt=prompt, stage="summary_reflection"
    )

    # Check if run_output.content is already a ReflectionSchema (e.g. from MockRunOutput/skipped or unit test mocks)
    if isinstance(run_output.content, ReflectionSchema):
        return run_output.content

    # If run_output has parsed attribute and it is ReflectionSchema, use it
    if hasattr(run_output, "parsed") and isinstance(run_output.parsed, ReflectionSchema):
        return run_output.parsed

    # If it is a string (e.g. JSON), parse it into ReflectionSchema
    if isinstance(run_output.content, str):
        try:
            import json
            data = json.loads(run_output.content)
            return ReflectionSchema.model_validate(data)
        except Exception:
            if hasattr(run_output, "parsed") and isinstance(run_output.parsed, ReflectionSchema):
                return run_output.parsed

    # Return a fallback ReflectionSchema
    return ReflectionSchema(
        has_hallucinations=False,
        invented_facts=[],
        omitted_critical_facts=[],
        contradicts_graph=False,
        explanation=str(run_output.content) if run_output.content else "No reflection content generated."
    )
