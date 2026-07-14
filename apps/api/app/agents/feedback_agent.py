import logging
import math
from typing import Any

from agno.agent import Agent
from pydantic import BaseModel, Field

from app.agents.base_agent import get_default_model, run_agent_with_observability
from app.schemas.synthesis_context import ArticleContext, EventContext, StoryContext
from app.services.vector_service import vector_service

logger = logging.getLogger(__name__)


class FeedbackReport(BaseModel):
    action: str = Field(
        ..., description="Action to take: 'publish', 'regenerate_summary', 'request_human_review'"
    )
    score: float = Field(..., description="Quality score between 0.0 (unusable) and 1.0 (perfect)")
    explanation: str = Field(..., description="Detailed rationale behind the action decision")
    hallucination_detected: bool = Field(
        ..., description="True if summary contains claims not supported by the KG"
    )
    hallucinated_claims: list[str] = Field(
        default_factory=list, description="List of hallucinated claims found"
    )
    missing_elements: list[str] = Field(
        default_factory=list,
        description="List of critical elements (facts/entities) missing from the summary",
    )
    targeted_corrections: list[str] = Field(
        default_factory=list,
        description="Section-level instructions for correction (e.g. 'Update Key Facts with missing entity X')",
    )


feedback_llm_agent = Agent(
    name="Feedback QA Agent",
    model=get_default_model(),
    instructions=[
        "You are a Senior Editor and QA Fact-Checker for a high-quality automated news platform.",
        "Your role is to check the generated summary against the Knowledge Graph, contradictions, and timeline.",
        "Specifically:",
        "1. Identify any claims in the summary that are not supported by the Knowledge Graph (hallucinations).",
        "2. Identify any critical omissions of facts from the timeline or contradictions list.",
        "3. Decide whether the summary can be published as-is ('publish'), needs a minor targeted correction ('regenerate_summary'), or is too flawed/complex and requires editorial intervention ('request_human_review').",
        "If you request regeneration, write a clear instruction in the 'targeted_corrections' field specifying what needs to be fixed. Be concise.",
    ],
    output_schema=FeedbackReport,
)


def calculate_hhi(articles: list[Any]) -> float:
    """Calculate the Herfindahl-Hirschman Index (HHI) for source representation.

    A higher HHI indicates single-source dominance (max 1.0).
    """
    if not articles:
        return 1.0
    source_counts: dict[str, int] = {}
    for art in articles:
        src_id = str(art.source_id) if art.source_id else "unknown"
        source_counts[src_id] = source_counts.get(src_id, 0) + 1
    total = len(articles)
    hhi = sum((count / total) ** 2 for count in source_counts.values())
    return hhi


async def check_clustering_similarity(articles: list[Any]) -> float:
    """Calculate the minimum pairwise cosine similarity of articles in the cluster."""
    if len(articles) <= 1:
        return 1.0

    art_ids = [str(art.id) for art in articles]
    try:
        vectors = await vector_service.retrieve_vectors(art_ids)
    except Exception as e:
        logger.warning("Failed to retrieve vectors for similarity check: %s", e)
        vectors = {}

    if len(vectors) < 2:
        return 1.0

    min_sim = 1.0
    vec_keys = list(vectors.keys())

    def cosine_similarity(v1, v2):
        dot = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    for i in range(len(vec_keys)):
        for j in range(i + 1, len(vec_keys)):
            sim = cosine_similarity(vectors[vec_keys[i]], vectors[vec_keys[j]])
            if sim < min_sim:
                min_sim = sim
    return min_sim


def check_missing_entities(kg: dict, summary_text: str) -> list[str]:
    """Identify key entities in the KG that are missing from the summary."""
    missing = []
    summary_lower = summary_text.lower()
    nodes = kg.get("nodes", [])

    # Check top entities based on degree/relevance (if specified, else all key entities)
    for node in nodes:
        label = node.get("label", "")
        ntype = node.get("type", "").lower()
        # Focus on Person, Organization, Location types
        if ntype in ("person", "organization", "location", "actor", "target") and len(label) > 2:
            if label.lower() not in summary_lower:
                missing.append(label)
    return missing


