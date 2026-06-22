from pydantic import BaseModel, Field
from agno.agent import Agent
from app.agents.base_agent import get_default_model, run_agent_with_observability

class JudgeSchema(BaseModel):
    final_decision: bool = Field(
        ...,
        description="The resolved final decision (e.g. same_event decision resolved as True or False)."
    )
    chosen_provider: str = Field(
        ...,
        description="The provider or model whose logic/evaluation was selected (e.g., 'gemini', 'openai')."
    )
    explanation: str = Field(
        ...,
        description="Detailed explanation of the disagreement, comparison of the reasoning, and rationale for the final decision."
    )

judge_agent = Agent(
    name="Judge Agent",
    model=get_default_model(),
    instructions=[
        "You are the Supreme Judge Agent on a news intelligence platform.",
        "Your mission is to arbitrate and resolve disagreements between different LLM providers or models (such as Gemini and OpenAI) on critical verification tasks.",
        "Analyze the inputs from both providers, compare their reasoning, check for logical fallacies or missed context, and make a definitive, high-confidence decision.",
        "Select the provider that demonstrates higher precision, alignment with facts, and conservative judgment.",
        "Rules:",
        "1. For cluster verification: If one model says same_event = False and has strong evidence (e.g., different locations or dates), favor same_event = False to prevent false positive merges.",
        "2. Detail the exact trade-offs and logical points considered."
    ],
    output_schema=JudgeSchema,
)

async def resolve_disagreement(
    task_description: str,
    provider_a_name: str,
    provider_a_output: dict,
    provider_b_name: str,
    provider_b_output: dict,
    context: str = ""
) -> JudgeSchema:
    """Invoke the judge agent to resolve a disagreement between two provider decisions."""
    prompt = f"""
    A disagreement occurred on a critical verification task. Please evaluate and make a final ruling:
    
    Task: {task_description}
    
    Provider A ({provider_a_name}) Decision:
    {provider_a_output}
    
    Provider B ({provider_b_name}) Decision:
    {provider_b_output}
    
    Context Details:
    {context[:3000]}
    
    Deliver your final judgment.
    """
    
    run_output = await run_agent_with_observability(
        agent=judge_agent,
        prompt=prompt,
        stage="judge_arbitration"
    )
    return run_output.content
