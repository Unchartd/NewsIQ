import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.observability_models import (
    StoryEvolutionModel,
)
from app.services.story_evolution_service import record_story_evolution
from app.workers.tasks import purge_observability_data_task


@pytest.mark.asyncio
async def test_record_story_evolution(mock_db_session):
    """Verify that story evolution records are successfully written to the database."""
    story_id = uuid.uuid4()
    run_id = uuid.uuid4()

    # Test explicit run_id
    await record_story_evolution(
        db=mock_db_session,
        story_id=story_id,
        event_type="article_merged",
        before_state={"article_count": 2},
        after_state={"article_count": 3},
        notes="Merged article test",
        run_id=run_id,
    )

    # Verify that add was called with a StoryEvolutionModel
    mock_db_session.add.assert_called_once()
    added_obj = mock_db_session.add.call_args[0][0]
    assert isinstance(added_obj, StoryEvolutionModel)
    assert added_obj.event_type == "article_merged"
    assert added_obj.run_id == run_id
    assert added_obj.before_state == {"article_count": 2}
    assert added_obj.after_state == {"article_count": 3}
    assert added_obj.notes == "Merged article test"


@pytest.mark.asyncio
async def test_purge_observability_data_task(mock_db_session):
    """Verify that old observability records are successfully purged (>30d) or redacted (>14d)."""
    # Setup mock session execute to return a result with rowcount
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_db_session.execute.return_value = mock_result

    # We patch async_session_factory context manager to yield our mock db session
    class MockSessionFactory:
        def __init__(self, session):
            self.session = session
        def __call__(self):
            return self
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    # Patch run_async to return the coroutine directly, and patch the session factory
    with patch("app.workers.tasks.run_async", lambda coro: coro), \
         patch("app.workers.tasks.async_session_factory", MockSessionFactory(mock_db_session)):
        coro = purge_observability_data_task(retention_days=30, redact_days=14)
        stats = await coro

    # Verify stats reflect the mock rowcounts
    assert stats["runs_purged"] == 5
    assert stats["llm_traces_purged"] == 5
    assert stats["runs_redacted"] == 5
    assert stats["stages_redacted"] == 5

    # Verify that commit was called
    mock_db_session.commit.assert_called_once()
