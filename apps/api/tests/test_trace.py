"""Unit tests for pipeline tracing and Langfuse integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.trace import (
    PipelineRun,
    StageSpan,
    StageStatus,
    calculate_llm_cost,
    get_trace_context,
    track_llm_call,
)


@pytest.mark.asyncio
async def test_pipeline_run_context_propagation():
    """Verify PipelineRun sets and resets context variables and triggers Langfuse."""
    with patch("app.core.trace.langfuse_client") as mock_lf:
        run = PipelineRun(trigger="manual", pipeline_type="batch")

        # Initially empty context
        ctx = get_trace_context()
        assert ctx["run_id"] == ""
        assert ctx["trace_id"] == ""

        # Enter context manager
        async with run:
            ctx = get_trace_context()
            assert ctx["run_id"] == run.id
            assert ctx["trace_id"] == run.trace_id
            assert run.status == StageStatus.RUNNING

            mock_lf.trace.assert_called_once_with(
                name="pipeline:batch",
                id=run.trace_id,
                metadata={
                    "trigger": "manual",
                    "pipeline_type": "batch",
                    "is_replay": False,
                    "parent_run_id": None,
                },
            )

        # Exit context manager
        ctx = get_trace_context()
        assert ctx["run_id"] == ""
        assert ctx["trace_id"] == ""
        assert run.status == StageStatus.SUCCESS


@pytest.mark.asyncio
async def test_stage_span_context_propagation():
    """Verify StageSpan sets context vars, appends to PipelineRun, and uses Langfuse."""
    with patch("app.core.trace.langfuse_client") as mock_lf:
        mock_lf.span.return_value = MagicMock()

        run = PipelineRun(trigger="celery_beat", pipeline_type="batch")
        async with run:
            async with StageSpan(run, stage="embedding", story_id="story-123") as span:
                ctx = get_trace_context()
                assert ctx["span_id"] == span.span_id
                assert ctx["stage"] == "embedding"
                assert ctx["story_id"] == "story-123"

                mock_lf.span.assert_called_once_with(
                    trace_id=run.trace_id,
                    name="embedding",
                    id=span.span_id,
                    metadata={"story_id": "story-123", "article_id": None},
                )
                span.set_metadata({"articles_processed": 5})

            # After span exit, span-specific context is cleared
            ctx = get_trace_context()
            assert ctx["span_id"] == ""
            assert ctx["stage"] == ""

        # Check registered span
        assert len(run.stages) == 1
        recorded = run.stages[0]
        assert recorded.stage == "embedding"
        assert recorded.status == StageStatus.SUCCESS
        assert recorded.metadata == {"articles_processed": 5}
        recorded.lf_span = span.lf_span
        assert recorded.lf_span is not None


@pytest.mark.asyncio
async def test_track_llm_call_cost_and_logging():
    """Verify track_llm_call calculates pricing, persists to DB, and logs to Langfuse."""
    from app.core.trace import LLMCallData

    # Mock the DB persistence helper
    with (
        patch("app.core.trace._persist_llm_call", AsyncMock()) as mock_persist,
        patch("app.core.trace.langfuse_client") as mock_lf,
    ):
        mock_lf_generation = MagicMock()
        mock_lf.generation.return_value = mock_lf_generation

        run = PipelineRun(trigger="manual", pipeline_type="batch")
        async with run:
            async with StageSpan(run, stage="summary"):
                async with track_llm_call(
                    provider="gemini",
                    model="gemini-2.5-flash",
                    stage="summary",
                    system_prompt="You are a summarizer.",
                    user_prompt="Summarize this text.",
                    temperature=0.5,
                ) as call:
                    assert isinstance(call, LLMCallData)
                    assert call.system_prompt == "You are a summarizer."

                    # Simulate API response filling tokens
                    call.response_text = "Here is the summary."
                    call.input_tokens = 100
                    call.output_tokens = 50

                mock_lf.generation.assert_called_once()
                mock_lf_generation.end.assert_called_once_with(
                    output="Here is the summary.",
                    usage={"input": 100, "output": 50},
                    level="DEFAULT",
                    status_message=None,
                )

        # Check calculated costs
        # gemini-2.5-flash: input 0.15/M, output 0.60/M
        # 100 input tokens = 0.000015 USD
        # 50 output tokens = 0.000030 USD
        # total cost = 0.000045 USD
        assert call.cost_usd == 0.000045
        assert call.total_tokens == 150
        assert call.status == "success"

        # Verify db persistence was called
        mock_persist.assert_called_once_with(call)


def test_calculate_llm_cost():
    """Test cost calculator with edge cases and normal scenarios."""
    # Gemini 2.5 Flash pricing
    cost = calculate_llm_cost("gemini-2.5-flash", 1_000_000, 1_000_000)
    assert cost == 0.15 + 0.60

    # Unknown model (should return 0.0 cost)
    cost = calculate_llm_cost("unknown-model", 100, 100)
    assert cost == 0.0


@pytest.mark.asyncio
async def test_pipeline_trace_collector_lifecycle():
    """Verify PipelineTraceCollector event emission, sequence numbering, and data sampling."""
    from app.core.trace import PipelineTraceCollector, sequence_number_ctx

    sequence_number_ctx.set(0)

    with (
        patch("app.core.trace.emit_pipeline_event", AsyncMock()) as mock_emit_event,
        patch("app.core.trace.save_artifact", return_value="art_path") as mock_save_artifact,
        patch("app.core.trace.StageTrace._persist_db", AsyncMock()) as mock_persist,
    ):
        async with PipelineTraceCollector.stage("embedding") as stage:
            assert stage.status == "RUNNING"
            stage.metric("accuracy", 0.99)
            stage.metric("latency_ms", 12.5)

            # Test input sampling limits (mock articles list)
            class MockArticle:
                def __init__(self, id_):
                    self.id = id_

            articles = [MockArticle(f"art_{i}") for i in range(25)]
            stage.input(articles=articles)

            # Output
            stage.output(articles=articles[:5])

            # Artifact
            stage.artifact("test_artifact", {"matrix": [1, 2, 3]}, tier=1)

            # Lineage
            stage.lineage("art_1", "ARTICLE", "EMBEDDED")

        # Exited context successfully
        assert stage.status == "COMPLETED"
        assert stage.latency_ms > 0
        assert mock_emit_event.call_count == 2  # StageStarted + StageCompleted

        # Check sequence numbers
        start_call = mock_emit_event.call_args_list[0][0][0]
        end_call = mock_emit_event.call_args_list[1][0][0]
        assert start_call["event_type"] == "StageStarted"
        assert start_call["sequence_number"] == 1
        assert end_call["event_type"] == "StageCompleted"
        assert end_call["sequence_number"] == 2

        # Check input/output sampling (first 10, last 10, count)
        assert stage.input_data["articles"]["total_count"] == 25
        assert len(stage.input_data["articles"]["sample"]) == 21  # 10 + "..." + 10
        assert stage.input_data["articles"]["sample"][10] == "..."
        assert stage.input_data["articles"]["sample"][0] == "art_0"
        assert stage.input_data["articles"]["sample"][-1] == "art_24"

        # Check lineage
        assert len(stage.lineage_data) == 1
        assert stage.lineage_data[0]["node_id"] == "art_1"
        assert stage.lineage_data[0]["transition"] == "EMBEDDED"

        # Check artifact
        mock_save_artifact.assert_called_once()
        assert stage.artifacts_data["test_artifact"] == "art_path"

        # Check db persistence
        mock_persist.assert_called_once()


@pytest.mark.asyncio
async def test_save_artifact_tier_policy():
    """Verify save_artifact respects Tier 1, 2, and 3 policies."""
    from app.core.trace import save_artifact
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("app.core.config.settings.LOCAL_STORAGE_PATH", tmpdir):
            # Tier 3: Never save
            res = save_artifact("vectors", [1.0, 2.0], tier=3, run_id="run_1", span_id="span_1")
            assert res is None

            # Tier 2: Save on failure only. Success = True -> Should not save.
            res = save_artifact("html", "<html></html>", tier=2, run_id="run_1", span_id="span_1", success=True)
            assert res is None

            # Tier 2: Save on failure only. Success = False -> Should save.
            res = save_artifact("html", "<html></html>", tier=2, run_id="run_1", span_id="span_1", success=False)
            assert res is not None
            assert os.path.exists(os.path.join(tmpdir, res))

            # Tier 1: Always save.
            res = save_artifact("matrix", {"similarity": 0.8}, tier=1, run_id="run_1", span_id="span_1")
            assert res is not None
            assert os.path.exists(os.path.join(tmpdir, res))


@pytest.mark.asyncio
async def test_llm_trace_parent_relationship():
    """Verify nested track_llm_call invocations propagate parent_llm_trace_id."""
    from app.core.trace import parent_llm_trace_id_ctx

    parent_llm_trace_id_ctx.set("")

    with (
        patch("app.core.trace._persist_llm_call", AsyncMock()) as mock_persist,
        patch("app.core.trace.langfuse_client") as mock_lf,
    ):
        async with track_llm_call(
            provider="gemini", model="gemini-2.5-flash", stage="summary"
        ) as parent_call:
            # Check context variable set
            assert parent_llm_trace_id_ctx.get() == parent_call.call_id

            # Trigger nested child call
            async with track_llm_call(
                provider="gemini", model="gemini-2.0-flash", stage="judge"
            ) as child_call:
                assert child_call.parent_llm_trace_id == parent_call.call_id

        # Checks after completion
        assert mock_persist.call_count == 2
        calls = mock_persist.call_args_list
        # First call completed (child)
        assert calls[0][0][0].call_id == child_call.call_id
        assert calls[0][0][0].parent_llm_trace_id == parent_call.call_id
        # Second call completed (parent)
        assert calls[1][0][0].call_id == parent_call.call_id
        assert calls[1][0][0].parent_llm_trace_id == ""

