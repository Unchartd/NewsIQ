"""AI service for story summarization, timeline generation, and difference engine using Gemini."""

import json
import logging
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

# Canonical category slugs the AI must choose from
CATEGORY_SLUGS = [
    "politics",
    "world",
    "business",
    "technology",
    "sports",
    "entertainment",
    "health",
    "science",
    "weather",
]


class TimelineEventSchema(BaseModel):
    date: str = Field(description="Date or time of the event, e.g. YYYY-MM-DD or time of day")
    description: str = Field(description="Summary of what happened at this point in the timeline")


class SourceDifferenceSchema(BaseModel):
    source_name: str = Field(description="Name of the news source/publisher, e.g. Reuters, BBC")
    unique_information: str = Field(
        description="Details mentioned ONLY by this source, or empty string"
    )
    missing_information: str = Field(
        description="Key details omitted by this source that others covered, or empty string"
    )
    contradictions: str = Field(
        description="Any factual contradictions or conflicting claims made by this source, or empty string"
    )


class StoryAIResponse(BaseModel):
    headline: str = Field(
        description="A highly neutral, objective, and non-clickbait headline summarizing the event"
    )
    one_line_summary: str = Field(description="A concise 1-sentence summary of the story")
    short_summary: str = Field(description="A short 1-paragraph summary (3-4 sentences)")
    detailed_summary: str = Field(
        description="A detailed multi-paragraph summary covering all angles and context"
    )
    key_facts: list[str] = Field(description="List of 3 to 6 key objective bullet points of fact")
    category: str = Field(
        description=(
            f"The single best-matching category slug for this story. "
            f"Must be one of: {', '.join(CATEGORY_SLUGS)}"
        )
    )
    timeline: list[TimelineEventSchema] = Field(
        description="Chronological timeline of events leading up to and during the story"
    )
    differences: list[SourceDifferenceSchema] = Field(
        description="Analysis of differences, biases, omissions, or contradictions per news source"
    )


class AIService:
    """Service to interact with Google Gemini for story processing."""

    def __init__(self):
        self.enabled = False
        if settings.GEMINI_API_KEY:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.enabled = True
            except Exception as e:
                logger.error("Failed to configure Google Gemini API: %s", e)
        else:
            logger.warning("GEMINI_API_KEY is not set. AI service will run in fallback mock mode.")

    def _generate_mock_response(self, articles: list[dict[str, Any]]) -> StoryAIResponse:
        """Generate a realistic mock response for local testing without API key."""
        primary_article = articles[0] if articles else {"title": "Global Event", "content": ""}
        title = primary_article.get("title") or "Major News Event"
        source_name = primary_article.get("source_name") or "Reuters"

        # Build list of sources
        sources = list(set(a.get("source_name", "Unknown Source") for a in articles))

        mock_differences = []
        for src in sources:
            mock_differences.append(
                SourceDifferenceSchema(
                    source_name=src,
                    unique_information=f"{src} highlighted specific context regarding local regulatory implications.",
                    missing_information=f"{src} did not cover the international diplomatic responses covered by other sources.",
                    contradictions="",
                )
            )

        return StoryAIResponse(
            headline=f"[Mock] {title}",
            one_line_summary=f"This is a mock 1-sentence summary of the story involving {len(articles)} articles from {', '.join(sources)}.",
            short_summary=(
                f"This is a short mock summary of the story. It compiles insights from {len(articles)} different "
                f"publishers including {', '.join(sources)}. The story covers the key event, its immediate impacts, "
                "and ongoing developments as of today."
            ),
            detailed_summary=(
                f"This is a detailed mock multi-paragraph summary.\n\n"
                f"Paragraph 1: Background. The event began with initial reports from {source_name} regarding the incident. "
                "Local authorities responded immediately and set up a response team.\n\n"
                f"Paragraph 2: Global Impact. Other publishers like {', '.join(sources)} soon added their coverage. "
                "Market indices fluctuated slightly in response, and industry analysts released preliminary reports.\n\n"
                "Paragraph 3: Outlook. Going forward, investigators are looking into the root causes. "
                "A formal briefing is expected by the end of the week."
            ),
            key_facts=[
                f"Event first reported by {source_name} with subsequent coverage from {len(sources)} publishers.",
                "Primary impact includes regulatory scrutiny and economic market reaction.",
                "Investigation is underway with preliminary results expected within days.",
            ],
            category="world",
            timeline=[
                TimelineEventSchema(
                    date="08:00 AM UTC",
                    description="Initial incident occurs and is first reported.",
                ),
                TimelineEventSchema(
                    date="10:30 AM UTC",
                    description="Emergency response teams and investigators arrive at the scene.",
                ),
                TimelineEventSchema(
                    date="02:00 PM UTC",
                    description="Official joint press conference held by authorities.",
                ),
            ],
            differences=mock_differences,
        )

    async def analyze_story(self, articles: list[dict[str, Any]]) -> StoryAIResponse:
        """Analyze a collection of articles about the same story and generate structured AI summaries, timeline, and differences."""
        if not articles:
            raise ValueError("No articles provided for AI analysis.")

        if not self.enabled:
            return self._generate_mock_response(articles)

        try:
            # Build clean prompt text representing the set of articles
            articles_text = ""
            for i, art in enumerate(articles):
                articles_text += (
                    f"--- ARTICLE {i + 1} ---\n"
                    f"Source: {art.get('source_name', 'Unknown')}\n"
                    f"Published: {art.get('published_at', 'Unknown')}\n"
                    f"Title: {art.get('title', 'No Title')}\n"
                    f"Content: {art.get('content', '')[:3000]}\n\n"
                )

            prompt = (
                "You are an objective, expert news intelligence analyst.\n"
                "Analyze the following articles about a single news event. "
                "Your output must be completely neutral, free of editorializing, clickbait, or political bias.\n\n"
                f"{articles_text}\n"
                "Synthesize this information into a single cohesive story, extracting the headline, summaries at "
                "3 detail levels (one-line, short, detailed), key bulleted facts, a chronological timeline, "
                "and an analysis of source differences/contradictions.\n"
                f"For the 'category' field, choose exactly one slug from: {', '.join(CATEGORY_SLUGS)}.\n"
                "For timeline dates, use ISO 8601 format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) whenever possible."
            )

            # Query Gemini using structured JSON schema output
            model = genai.GenerativeModel(settings.SUMMARIZATION_MODEL)
            response = await model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=StoryAIResponse,
                    temperature=0.1,
                ),
            )

            # Parse response JSON
            data = json.loads(response.text)
            # Validate category is one of the allowed slugs
            if data.get("category") not in CATEGORY_SLUGS:
                data["category"] = "world"
            return StoryAIResponse(**data)

        except Exception as e:
            logger.error("Failed to generate AI story analysis: %s. Falling back to mock.", e)
            return self._generate_mock_response(articles)


ai_service = AIService()
