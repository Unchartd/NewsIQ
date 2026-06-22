from pydantic import BaseModel, Field
from agno.agent import Agent
from app.agents.base_agent import get_default_model, run_agent_with_observability

class ClusterVerificationSchema(BaseModel):
    same_event: bool = Field(
        ...,
        description="True if both articles describe exactly the same real-world event/occurrence, False otherwise."
    )
    confidence: float = Field(
        ...,
        description="Confidence score from 0.0 to 1.0 indicating how certain you are of this decision."
    )
    explanation: str = Field(
        ...,
        description="Reasoning/explanation behind your decision, referencing specific facts and overlaps."
    )

cluster_verification_agent = Agent(
    name="Cluster Verification Agent",
    model=get_default_model(),
    instructions=[
        "You are a Staff Search and News Intelligence Engineer specializing in event validation.",
        "Your mission is to prevent false positive merges in news clustering. False positive merges are catastrophic.",
        "Compare two articles (including their titles, descriptions, extracted events, entities, and knowledge graph details).",
        "Determine if both articles describe the EXACT SAME real-world event/occurrence.",
        "Rules:",
        "1. If they describe different occurrences (e.g. two separate air strikes on the same city on different days), return same_event = False.",
        "2. If there is a core conflict in actors, targets, location, or event time, return same_event = False.",
        "3. If they describe the same event from different perspectives or timelines of the same event, return same_event = True.",
        "4. Be extremely precise and conservative."
    ],
    output_schema=ClusterVerificationSchema,
)

async def verify_cluster_decision(
    article_a_title: str,
    article_a_event: dict,
    article_b_title: str,
    article_b_event: dict,
    similarity_score: float,
    kg_nodes: list = None,
) -> ClusterVerificationSchema:
    """Invoke the agent to verify if two articles describe the same event."""
    prompt = f"""
    Compare the following two articles and decide if they describe the exact same event:
    
    Article A:
    - Title: {article_a_title}
    - Extracted Event: {article_a_event}
    
    Article B:
    - Title: {article_b_title}
    - Extracted Event: {article_b_event}
    
    Determined Similarity Score: {similarity_score:.4f}
    Knowledge Graph Context: {kg_nodes or 'None'}
    
    Determine if they represent the same event.
    """
    
    run_output = await run_agent_with_observability(
        agent=cluster_verification_agent,
        prompt=prompt,
        stage="cluster_verification"
    )
    return run_output.content
