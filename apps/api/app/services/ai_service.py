"""AI service — story summarization using unified LLM Gateway."""

import logging
from typing import Any

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


# Canonical category slugs the AI must choose from
CATEGORY_SLUGS = [
    "politics",
    "world",
    "business",
    "technology",
    "sports",
    "entertainment",
    "lifestyle",
    "travel",
    "education",
    "health",
    "science",
    "weather",
]


# Values a model emits when it echoes the JSON schema instead of answering it.
# Production published a story whose headline, all three summaries and only key
# fact were each the literal word "string" — the schema's type name. Every field
# was a valid non-empty string, so Pydantic accepted it and synthesis recorded
# decision=success against a knowledge graph of 30 nodes and 12 timeline events.
_PLACEHOLDER_VALUES = frozenset(
    {
        "string",
        "str",
        "text",
        "summary",
        "headline",
        "n/a",
        "na",
        "none",
        "null",
        "todo",
        "tbd",
        "example",
        "lorem ipsum",
    }
)


class StorySummaryResponse(BaseModel):
    # The length floors are what make a schema echo fail validation rather than
    # reach a reader. They are deliberately far below any real summary, so they
    # catch degenerate output without rejecting a genuinely terse story.
    headline: str = Field(
        min_length=12,
        description="A highly neutral, objective, and non-clickbait headline summarizing the event",
    )
    one_line_summary: str = Field(
        min_length=25,
        max_length=400,
        description="A concise 1-sentence summary of the story",
    )
    short_summary: str = Field(
        min_length=60, description="A short 1-paragraph summary (3-4 sentences)"
    )
    detailed_summary: str = Field(
        min_length=150,
        description="A detailed multi-paragraph summary covering all angles and context",
    )
    key_facts: list[str] = Field(description="List of 3 to 6 key objective bullet points of fact")
    category: str = Field(
        description=(
            f"The single best-matching category slug for this story. "
            f"Must be one of: {', '.join(CATEGORY_SLUGS)}"
        )
    )

    @model_validator(mode="after")
    def _reject_placeholder_or_duplicated_summaries(self) -> "StorySummaryResponse":
        """Fail validation so the gateway retries and then falls back.

        Two failure modes reach here, and both used to be stored as successes:
        a model echoing the schema ("string" in every field), and a model
        emitting the same text for all three tiers, which puts a full paragraph
        behind a tab labelled "1-line".
        """
        for name in ("headline", "one_line_summary", "short_summary", "detailed_summary"):
            value = getattr(self, name).strip()
            if value.lower().rstrip(".") in _PLACEHOLDER_VALUES:
                raise ValueError(
                    f"{name} is the placeholder {value!r} — the model echoed the schema "
                    f"instead of summarising the story"
                )

        if self.one_line_summary.strip() == self.short_summary.strip():
            raise ValueError("one_line_summary and short_summary are identical")
        if self.short_summary.strip() == self.detailed_summary.strip():
            raise ValueError("short_summary and detailed_summary are identical")

        return self


