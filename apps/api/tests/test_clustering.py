"""Unit tests for the story clustering service."""

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import Article
from app.services.ai_service import SourceDifferenceSchema, StoryAIResponse, TimelineEventSchema
from app.services.clustering_service import clustering_service


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.analyze_story")
@patch("app.services.ner_service.ner_service.extract_entities")
@patch("app.services.vector_service.vector_service.client")
async def test_run_batch_clustering(
    mock_qdrant_client, mock_extract_entities, mock_analyze_story, mock_db_session
):
    """Verify that batch clustering groups articles, creates stories, and runs AI/NER synthesis."""
    # 1. Setup mock unclustered articles
    article_id_1 = uuid.uuid4()
    article_id_2 = uuid.uuid4()

    art1 = Article(
        id=article_id_1,
        source_id=uuid.uuid4(),
        title="AI Breakthrough in Medicine",
        description="Researchers use deep learning to predict protein fold structures.",
        content="Detailed medical breakthrough content.",
        url="http://example.com/art1",
        published_at=datetime.datetime.utcnow(),
        embedding_status="completed",
    )
    art2 = Article(
        id=article_id_2,
        source_id=uuid.uuid4(),
        title="New Deep Learning Model predicts proteins",
        description="A medical AI model has achieved state of the art results.",
        content="Detailed medical AI content.",
        url="http://example.com/art2",
        published_at=datetime.datetime.utcnow(),
        embedding_status="completed",
    )

    # Mock DB queries
    # Mocking first query (fetch unclustered articles)
    from app.services.embedding_service import EMBEDDING_DIM
    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value.all.return_value = [art1, art2]
    mock_execute_result.scalar_one.return_value = 2
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_result

    # Mock Qdrant retrieve returning vectors for our two articles
    mock_point_1 = MagicMock(id=str(article_id_1), vector=[0.1] * EMBEDDING_DIM)
    mock_point_2 = MagicMock(id=str(article_id_2), vector=[0.11] * EMBEDDING_DIM)
    mock_qdrant_client.retrieve = AsyncMock(return_value=[mock_point_1, mock_point_2])

    # Mock HDBSCAN return labels
    # We patch the HDBSCAN fit_predict method to group them into cluster label 0
    with patch("hdbscan.HDBSCAN") as mock_hdbscan_cls:
        mock_instance = MagicMock()
        mock_instance.fit_predict.return_value = [0, 0]  # both articles in cluster 0
        mock_hdbscan_cls.return_value = mock_instance

        # Mock AI Service output
        mock_analyze_story.return_value = StoryAIResponse(
            headline="AI Deep Learning Breakthrough in Protein Prediction",
            one_line_summary="A new deep learning model predicts protein structures.",
            short_summary="Medical researchers achieve state of the art results using AI.",
            detailed_summary="Medical researchers achieve state of the art results using AI deep learning.",
            key_facts=["Breakthrough in medical AI.", "Uses deep learning."],
            timeline=[TimelineEventSchema(date="2026-06-12", description="Incident reported")],
            differences=[
                SourceDifferenceSchema(
                    source_name="Unknown Source",
                    unique_information="Focuses on medical side.",
                    missing_information="Omitted details.",
                    contradictions="",
                )
            ],
            category="technology",
        )

        # Mock NER Service output
        mock_extract_entities.return_value = [
            {"value": "AI", "type": "ORG"},
            {"value": "Deep Learning", "type": "EVENT"},
        ]

        # Call batch clustering
        # We patch get_or_create_category to bypass category DB creation
        with patch.object(
            clustering_service, "get_or_create_category", AsyncMock(return_value=uuid.uuid4())
        ):
            stories_created = await clustering_service.run_batch_clustering(mock_db_session)

            # Check results
            assert stories_created == 1

            # Check that commit was called
            assert mock_db_session.commit.call_count >= 2
