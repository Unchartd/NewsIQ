import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.deps import require_admin
from app.main import app
from app.models.models import (
    Article,
    Category,
    Source,
    Story,
    StoryVersion,
    SynthesisArtifact,
)
from app.services.story_synthesis_service import story_synthesis_orchestrator


@pytest.fixture(autouse=True)
def override_admin_auth():
    """Override require_admin dependency to bypass JWT auth for admin tests."""
    mock_admin = MagicMockUser()
    app.dependency_overrides[require_admin] = lambda: mock_admin
    yield
    app.dependency_overrides.pop(require_admin, None)


class MagicMockUser:
    def __init__(self):
        self.id = uuid.uuid4()
        self.email = "admin@newsiq.io"
        self.role = "admin"


@pytest.mark.asyncio
async def test_story_synthesis_orchestrator_flow(mock_db_session):
    """Verify synthesis orchestrator saves artifacts and version snapshots correctly."""
    story_id = uuid.uuid4()

    # 1. Setup mock data returned by queries
    category = Category(id=uuid.uuid4(), slug="world", name="World News")
    source = Source(id=uuid.uuid4(), name="BBC", slug="bbc")
    story = Story(
        id=story_id,
        category_id=category.id,
        story_status="pending",
    )

    # Mock articles
    article1 = Article(
        id=uuid.uuid4(), source_id=source.id, title="A", description="A", content="A"
    )
    article2 = Article(
        id=uuid.uuid4(), source_id=source.id, title="B", description="B", content="B"
    )

    async def mock_execute_side_effect(stmt, params=None, *args, **kwargs):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []

        if "articleevent" in stmt_str or "article_event" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "synthesis_artifact" in stmt_str:
            res.scalar_one_or_none.return_value = None
        elif "storyarticle" in stmt_str or "article" in stmt_str:
            res.scalars.return_value.all.return_value = [article1, article2]
        elif "story" in stmt_str:
            res.scalar_one_or_none.return_value = story
        elif "category" in stmt_str:
            res.scalar_one_or_none.return_value = category
        elif "source" in stmt_str:
            res.scalar_one_or_none.return_value = source

        return res

    mock_db_session.execute.side_effect = mock_execute_side_effect

    # Mock AI Service & Feedback QA
    from app.services.ai_service import StorySummaryResponse

    mock_summary = StorySummaryResponse(
        headline="AI and ML Growth",
        one_line_summary="AI is growing fast.",
        short_summary="A short summary.",
        detailed_summary="A detailed summary of AI growth.",
        key_facts=["AI is fast", "ML is growing"],
        category="world",
    )

    from app.agents.feedback_agent import FeedbackReport

    mock_feedback = FeedbackReport(
        action="publish", score=0.95, explanation="Approved.", hallucination_detected=False
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
        # Run orchestrator
        await story_synthesis_orchestrator.synthesize_story(
            session=mock_db_session, story_id=story_id, trigger="manual_regenerate"
        )

    # Assert session methods are called to persist the version and artifacts
    assert mock_db_session.add.call_count >= 2  # StoryVersion and SynthesisArtifacts


def test_admin_rollback_endpoint():
    """Verify that POST /admin/pipeline/story/{story_id}/rollback/{version} works atomically."""
    client = TestClient(app)
    story_id = uuid.uuid4()
    version_number = 1

    # Mock the DB queries inside the rollback endpoint
    mock_version = StoryVersion(
        id=uuid.uuid4(),
        story_id=story_id,
        version_number=version_number,
        summary_artifact_id=uuid.uuid4(),
        timeline_artifact_id=uuid.uuid4(),
        kg_artifact_id=uuid.uuid4(),
        source_comparison_artifact_id=uuid.uuid4(),
        contradiction_artifact_id=uuid.uuid4(),
        pipeline_version="1.0.0",
        trigger="manual_regenerate",
    )

    mock_artifacts = [
        SynthesisArtifact(
            id=uuid.uuid4(),
            story_id=story_id,
            artifact_type="summary",
            payload={
                "headline": "Version 1 Headline",
                "one_line_summary": "One line 1",
                "short_summary": "Short 1",
                "detailed_summary": "Detailed 1",
                "key_facts": ["Fact 1"],
                "category": "world",
            },
            content_hash="hash1",
        ),
        SynthesisArtifact(
            id=uuid.uuid4(),
            story_id=story_id,
            artifact_type="timeline",
            payload=[],
            content_hash="hash2",
        ),
        SynthesisArtifact(
            id=uuid.uuid4(),
            story_id=story_id,
            artifact_type="contradictions",
            payload=[],
            content_hash="hash3",
        ),
        SynthesisArtifact(
            id=uuid.uuid4(),
            story_id=story_id,
            artifact_type="source_comparison",
            payload={},
            content_hash="hash4",
        ),
    ]

    mock_story = Story(id=story_id, headline="Current Headline", story_status="active")

    from unittest.mock import MagicMock

    # Mock DB executions
    mock_execute = AsyncMock()
    # Mock return values for: StoryVersion, Story, and SynthesisArtifacts queries
    mock_result_version = MagicMock()
    mock_result_version.scalar_one_or_none = MagicMock(return_value=mock_version)

    mock_result_story = MagicMock()
    mock_result_story.scalar_one_or_none = MagicMock(return_value=mock_story)

    mock_result_arts = MagicMock()
    mock_result_arts.scalars.return_value.all = MagicMock(return_value=mock_artifacts)

    mock_result_cat = MagicMock()
    mock_result_cat.scalar_one_or_none = MagicMock(
        return_value=Category(id=uuid.uuid4(), slug="world", name="World")
    )

    mock_execute.side_effect = [
        mock_result_version,
        mock_result_story,
        mock_result_arts,
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        mock_result_cat,
        AsyncMock(),
    ]

    with (
        patch("sqlalchemy.ext.asyncio.AsyncSession.execute", mock_execute),
        patch("sqlalchemy.ext.asyncio.AsyncSession.commit", AsyncMock()),
        patch("sqlalchemy.ext.asyncio.AsyncSession.flush", AsyncMock()),
        patch("app.services.cache_service.cache_service.invalidate_story", AsyncMock()),
    ):
        response = client.post(f"/api/v1/admin/pipeline/story/{story_id}/rollback/{version_number}")
        assert response.status_code == 200
        assert response.json()["version_number"] == version_number
        assert "successfully rolled back" in response.json()["message"]


@pytest.mark.asyncio
async def test_story_synthesis_transaction_decoupling():
    """Verify that synthesize_story commits after stage transitions to release DB connections."""
    from app.models.models import Category, Source, Story
    from app.services.story_synthesis_service import story_synthesis_orchestrator

    story_id = uuid.uuid4()
    mock_db_session = AsyncMock()

    category = Category(id=uuid.uuid4(), name="World", slug="world")
    source = Source(id=uuid.uuid4(), name="Test Source")
    story = Story(id=story_id, headline=None, story_status="pending", category_id=category.id)

    # Mock articles
    article1 = Article(
        id=uuid.uuid4(), source_id=source.id, title="A", description="A", content="A"
    )

    async def mock_execute_side_effect(stmt, params=None, *args, **kwargs):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []

        if "articleevent" in stmt_str or "article_event" in stmt_str:
            res.scalars.return_value.all.return_value = []
        elif "synthesis_artifact" in stmt_str:
            res.scalar_one_or_none.return_value = None
        elif "storyarticle" in stmt_str or "article" in stmt_str:
            res.scalars.return_value.all.return_value = [article1]
        elif "story" in stmt_str:
            res.scalar_one_or_none.return_value = story
        elif "category" in stmt_str:
            res.scalar_one_or_none.return_value = category
        elif "source" in stmt_str:
            res.scalar_one_or_none.return_value = source

        return res

    mock_db_session.execute.side_effect = mock_execute_side_effect

    # Mock AI Service & Feedback QA
    from app.services.ai_service import StorySummaryResponse
    mock_summary = StorySummaryResponse(
        headline="AI Growth",
        one_line_summary="AI is growing.",
        short_summary="A short summary.",
        detailed_summary="Detailed summary.",
        key_facts=["AI is growing"],
        category="world",
    )

    from app.agents.feedback_agent import FeedbackReport
    mock_feedback = FeedbackReport(
        action="publish", score=0.95, explanation="Approved.", hallucination_detected=False
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
        # Run orchestrator
        await story_synthesis_orchestrator.synthesize_story(
            session=mock_db_session, story_id=story_id, trigger="manual_regenerate"
        )

    # Assert session.commit was called after stage transitions
    # At least: once at start, after Stage 1, Stage 2, Stage 3, Stage 4, Stage 5, and at end.
    assert mock_db_session.commit.call_count >= 6