class AIService:
    """Story analysis and summarization using LLM Gateway."""

    def _build_summary_prompt(
        self,
        kg: dict[str, Any],
        contradictions: list[dict[str, Any]],
        timeline: list[dict[str, Any]],
        source_comparisons: list[dict[str, Any]],
    ) -> str:
        import json

        kg_str = json.dumps(kg, indent=2)
        contras_str = json.dumps(contradictions, indent=2)
        timeline_str = json.dumps(timeline, indent=2)
        source_comp_str = json.dumps(source_comparisons, indent=2)

        schema = (
            "{\n"
            '  "headline": "<neutral headline>",\n'
            '  "one_line_summary": "<1-sentence summary>",\n'
            '  "short_summary": "<1-paragraph summary>",\n'
            '  "detailed_summary": "<multi-paragraph detailed summary>",\n'
            '  "key_facts": ["fact1", "fact2", "fact3"],\n'
            '  "category": "<one of: politics, world, business, technology, sports, entertainment, lifestyle, travel, education, health, science, weather>"\n'
            "}"
        )

        return (
            "You are an objective, expert news intelligence analyst.\n"
            "Generate a highly objective, neutral story summary using ONLY the structured event knowledge graph, timeline, source comparison, and contradictions below.\n"
            "Do NOT invent or extrapolate facts not present in this structured knowledge.\n\n"
            f"--- KNOWLEDGE GRAPH ---\n{kg_str}\n\n"
            f"--- TIMELINE OF EVENTS ---\n{timeline_str}\n\n"
            f"--- SOURCE COVERAGE & DIFFERENCES ---\n{source_comp_str}\n\n"
            f"--- DETECTED CONTRADICTIONS ---\n{contras_str}\n\n"
            f"For the 'category' field, choose exactly one slug from: {', '.join(CATEGORY_SLUGS)}.\n\n"
            "Respond with ONLY a valid JSON object matching this exact schema (no markdown, no code blocks):\n"
            f"{schema}"
        )

    async def summarize_story_from_kg(
        self,
        kg: dict[str, Any],
        contradictions: list[dict[str, Any]],
        timeline: list[dict[str, Any]],
        source_comparisons: list[dict[str, Any]],
    ) -> StorySummaryResponse:
        """Summarize story from its knowledge graph and analysis inputs using the central AI Gateway."""
        import json

        from app.ai.gateway import ai_gateway
        from app.core.trace import story_id_ctx

        story_id = story_id_ctx.get("")

        kg_str = json.dumps(kg, indent=2, default=str)
        contras_str = json.dumps(contradictions, indent=2, default=str)
        timeline_str = json.dumps(timeline, indent=2, default=str)
        source_comp_str = json.dumps(source_comparisons, indent=2, default=str)

        source_count = 0
        if isinstance(kg, dict) and "nodes" in kg:
            source_count = len([n for n in kg["nodes"] if n.get("type") == "source"])

        prompt_variables = {
            "knowledge_graph": kg_str,
            "timeline": timeline_str,
            "contradictions": contras_str,
            "source_comparisons": source_comp_str,
            "category": f"Choose from: {', '.join(CATEGORY_SLUGS)}",
            "source_count": source_count,
        }

        logger.info("Summarizing story from KG via central AI Gateway.")
        response = await ai_gateway.generate_stage(
            stage="summary_generation",
            prompt_variables=prompt_variables,
            schema=StorySummaryResponse,
            story_id=story_id,
        )

        if response.parsed:
            return response.parsed
        raise RuntimeError("AI Gateway failed to return a validated StorySummaryResponse.")

    def _generate_mock_summary_response(
        self,
        kg: dict[str, Any],
        contradictions: list[dict[str, Any]],
        timeline: list[dict[str, Any]],
        source_comparisons: list[dict[str, Any]],
    ) -> StorySummaryResponse:
        """Mock fallback for story summarization."""
        title = "Major News Event"
        if isinstance(kg, dict):
            if "nodes" in kg:
                for node in kg["nodes"]:
                    if node.get("type") == "event":
                        title = node.get("label") or node.get("properties", {}).get(
                            "name", "Major News Event"
                        )
                        break
            elif "event" in kg:
                title = kg["event"].get("name", "Major News Event")
        return StorySummaryResponse(
            headline=f"[Mock] {title}",
            one_line_summary="[Mock] Story summary based on structured event knowledge graph.",
            short_summary=f"[Mock] Short summary of event: {title}.",
            detailed_summary=f"[Mock] Detailed summary covering: {title}.\nTimeline events: {len(timeline)}.\nContradictions: {len(contradictions)}.",
            key_facts=[
                f"[Mock] Structured event contains {len(timeline)} timeline items.",
                f"[Mock] Analyzed {len(source_comparisons)} source comparisons.",
            ],
            category="world",
        )


ai_service = AIService()
