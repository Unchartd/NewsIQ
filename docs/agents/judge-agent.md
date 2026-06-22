# Judge Agent

The **Judge Agent** is an arbitration layer that resolves conflicting evaluations or decisions from different LLM models.

## Execution and Triggers

- **Scope**: Used only on high-stakes critical events (e.g. War, Elections, Finance, Breaking News).
- **Behavior**: If two different verification agents (e.g. Gemini-backed and OpenAI-backed) arrive at different conclusions regarding an event merge or verification task, the Judge Agent arbitrates to make the final determination.

## Schema and Structure

The agent utilizes structured outputs matching the following Pydantic schema:

```python
class JudgeSchema(BaseModel):
    final_decision: bool = Field(..., description="The resolved final decision.")
    chosen_provider: str = Field(..., description="The provider or model whose logic/evaluation was selected (e.g. 'gemini', 'openai').")
    explanation: str = Field(..., description="Detailed explanation of the ruling.")
```

## Instructions

1. Critically compare the reasoning, confidence, and context from both conflicting providers.
2. Spot logic errors, missed details, or over-assumptions.
3. Choose the decision that ensures the highest precision for the system (favoring conservative/careful options to prevent incorrect merges).
