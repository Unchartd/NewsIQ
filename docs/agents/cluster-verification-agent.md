# Cluster Verification Agent

The **Cluster Verification Agent** is a core quality gate in the NewsIQ clustering engine. Its purpose is to prevent false-positive merges, ensuring high-fidelity storytelling where every story represents exactly **one real-world event**.

## Triggers and Thresholds

The agent is not invoked on every similarity comparison. It runs as part of a hybrid deterministic/agentic pipeline:

- **Similarity > 0.90**: High confidence. Auto-merge the article into the story/sub-cluster.
- **Similarity < 0.70**: Low confidence. Reject merge, creating a separate story.
- **0.70 <= Similarity <= 0.90**: Ambiguity zone. Invoke the **Cluster Verification Agent** to make the final determination.

## Schema and Structure

The agent utilizes structured outputs matching the following Pydantic schema:

```python
class ClusterVerificationSchema(BaseModel):
    same_event: bool = Field(..., description="True if both articles describe exactly the same real-world event/occurrence, False otherwise.")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0.")
    explanation: str = Field(..., description="Reasoning/explanation behind your decision.")
```

## Instructions

The agent operates under strict instructions to prioritize precision over recall (rejecting ambiguous merges is preferred over incorrect merges):
1. Factual contradictions in actors, locations, dates, or actions automatically result in `same_event = False`.
2. Different occurrences of similar events (e.g. separate rocket launches or consecutive air strikes) must not be merged.
3. Diverse sources reporting the same event from different perspectives should be merged.
