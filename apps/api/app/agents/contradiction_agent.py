from pydantic import BaseModel, Field
from agno.agent import Agent
from app.agents.base_agent import get_default_model, run_agent_with_observability

class ContradictionSchema(BaseModel):
    contradiction: bool = Field(
        ...,
        description="True if there is a true factual contradiction, False otherwise."
    )
    field: str | None = Field(
        None,
        description="The field of contradiction (e.g., event_time, number, quote, casualty)."
    )
    confidence: float = Field(
        ...,
        description="Confidence score from 0.0 to 1.0 of this contradiction assessment."
    )
    explanation: str = Field(
        ...,
        description="Clear, explainable description of the contradiction (e.g., 'BBC reports rain began at 2 PM, while TOI reports it began at 3 PM.')"
    )

contradiction_agent = Agent(
    name="Contradiction Agent",
    model=get_default_model(),
    instructions=[
        "You are a factual contradiction validator for a news intelligence platform.",
        "Your task is to analyze candidate mismatches between two news sources covering the same story and determine if it represents a true factual contradiction.",
        "Factual contradictions include differences in times (e.g. 2 PM vs 3 PM), numbers/casualty counts (e.g. 15 dead vs 50 dead), quotes, or conflicting actor actions.",
        "Rules:",
        "1. Subset relationships (e.g. 'at least 10 dead' vs '12 dead') are NOT contradictions.",
        "2. Wording differences or minor translation differences are NOT contradictions.",
        "3. Only mark contradiction = True when the statements explicitly oppose or conflict with each other."
    ],
    output_schema=ContradictionSchema,
)

async def check_contradiction(
    fact_type: str,
    val1: str,
    val2: str,
    source1_name: str,
    source2_name: str,
    context: str = ""
) -> ContradictionSchema:
    """Invoke the contradiction agent to analyze a candidate mismatch."""
    prompt = f"""
    Compare these two conflicting reports of the same details/facts:
    - Detail Category/Field: {fact_type}
    - Report 1 ({source1_name}): {val1}
    - Report 2 ({source2_name}): {val2}
    
    Context from the articles:
    {context[:3000]}
    
    Determine if this represents a true factual contradiction.
    """
    
    run_output = await run_agent_with_observability(
        agent=contradiction_agent,
        prompt=prompt,
        stage="contradiction_detection"
    )
    return run_output.content
