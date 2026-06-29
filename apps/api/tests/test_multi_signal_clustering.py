"""Unit tests for multi-signal story clustering, gated merges, and cluster splitting."""

import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.models import Article, ArticleEvent, Story
from app.services.clustering_service import clustering_service


@pytest.mark.asyncio
async def test_compute_event_similarity_direct_math():
    """Verify that multi-signal similarity calculation matches our weighted scoring design."""
    # 1. Exact Match (All signals match, score = 1.0)
    evt1 = ArticleEvent(
        event_type_canonical="ATTACK",
        actors=["Russia"],
        targets=["Ukraine"],
        location="Kyiv",
        event_time=datetime.datetime(2026, 6, 20, 10, 0, 0),
    )
    evt2 = ArticleEvent(
        event_type_canonical="ATTACK",
        actors=["Russia"],
        targets=["Ukraine"],
        location="Kyiv",
        event_time=datetime.datetime(2026, 6, 20, 12, 0, 0),  # < 1 day diff -> 1.0
    )
    score = clustering_service._compute_event_similarity_direct(evt1, evt2)
    # Weights now sum to 0.90 (entity overlap 10% is applied externally)
    assert pytest.approx(score) == 0.90

    # Symmetry check
    score_sym = clustering_service._compute_event_similarity_direct(evt2, evt1)
    assert score == score_sym

    # 2. Defaults for unspecified fields (actors/targets empty -> 0.0, location empty -> 0.5, time empty -> 0.5)
    # Type mismatch (0.0)
    evt_empty1 = ArticleEvent(
        event_type_canonical="ATTACK",
        actors=[],
        targets=[],
        location=None,
        event_time=None,
    )
    evt_empty2 = ArticleEvent(
        event_type_canonical="ELECTION",
        actors=[],
        targets=[],
        location=None,
        event_time=None,
    )
    # Weights: actor (0.25 * 0.0) + target (0.20 * 0.0) + loc (0.20 * 0.5) + type (0.15 * 0.0) + time (0.10 * 0.5)
    # Score = 0.0 + 0.0 + 0.10 + 0.0 + 0.05 = 0.15
    score = clustering_service._compute_event_similarity_direct(evt_empty1, evt_empty2)
    assert pytest.approx(score) == 0.15

    # 3. Substring location and parent event type match
    # Location: "Kyiv" vs "Kyiv Oblast" (substring -> 0.8)
    # Type: "MISSILE_STRIKE" vs "ATTACK" (same parent "ATTACK" -> 0.5)
    # Actors: ["Russia"] vs ["Russia", "Belarus"] (Jaccard = 1/2 = 0.5)
    # Targets: ["Kyiv"] vs ["Kyiv"] (Jaccard = 1.0)
    # Time: 2 days diff (different days -> 0.0)
    evt3 = ArticleEvent(
        event_type_canonical="MISSILE_STRIKE",
        actors=["Russia"],
        targets=["Kyiv"],
        location="Kyiv",
        event_time=datetime.datetime(2026, 6, 20),
    )
    evt4 = ArticleEvent(
        event_type_canonical="ATTACK",
        actors=["Russia", "Belarus"],
        targets=["Kyiv"],
        location="Kyiv Oblast",
        event_time=datetime.datetime(2026, 6, 22),
    )
    # Actor: 0.25 * 0.5 = 0.125
    # Target: 0.20 * 1.0 = 0.20
    # Location: 0.20 * 0.8 = 0.16
    # Type: 0.15 * 0.5 = 0.075
    # Time: 0.10 * 0.0 = 0.0
    # Total = 0.125 + 0.20 + 0.16 + 0.075 + 0.0 = 0.56
    score = clustering_service._compute_event_similarity_direct(evt3, evt4)
    assert pytest.approx(score) == 0.56


