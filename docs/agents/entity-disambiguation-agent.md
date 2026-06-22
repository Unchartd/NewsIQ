# Entity Disambiguation Agent

The **Entity Disambiguation Agent** canonicalizes raw entity mentions and resolves them to globally unique canonical entities.

## Triggers

This agent is invoked as a fallback when:
1. Deterministic database lookup fails (the entity mention name is not in the `canonical_entities` table).
2. The Redis resolution cache has expired or is a miss.
3. Standard Wikidata API lookup fails to return a matching Wikidata QID.

## Schema and Structure

The agent utilizes structured outputs matching the following Pydantic schema:

```python
class EntityDisambiguationSchema(BaseModel):
    canonical_name: str = Field(..., description="The standardized canonical name of the entity.")
    wikidata_id: str | None = Field(None, description="The Wikidata ID (QID) if found, otherwise null.")
    entity_type: str = Field(..., description="The correct entity category (e.g., PERSON, ORG, GPE, AGREEMENT).")
    explanation: str = Field(..., description="Reasoning/explanation behind this disambiguation.")
```

## Instructions

The agent is instructed to resolve ambiguity using the surrounding text:
1. Standardize variants of the same name (e.g., "Trump", "President Trump", "Donald Trump" -> "Donald Trump").
2. Correct entity type misclassifications (e.g., a "Memorandum of Understanding" should be classified as `AGREEMENT`, not `PERSON`).
3. Resolve Wikidata QIDs where possible; if uncertain, default to `null` to prevent wrong associations.
