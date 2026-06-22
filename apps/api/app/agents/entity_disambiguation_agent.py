from pydantic import BaseModel, Field
from agno.agent import Agent
from app.agents.base_agent import get_default_model, run_agent_with_observability

class EntityDisambiguationSchema(BaseModel):
    canonical_name: str = Field(
        ...,
        description="The standardized canonical name of the entity."
    )
    wikidata_id: str | None = Field(
        None,
        description="The Wikidata ID (QID) if found, otherwise null."
    )
    entity_type: str = Field(
        ...,
        description="The correct entity category (e.g., PERSON, ORG, GPE, AGREEMENT, EVENT)."
    )
    explanation: str = Field(
        ...,
        description="Reasoning/explanation behind this disambiguation."
    )

entity_disambiguation_agent = Agent(
    name="Entity Disambiguation Agent",
    model=get_default_model(),
    instructions=[
        "You are a Knowledge Graph Architect and Entity Linker.",
        "Your goal is to resolve and canonicalize raw entity mentions using context.",
        "Disambiguate terms that are ambiguous or misspelled.",
        "Rules:",
        "1. Resolve raw mentions of persons, organizations, locations, agreements, and concepts.",
        "2. If an acronym or short name matches a well-known entity (e.g., 'Trump' -> 'Donald Trump'), resolve it.",
        "3. Correct incorrect classification types (e.g., 'MoU' or 'Memorandum of Understanding' is an AGREEMENT, not a PERSON).",
        "4. If a Wikidata ID can be resolved, provide it (e.g. 'Q22686' for Donald Trump). Otherwise, return null.",
        "5. Be conservative and correct."
    ],
    output_schema=EntityDisambiguationSchema,
)

async def disambiguate_entity(
    entity_value: str,
    entity_type: str,
    context: str = ""
) -> EntityDisambiguationSchema:
    """Invoke the agent to resolve and link an entity."""
    prompt = f"""
    Resolve and canonicalize the following entity mention:
    - Raw Value: {entity_value}
    - Initial Type: {entity_type}
    - Context: {context[:2000]}
    """
    
    run_output = await run_agent_with_observability(
        agent=entity_disambiguation_agent,
        prompt=prompt,
        stage="entity_disambiguation"
    )
    return run_output.content
