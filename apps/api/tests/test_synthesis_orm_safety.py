import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import Article, ArticleEvent, Category, Source, Story, StoryEntity
from app.schemas.synthesis_context import (
    ArticleContext,
    EntityContext,
    EventContext,
    StoryContext,
)
from app.services.story_synthesis_service import (
    map_article_to_context,
    map_entity_to_context,
    map_event_to_context,
    map_story_to_context,
    story_synthesis_orchestrator,
)


def test_dto_mappers_no_relationship_traversal():
    """Verify that mapping ORM models to DTO contexts does not traverse lazy-loaded relations."""
    story_id = uuid.uuid4()
    category_id = uuid.uuid4()
    source_id = uuid.uuid4()
    article_id = uuid.uuid4()

    # Instantiate ORM objects without relationship attributes populated
    story = Story(
        id=story_id,
        category_id=category_id,
        headline="Test Story",
        story_status="pending",
        first_seen_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    # We do NOT assign story.category or story.articles relationship

    article = Article(
        id=article_id,
        source_id=source_id,
        title="Test Article Title",
        description="Test Desc",
        content="Test Content",
        url="http://example.com",
        published_at=datetime.utcnow(),
    )
    # We do NOT assign article.source or article.events relationship

    event = ArticleEvent(
        id=uuid.uuid4(),
        article_id=article_id,
        event_type="protest",
        event_type_canonical="Protest",
        location="London",
        event_time=datetime.utcnow(),
        event_time_raw="2026-07-14",
        confidence=0.9,
        numbers={"casualties": 0},
        actors=["Activists"],
        targets=["Government"],
        event_fingerprint="fingerprint123",
        created_at=datetime.utcnow(),
    )
    # We do NOT assign event.article relationship

    story_entity = StoryEntity(
        id=uuid.uuid4(),
        story_id=story_id,
        canonical_entity_id=None,
        entity_type="person",
        entity_value="John Doe",
    )
    # We do NOT assign story_entity.canonical_entity relationship

    # Map Story
    story_dto = map_story_to_context(story, "world")
    assert isinstance(story_dto, StoryContext)
    assert story_dto.headline == "Test Story"
    assert story_dto.category_slug == "world"

    # Map Article
    art_dto = map_article_to_context(article)
    assert isinstance(art_dto, ArticleContext)
    assert art_dto.title == "Test Article Title"
    assert art_dto.source_id == source_id

    # Map Event
    evt_dto = map_event_to_context(event)
    assert isinstance(evt_dto, EventContext)
    assert evt_dto.event_type == "protest"
    assert evt_dto.event_fingerprint == "fingerprint123"

    # Map Entity (with no canonical_entity loaded)
    ent_dto = map_entity_to_context(story_entity)
    assert isinstance(ent_dto, EntityContext)
    assert ent_dto.entity_value == "John Doe"
    assert ent_dto.canonical_name is None


@pytest.mark.asyncio
async def test_synthesis_flow_orm_safety_mocked(mock_db_session):
    """Verify synthesis orchestrator runs using DTOs without raising MissingGreenlet."""
    story_id = uuid.uuid4()
    category = Category(id=uuid.uuid4(), slug="world", name="World")
    source = Source(id=uuid.uuid4(), name="BBC", slug="bbc")
    story = Story(id=story_id, category_id=category.id, story_status="pending")
    article = Article(id=uuid.uuid4(), source_id=source.id, title="Test title")
    article_event = ArticleEvent(id=uuid.uuid4(), article_id=article.id, event_fingerprint="ep1")
    story_entity = StoryEntity(
        id=uuid.uuid4(), story_id=story_id, entity_type="person", entity_value="Jane"
    )

    # Setup database mocks
    async def mock_execute_side_effect(stmt, *args, **kwargs):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []
        res.all.return_value = []

        if "story_entities" in stmt_str or "storyentity" in stmt_str:
            res.scalars.return_value.all.return_value = [story_entity]
        elif "articleevent" in stmt_str or "article_event" in stmt_str:
            res.scalars.return_value.all.return_value = [article_event]
        elif "storyarticle" in stmt_str or "article" in stmt_str:
            res.scalars.return_value.all.return_value = [article]
        elif "story" in stmt_str:
            res.scalar_one_or_none.return_value = story
        elif "category" in stmt_str:
            res.scalar_one_or_none.return_value = category
        elif "source" in stmt_str:
            res.scalars.return_value.all.return_value = [source]
            res.scalar_one_or_none.return_value = source

        return res

    mock_db_session.execute.side_effect = mock_execute_side_effect

    # Mock AI/Agent calls
    from app.services.ai_service import StorySummaryResponse

    mock_summary = StorySummaryResponse(
        headline="Title",
        one_line_summary="One line",
        short_summary="Short",
        detailed_summary="Detailed",
        key_facts=["Fact"],
        category="world",
    )

    from app.agents.feedback_agent import FeedbackReport

    mock_feedback = FeedbackReport(
        action="publish", score=0.9, explanation="OK", hallucination_detected=False
    )

    with (
        patch(
            "app.services.ai_service.AIService.summarize_story_from_kg",
            AsyncMock(return_value=mock_summary),
        ),
        patch(
            "app.agents.feedback_agent.evaluate_story_quality",
            AsyncMock(return_value=mock_feedback),
        ),
        patch(
            "app.services.vector_service.vector_service.retrieve_vectors",
            AsyncMock(return_value={}),
        ),
        patch(
            "app.services.story_synthesis_service.story_synthesis_orchestrator.record_trace",
            AsyncMock(),
        ),
    ):
        # Trigger synthesis
        await story_synthesis_orchestrator.synthesize_story(
            session=mock_db_session, story_id=story_id, trigger="manual_regenerate"
        )

    # Verify that add was called for StoryVersion and SynthesisArtifacts
    assert mock_db_session.add.call_count >= 2
