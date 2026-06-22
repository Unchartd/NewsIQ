# Reflection Agent

The **Reflection Agent** is the final quality assurance gate for story generation. It analyzes the generated story summary against raw source facts to prevent hallucinations or factual distortions.

## Execution and Triggers

Reflection runs right after story summary synthesis, but is restricted to specific criteria to control latency and costs:
- **Scope**: Top/trending stories (stories with 3 or more articles) or high-stakes categories (e.g. world, politics, business).
- **Behavior**: If the agent detects critical hallucinations or graph contradictions, it triggers a **regeneration** of the story summary.

## Schema and Structure

The agent utilizes structured outputs matching the following Pydantic schema:

```python
class ReflectionSchema(BaseModel):
    has_hallucinations: bool = Field(..., description="True if the summary invents facts not supported by the inputs, False otherwise.")
    invented_facts: list[str] = Field(default_factory=list, description="List of invented facts or hallucinations found in the summary.")
    omitted_critical_facts: list[str] = Field(default_factory=list, description="List of critical facts present in the timeline but missing from the summary.")
    contradicts_graph: bool = Field(..., description="True if the summary directly contradicts relationships/entities in the knowledge graph.")
    explanation: str = Field(..., description="Detailed evaluation explanation.")
```

## Instructions

The agent acts as a strict proofreader:
1. Ensure every fact, number, and actor role mentioned in the summary is fully grounded in the timeline or knowledge graph.
2. Flag any invented contextual assertions.
3. Check for omission of pivotal timeline events.
