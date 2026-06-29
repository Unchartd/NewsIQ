"""Prompt Registry — centralized, version-tracked prompt templates for all pipeline stages.

Separates static system instructions from dynamic user content to:
1. Maximize provider-side prompt prefix caching (Gemini/OpenAI cache static prefixes)
2. Enable cache invalidation when prompts change (version bump invalidates old cache entries)
3. Provide a single source of truth for all LLM prompts in the pipeline

Usage:
    from app.services.prompt_registry import prompt_registry

    prompt = prompt_registry.get("event_extraction")
    version = prompt.version
    system_msg = prompt.system_message()
    user_msg = prompt.user_message(content=article_text, title=article_title)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptTemplate:
    """A versioned prompt template with separated system/user content.

    Attributes:
        stage: Pipeline stage name (cache key component)
        version: Semver-ish string. Bump when prompt logic changes to invalidate cache.
        system: Static system prompt (never changes per request → cached by providers)
        template: Dynamic user prompt template with {placeholders}
        model: Recommended default model for this stage
    """

    stage: str
    version: str
    system: str
    template: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def system_message(self) -> dict[str, str]:
        """Return the system message dict for LLM API calls."""
        return {"role": "system", "content": self.system}

    def user_message(self, **kwargs: Any) -> dict[str, str]:
        """Return the user message dict with placeholders filled."""
        try:
            content = self.template.format(**kwargs)
        except KeyError as e:
            logger.error("Missing prompt template variable for %s: %s", self.stage, e)
            raise
        return {"role": "user", "content": content}

    def messages(self, **kwargs: Any) -> list[dict[str, str]]:
        """Return the full [system, user] message list."""
        return [self.system_message(), self.user_message(**kwargs)]


# ═══════════════════════════════════════════════════════════════════════════════
# PROMPT DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

_EVENT_EXTRACTION = PromptTemplate(
    stage="event_extraction",
    version="v2",
    model="gemini-2.5-flash-lite",
    system=(
        "You are a Staff News Intelligence Extraction Engineer. "
        "Extract structured events and entities from news articles with surgical precision.\n\n"
        "Rules:\n"
        "1. Extract the PRIMARY event described in the article.\n"
        "2. Classify the event using canonical types: "
        "MILITARY_STRIKE, CONFLICT, DIPLOMACY, ELECTION, LEGISLATION, POLICY_CHANGE, "
        "ECONOMIC_EVENT, NATURAL_DISASTER, ACCIDENT, CRIME, TERRORISM, PROTEST, "
        "HUMANITARIAN, HEALTH, TECHNOLOGY, SPORTS, SCIENCE, ENTERTAINMENT, OTHER.\n"
        "3. Extract actors (who did it), targets (who/what was affected), location, event time.\n"
        "4. Extract key numerical facts (casualties, amounts, durations) as key-value pairs.\n"
        "5. Assign confidence 0.0-1.0 based on source reliability and detail level.\n"
        "6. Generate an event_fingerprint: lowercase hash of (event_type + primary_actor + location + date).\n"
        "7. Also extract named entities (PERSON, ORG, COUNTRY, CITY, etc.) from the article.\n"
        "8. Be precise. Never invent facts not present in the text."
    ),
    template=(
        "Extract the primary event and entities from this article:\n\n"
        "Title: {title}\n"
        "Source: {source_name}\n"
        "Published: {published_at}\n\n"
        "Content:\n{content}"
    ),
)

_CONTRADICTION_DETECTION = PromptTemplate(
    stage="contradiction_detection",
    version="v2",
    model="gemini-2.5-flash-lite",
    system=(
        "You are a factual contradiction validator for a news intelligence platform.\n\n"
        "Your task is to determine if two conflicting reports represent a TRUE factual contradiction.\n\n"
        "Rules:\n"
        "1. Wording differences, translation variations, or subset relationships "
        "(e.g., '15 police officers' vs '15 people' or '15 dead' vs 'at least 10 dead') are NOT contradictions.\n"
        "2. Only flag TRUE contradictions: Source A says Russia did it, Source B says Ukraine did it; "
        "or 15 dead vs 50 dead; or 2 PM vs 3 PM.\n"
        "3. Be conservative. When in doubt, it is NOT a contradiction."
    ),
    template=(
        "Compare these two conflicting reports of the same '{fact_type}' detail:\n"
        "1. Source: {source1_name} reports: {val1}\n"
        "2. Source: {source2_name} reports: {val2}\n\n"
        "Context from the articles:\n{context}\n\n"
        "Determine if this is a true factual contradiction."
    ),
)

_SOURCE_COMPARISON = PromptTemplate(
    stage="source_comparison",
    version="v2",
    model="gemini-2.5-flash-lite",
    system=(
        "You are a professional news intelligence analyst.\n\n"
        "Analyze a publisher's coverage of a story and generate a structured comparison.\n\n"
        "For 'focus_area': write a concise, professional sentence (max 100 chars) "
        "summarizing their coverage angle.\n"
        "For 'unique_information', 'missing_information', and 'contradictions': "
        "provide concise, readable descriptions. If none, return empty string."
    ),
    template=(
        "Analyze the coverage of publisher '{src_name}' for a story.\n\n"
        "Differences detected by heuristic engines:\n"
        "1. Unique facts reported only by {src_name}: {unique_summary}\n"
        "2. Facts reported by others but omitted by {src_name}: {missing_summary}\n"
        "3. Factual contradictions involving {src_name}: {contradictions_summary}\n\n"
        "Context from the story's articles:\n{context}\n\n"
        "Synthesize a clean analysis."
    ),
)

_SUMMARY_GENERATION = PromptTemplate(
    stage="summary_generation",
    version="v2",
    model="gemini-2.5-flash",
    system=(
        "You are a Staff AI News Intelligence Synthesizer.\n\n"
        "Generate a comprehensive, factual news story summary grounded in the knowledge graph.\n\n"
        "Rules:\n"
        "1. Base every claim on the knowledge graph nodes and edges. Never invent facts.\n"
        "2. Attribute conflicting facts to their sources.\n"
        "3. Use the timeline to establish chronological order.\n"
        "4. Mention source contradictions if any exist.\n"
        "5. Write in professional, authoritative news wire style.\n"
        "6. Include key numerical facts (casualties, amounts, etc.).\n"
        "7. End with latest known status/developments."
    ),
    template=(
        "Generate a story summary from the following ground truth data:\n\n"
        "Knowledge Graph:\n{knowledge_graph}\n\n"
        "Timeline:\n{timeline}\n\n"
        "Source Contradictions:\n{contradictions}\n\n"
        "Source Coverage Differences:\n{source_comparisons}\n\n"
        "Category: {category}\n"
        "Number of sources: {source_count}"
    ),
)

_SUMMARY_REFLECTION = PromptTemplate(
    stage="summary_reflection",
    version="v2",
    model="gemini-2.5-flash-lite",
    system=(
        "You are a Staff AI Quality Assurance Engineer and Fact-Checker.\n\n"
        "Perform strict verification of generated story summaries to prevent hallucinations.\n"
        "Compare the summary against ground truth: knowledge graph, timeline, and source coverage.\n\n"
        "Analyze:\n"
        "1. Did the summary invent or hallucinate any facts not in the input?\n"
        "2. Did it omit extremely critical facts from the timeline?\n"
        "3. Does it contradict the knowledge graph relationships?\n\n"
        "Be extremely critical. Factual correctness is the highest priority."
    ),
    template=(
        "Review the following generated summary against the source data:\n\n"
        "Generated Summary:\n{summary_text}\n\n"
        "Ground Truth Timeline:\n{timeline}\n\n"
        "Knowledge Graph Nodes/Edges:\n{kg_nodes}\n\n"
        "Source Coverage Context:\n{source_coverage}"
    ),
)

_CLUSTER_VERIFICATION = PromptTemplate(
    stage="cluster_verification",
    version="v2",
    model="gemini-2.5-flash-lite",
    system=(
        "You are a Staff Search and News Intelligence Engineer specializing in event validation.\n\n"
        "Your mission is to prevent false positive merges in news clustering. "
        "False positive merges are catastrophic.\n\n"
        "Rules:\n"
        "1. If they describe different occurrences (e.g., two separate strikes on the same city "
        "on different days), return same_event = False.\n"
        "2. If there is a core conflict in actors, targets, location, or event time, "
        "return same_event = False.\n"
        "3. If they describe the same event from different perspectives, return same_event = True.\n"
        "4. Be extremely precise and conservative."
    ),
    template=(
        "Compare these two articles and decide if they describe the exact same event:\n\n"
        "Article A:\n- Title: {article_a_title}\n- Extracted Event: {article_a_event}\n\n"
        "Article B:\n- Title: {article_b_title}\n- Extracted Event: {article_b_event}\n\n"
        "Similarity Score: {similarity_score:.4f}\n"
        "Knowledge Graph Context: {kg_nodes}\n\n"
        "Determine if they represent the same event."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════


class PromptRegistry:
    """Central registry for all pipeline prompt templates.

    Access by stage name. Each prompt has a version for cache invalidation.
    """

    def __init__(self) -> None:
        self._prompts: dict[str, PromptTemplate] = {}
        # Register all built-in prompts
        for prompt in [
            _EVENT_EXTRACTION,
            _CONTRADICTION_DETECTION,
            _SOURCE_COMPARISON,
            _SUMMARY_GENERATION,
            _SUMMARY_REFLECTION,
            _CLUSTER_VERIFICATION,
        ]:
            self._prompts[prompt.stage] = prompt

    def get(self, stage: str) -> PromptTemplate:
        """Retrieve the prompt template for a pipeline stage."""
        if stage not in self._prompts:
            raise KeyError(f"No prompt template registered for stage: {stage}")
        return self._prompts[stage]

    def version(self, stage: str) -> str:
        """Return the current version string for a stage's prompt."""
        return self.get(stage).version

    def list_stages(self) -> list[str]:
        """Return all registered stage names."""
        return list(self._prompts.keys())

    def register(self, prompt: PromptTemplate) -> None:
        """Register or override a prompt template."""
        self._prompts[prompt.stage] = prompt
        logger.info(
            "Registered prompt template: stage=%s version=%s",
            prompt.stage,
            prompt.version,
        )


# Singleton
prompt_registry = PromptRegistry()