@pytest.mark.asyncio
@patch("app.services.vector_service.vector_service.client")
@patch("app.services.vector_service.vector_service.search_similar")
async def test_add_article_gated_merge(mock_search_similar, mock_qdrant_client, mock_db_session):
    """Verify that incremental merges are gated by the multi-signal event similarity threshold."""
    article_id = uuid.uuid4()
    similar_article_id = uuid.uuid4()
    story_id = uuid.uuid4()

    article = Article(
        id=article_id,
        title="Breaking News: Fire in Chicago",
        embedding_status="completed",
    )
    similar_article = Article(
        id=similar_article_id,
        title="Fire reported in Chicago suburb",
        embedding_status="completed",
    )

    # 1. Mock DB returns for article and event
    # First call: fetch Article by ID
    # Second call: fetch ArticleEvent for this Article
    # Third call: check if StoryArticle relation exists
    # Fourth call: get story_id of similar article from StoryArticle
    # Fifth call: get Story by story_id
    # Sixth call: get events of the story
    evt_article = ArticleEvent(
        article_id=article_id,
        event_type_canonical="FIRE",
        actors=["Firefighters"],
        targets=["Warehouse"],
        location="Chicago",
        event_time=datetime.datetime(2026, 6, 20),
    )

    evt_story = ArticleEvent(
        article_id=similar_article_id,
        event_type_canonical="FIRE",
        actors=["Firefighters"],
        targets=["Warehouse"],
        location="Chicago",
        event_time=datetime.datetime(2026, 6, 20),
    )

    story = Story(id=story_id)

    current_story_events = [evt_story]

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        print(f"\n[mock_execute] SQL: {stmt_str} | PARAMS: {stmt.compile().params}")
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        res.scalars.return_value.all.return_value = []
        if "from articles" in stmt_str or "from article " in stmt_str:
            if "story_articles" in stmt_str:
                # Retrieve all articles in story
                res.scalars.return_value.all.return_value = [similar_article, article]
            else:
                res.scalar_one_or_none.return_value = article
        elif "from article_events" in stmt_str:
            if "join story_articles" in stmt_str:
                res.scalars.return_value.all.return_value = current_story_events
            else:
                res.scalar_one_or_none.return_value = evt_article
        elif "from story_articles" in stmt_str:
            if "select story_articles.story_id, story_articles.article_id" in stmt_str:
                res.scalar_one_or_none.return_value = None
            elif "select story_articles.story_id" in stmt_str:
                res.scalar.return_value = story_id
        elif "from stories" in stmt_str:
            res.scalar_one_or_none.return_value = story
        return res

    mock_db_session.execute.side_effect = mock_execute

    # Mock Qdrant retrieval of the vector
    mock_point = MagicMock(id=str(article_id), vector=[0.1] * 128)
    mock_qdrant_client.retrieve = AsyncMock(return_value=[mock_point])

    # Mock search similar returning similar_article_id
    mock_search_similar.return_value = [{"id": similar_article_id, "score": 0.85}]

    # 2. Case A: Event similarity is high (>= 0.80) -> Merge succeeds
    with patch.object(clustering_service, "update_story_incrementally", AsyncMock()) as mock_incr_update, \
         patch.object(clustering_service, "compute_trending_score", AsyncMock()) as mock_trend:

        merged = await clustering_service.add_article_to_existing_story_if_similar(article_id, mock_db_session)
        assert merged is True
        mock_incr_update.assert_called_once()
        mock_trend.assert_called_once()

    # In Case B, the event in the story is completely different (e.g. in Miami, different type/actors)
    evt_different = ArticleEvent(
        article_id=similar_article_id,
        event_type_canonical="ELECTION",
        actors=["Politician"],
        targets=[],
        location="Miami",
        event_time=datetime.datetime(2026, 6, 10),
    )
    current_story_events = [evt_different]

    # 3. Case B: Event similarity is low (< 0.80) -> Merge rejected
    with patch.object(clustering_service, "update_story_incrementally", AsyncMock()) as mock_incr_update:
        merged = await clustering_service.add_article_to_existing_story_if_similar(article_id, mock_db_session)
        assert merged is False
        mock_incr_update.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.vector_service.vector_service.client")
