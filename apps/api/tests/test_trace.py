"""Unit tests for pipeline tracing and Langfuse integration."""

import uuid
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
    with patch("app.core.trace._persist_llm_call", AsyncMock()) as mock_persist, \
         patch("app.core.trace.langfuse_client") as mock_lf:
        
        mock_lf_generation = MagicMock()
        mock_lf.generation.return_value = mock_lf_generation

        run = PipelineRun(trigger="manual", pipeline_type="batch")
        async with run:
            async with StageSpan(run, stage="summary") as span:
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
