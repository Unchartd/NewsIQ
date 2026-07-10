"""Unit tests for the story clustering service."""

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import Article, ArticleEvent
from app.services.ai_service import StorySummaryResponse
from app.services.clustering_service import clustering_service


@pytest.mark.asyncio
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
@patch("app.services.vector_service.vector_service.client")
async def test_run_batch_clustering(
    mock_qdrant_client, mock_extract_entities, mock_summarize_story, mock_db_session
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

    # Mock DB queries using a query-aware helper
    from app.services.embedding_service import EMBEDDING_DIM

    async def mock_execute_side_effect(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        res.scalars.return_value.all.return_value = []
        if "article_events" in stmt_str:
            evt1 = ArticleEvent(
                article_id=article_id_1,
                event_type_canonical="ATTACK",
                actors=["Russia"],
                targets=["Ukraine"],
                location="Kyiv",
                event_time=datetime.datetime(2026, 6, 20),
            )
            evt2 = ArticleEvent(
                article_id=article_id_2,
                event_type_canonical="ATTACK",
                actors=["Russia"],
                targets=["Ukraine"],
                location="Kyiv",
                event_time=datetime.datetime(2026, 6, 20),
            )
            res.scalar_one_or_none.side_effect = [evt1, evt2, evt1, evt2]
            res.scalars.return_value.all.return_value = [evt1, evt2]
        elif "articles" in stmt_str or "article " in stmt_str or "discoveryqueue" in stmt_str:
            res.scalars.return_value.all.return_value = [art1, art2]
            res.scalar_one_or_none.return_value = art1
            res.all.return_value = [(art1, MagicMock(id=uuid.uuid4(), state="ready")), (art2, MagicMock(id=uuid.uuid4(), state="ready"))]
        elif "sources" in stmt_str or "source" in stmt_str:
            res.scalar_one_or_none.return_value = MagicMock(name="Source Mock", country_code="US")
        elif "canonical_entities" in stmt_str:
            res.scalar_one_or_none.return_value = MagicMock(id=uuid.uuid4())
        return res

    mock_db_session.execute.side_effect = mock_execute_side_effect

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
        mock_summarize_story.return_value = StorySummaryResponse(
            headline="AI Deep Learning Breakthrough in Protein Prediction",
            one_line_summary="A new deep learning model predicts protein structures.",
            short_summary="Medical researchers achieve state of the art results using AI.",
            detailed_summary="Medical researchers achieve state of the art results using AI deep learning.",
            key_facts=["Breakthrough in medical AI.", "Uses deep learning."],
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