async def evaluate_story_quality(
    story: StoryContext,
    articles: list[ArticleContext],
    kg: dict,
    contradictions: list[dict],
    timeline: list[dict],
    summary_text: str,
    category_slug: str,
    article_events: list[EventContext] = None,
    regeneration_count: int = 0,
) -> FeedbackReport:
    """Evaluate story synthesis quality using programmatic and conditional LLM gates."""

    # 1. Run Programmatic Checks
    hhi = calculate_hhi(articles)
    min_similarity = await check_clustering_similarity(articles)
    missing_ents = check_missing_entities(kg, summary_text)

    # Calculate unique event IDs to detect multi-event leakage using pre-loaded article events
    if article_events:
        unique_events = len(
            {
                evt.event_fingerprint
                for evt in article_events
                if getattr(evt, "event_fingerprint", None)
            }
        )
    else:
        unique_events = 0

    # Determine base programmatic score
    prog_score = 1.0
    explanation_parts = []

    if hhi > 0.6:
        prog_score -= 0.15
        explanation_parts.append(f"Low source diversity (HHI: {hhi:.2f})")

    if min_similarity < 0.65:
        prog_score -= 0.15
        explanation_parts.append(f"Weak clustering (Min Cosine Sim: {min_similarity:.2f})")

    if len(missing_ents) > 3:
        prog_score -= 0.15
        explanation_parts.append(f"Missing key entities: {', '.join(missing_ents[:3])}")

    if unique_events > 1:
        prog_score -= 0.10
        explanation_parts.append(f"Multiple canonical events in cluster (Count: {unique_events})")

    # Prevent infinite loops of regeneration
    if regeneration_count >= 1:
        # If we already regenerated once, any further failure means human review
        if prog_score < 0.85:
            return FeedbackReport(
                action="request_human_review",
                score=prog_score,
                explanation=f"Fails programmatic check after regeneration. Issues: {'; '.join(explanation_parts) or 'None'}",
                hallucination_detected=False,
                missing_elements=missing_ents,
            )

    # 2. Gate rules to decide if we need LLM verification
    is_high_stakes = category_slug in ("politics", "business", "health", "world")
    needs_llm = is_high_stakes or (prog_score < 0.85) or (len(contradictions) > 0)

    if not needs_llm:
        # Programmatic green-light
        return FeedbackReport(
            action="publish",
            score=max(prog_score, 0.0),
            explanation="Passed programmatic quality checks with high score.",
            hallucination_detected=False,
        )

    # 3. LLM QA fact-checking (grounded verification)
    logger.info("Triggering LLM Feedback QA check for story %s.", story.id)

    prompt = f"""
    Review the following news story summaries and verify against the ground truth Knowledge Graph and contradictions list.

    Generated Summary text:
    {summary_text}

    Ground Truth Knowledge Graph:
    {kg}

    Contradictions Identified:
    {contradictions}

    Timeline:
    {timeline}

    Evaluate the quality and accuracy. If the summary contains claims not present or contradictory to the KG, flag it as hallucination.
    """

    try:
        run_output = await run_agent_with_observability(
            agent=feedback_llm_agent, prompt=prompt, stage="feedback_agent", story_id=str(story.id)
        )

        # Parse result
        if isinstance(run_output.content, FeedbackReport):
            report = run_output.content
        elif hasattr(run_output, "parsed") and isinstance(run_output.parsed, FeedbackReport):
            report = run_output.parsed
        elif isinstance(run_output.content, str):
            import json

            data = json.loads(run_output.content)
            report = FeedbackReport.model_validate(data)
        else:
            raise ValueError("Invalid output format from feedback agent")

        # If LLM suggests regeneration but we have already run it once, override to request_human_review
        if report.action == "regenerate_summary" and regeneration_count >= 1:
            report.action = "request_human_review"
            report.explanation = f"(Overridden due to max regeneration count) {report.explanation}"

        return report

    except Exception as e:
        logger.error(
            "LLM Feedback QA agent call failed: %s. Falling back to programmatic verdict.", e
        )
        # Fallback to programmatic verdict
        fallback_action = "publish" if prog_score >= 0.7 else "request_human_review"
        return FeedbackReport(
            action=fallback_action,
            score=max(prog_score, 0.0),
            explanation=f"LLM check failed ({e}). Fallback programmatic action taken.",
            hallucination_detected=False,
        )