@patch("app.services.ai_service.ai_service.summarize_story_from_kg")
@patch("app.services.ner_service_v2.ner_service_v2.extract_entities")
async def test_batch_clustering_validation_split(
    mock_extract_entities, mock_summarize_story, mock_qdrant_client, mock_db_session
):
    """Verify that batch clustering splits clusters whose articles don't meet the similarity threshold."""
    # 1. Setup 2 unclustered articles
    art1_id = uuid.uuid4()
    art2_id = uuid.uuid4()
    art1 = Article(id=art1_id, embedding_status="completed")
    art2 = Article(id=art2_id, embedding_status="completed")

    # Event 1: Chicago Fire
    evt1 = ArticleEvent(
        article_id=art1_id,
        event_type_canonical="FIRE",
        actors=["Firefighters"],
        targets=["Warehouse"],
        location="Chicago",
        event_time=datetime.datetime(2026, 6, 20),
    )
    # Event 2: London Arrest (completely different, similarity < 0.80)
    evt2 = ArticleEvent(
        article_id=art2_id,
        event_type_canonical="DETENTION",
        actors=["Police"],
        targets=["Suspect"],
        location="London",
        event_time=datetime.datetime(2026, 6, 20),
    )

    # Mock execute results using a query-aware helper
    async def mock_execute_batch(stmt):
        stmt_str = str(stmt).lower()
        params = stmt.compile().params
        print(f"\n[mock_execute_batch] SQL: {stmt_str} | PARAMS: {params}")
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        res.scalar_one.return_value = 0
        res.scalar.return_value = None
        res.scalars.return_value.all.return_value = []
        if "from articles" in stmt_str or "from article " in stmt_str:
            res.scalars.return_value.all.return_value = [art1, art2]
        elif "from article_events" in stmt_str:
            if any(v == art1_id for v in params.values()):
                res.scalar_one_or_none.return_value = evt1
            elif any(v == art2_id for v in params.values()):
                res.scalar_one_or_none.return_value = evt2
            else:
                # Fallback if uncompiled/empty
                if not hasattr(mock_execute_batch, "_call_count"):
                    mock_execute_batch._call_count = 0
                if mock_execute_batch._call_count == 0:
                    mock_execute_batch._call_count += 1
                    res.scalar_one_or_none.return_value = evt1
                else:
                    res.scalar_one_or_none.return_value = evt2
        return res

    mock_db_session.execute.side_effect = mock_execute_batch

    # Mock Qdrant retrieve returning vectors
    mock_point_1 = MagicMock(id=str(art1_id), vector=[0.1] * 128)
    mock_point_2 = MagicMock(id=str(art2_id), vector=[0.11] * 128)
    mock_qdrant_client.retrieve = AsyncMock(return_value=[mock_point_1, mock_point_2])

    # Mock HDBSCAN returning them in the SAME cluster (label 0)
    with patch("hdbscan.HDBSCAN") as mock_hdbscan_cls:
        mock_instance = MagicMock()
        mock_instance.fit_predict.return_value = [0, 0]
        mock_hdbscan_cls.return_value = mock_instance

        # Bypass generate_story_content and category setups
        with patch.object(clustering_service, "_ensure_all_categories", AsyncMock()), \
             patch.object(clustering_service, "generate_story_content", AsyncMock()), \
             patch.object(clustering_service, "compute_trending_score", AsyncMock()):

            # Run clustering. Since event similarity is very low, it should split
            # the cluster of size 2 into 2 sub-clusters of size 1.
            # And it should create stories for them (or single articles, depending on implementation).
            # Wait, run_batch_clustering creates a story for each sub-cluster:
            # "for art_list in verified_clusters: ... Creating story for cluster with len(art_list) articles."
            stories_created = await clustering_service.run_batch_clustering(mock_db_session)

            # Should split into 2 separate stories (one for each article)
            assert stories_created == 2

            # Story additions to session: Story, StoryMetric, StoryArticle for art1; then same for art2
            assert mock_db_session.add.call_count >= 6
