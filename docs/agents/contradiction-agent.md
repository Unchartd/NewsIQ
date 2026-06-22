# Contradiction Agent

The **Contradiction Agent** identifies factual discrepancies across different articles/sources clustered within a single story.

## Execution and Triggers

- **Scope**: Runs per story, auditing facts collected across all of its source articles.
- **Trigger**: Local heuristics identify candidate mismatches (e.g. differing casualty numbers, conflicting timestamps, or opposing quotes). The agent is then invoked to perform semantic validation.

## Schema and Structure

The agent utilizes structured outputs matching the following Pydantic schema:

```python
class ContradictionSchema(BaseModel):
    contradiction: bool = Field(..., description="True if there is a true factual contradiction, False otherwise.")
    field: str | None = Field(None, description="The field of contradiction (e.g., event_time, number, quote, casualty).")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0.")
    explanation: str = Field(..., description="Explain why it is or is not a contradiction.")
```

## Instructions

1. Differentiate between genuine contradictions (e.g., "15 casualties" vs "50 casualties") and subset descriptions (e.g., "at least 10 dead" vs "12 dead" is not a contradiction).
2. Flag mismatches in key quotes, timelines, or actor actions.
3. Ignore wording or minor translation variations.
