import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.admin import trigger_run_export_otel
from app.models.observability_models import LLMTraceModel, PipelineRunModel, StageRunModel
from app.services.otel_exporter import OTelTraceExporter
from app.services.rca_classifier import RootCauseAnalysisService


def test_rca_classifier_rate_limits():
    """Verify that error messages with rate limit cues classify to LLM_RATE_LIMIT."""
    report = RootCauseAnalysisService.classify_error(
        error_msg="RateLimitError: 429 Too Many Requests on model gemini-2.5-flash",
        error_type="RateLimitError"
    )
    assert report is not None
    assert report.category == "LLM_RATE_LIMIT"
    assert report.confidence == 0.95
    assert "backoff" in report.remediation.lower()


def test_rca_classifier_context_window():
    """Verify that token limits error classify to LLM_CONTEXT_WINDOW_EXCEEDED."""
    report = RootCauseAnalysisService.classify_error(
        error_msg="context length exceeded limit of 1048576 tokens",
        error_type="ContextLengthExceeded"
    )
    assert report is not None
    assert report.category == "LLM_CONTEXT_WINDOW_EXCEEDED"
    assert report.confidence == 0.90


def test_rca_classifier_db_timeout():
    """Verify database OperationalError maps to DATABASE_TIMEOUT."""
    report = RootCauseAnalysisService.classify_error(
        error_msg="sqlalchemy.exc.OperationalError: asyncpg connection pool timeout",
        error_type="OperationalError"
    )
    assert report is not None
    assert report.category == "DATABASE_TIMEOUT"


def test_rca_classifier_vector_db():
    """Verify vector DB connection failures map to VECTOR_DB_UNAVAILABLE."""
    report = RootCauseAnalysisService.classify_error(
        error_msg="Qdrant connection refused on grpc://localhost:6334",
        error_type="ConnectionRefusedError"
    )
    assert report is not None
    assert report.category == "VECTOR_DB_UNAVAILABLE"


def test_rca_classifier_oom():
    """Verify high memory or OutOfMemory classifications map to OUT_OF_MEMORY."""
    report = RootCauseAnalysisService.classify_error(
        error_msg="Process killed by OOM killer (MemoryError)",
        error_type="MemoryError",
        metadata={"resource_usage": {"memory_percent": 98.5}}
    )
    assert report is not None
    assert report.category == "OUT_OF_MEMORY"


@pytest.mark.asyncio
async def test_otel_exporter_payload():
    """Verify OTel exporter formats and sends spans correctly to Jaeger/Tempo OTLP endpoint."""
    run = PipelineRunModel(
        id=uuid.uuid4(),
        trace_id=uuid.uuid4(),
        pipeline_type="batch",
        trigger="manual",
        status="success",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        completed_at=datetime.now(UTC).replace(tzinfo=None),
        metadata_payload={
            "cost_usd": 0.005,
            "total_tokens": 15000,
            "success_count": 12,
            "failure_count": 0,
        }
    )

    stage = StageRunModel(
        id=uuid.uuid4(),
        run_id=run.id,
        trace_id=run.trace_id,
        stage="synthesis",
        status="success",
        latency_ms=2500.0,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        completed_at=datetime.now(UTC).replace(tzinfo=None),
    )

    llm = LLMTraceModel(
        id=uuid.uuid4(),
        run_id=run.id,
        stage="synthesis",
        provider="google",
        model="gemini-2.5-flash",
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        cost_usd=0.0003,
        latency_ms=1200.0,
        status="success",
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )

    # Mock settings to enable exporter
    with patch("app.services.otel_exporter.settings") as mock_settings:
        mock_settings.OTEL_EXPORTER_ENABLED = True
        mock_settings.OTEL_EXPORTER_OTLP_ENDPOINT = "http://mock-jaeger:4318/v1/traces"

        # Mock httpx client post call
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient.post", mock_post):
            exporter = OTelTraceExporter()
            success = await exporter.export_run(run, [stage], [llm])

            assert success is True
            mock_post.assert_called_once()
            called_json = mock_post.call_args[1]["json"]

            # Verify structure
            assert "resourceSpans" in called_json
            spans = called_json["resourceSpans"][0]["scopeSpans"][0]["spans"]
            assert len(spans) == 3  # Pipeline, Stage, LLM

            # Verify spans names
            assert spans[0]["name"] == "pipeline:batch"
            assert spans[1]["name"] == "stage:synthesis"
            assert spans[2]["name"] == "llm:gemini-2.5-flash"


@pytest.mark.asyncio
async def test_manual_export_endpoint(mock_db_session):
    """Verify that manual OTel export endpoint triggers exporter and responds 200."""
    run_id = uuid.uuid4()

    mock_run = PipelineRunModel(
        id=run_id,
        trace_id=uuid.uuid4(),
        pipeline_type="batch",
        trigger="manual",
        status="success",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )

    mock_db_session.get.return_value = mock_run

    # Mock database execute calls returning stages and LLM traces
    mock_result_stages = MagicMock()
    mock_result_stages.scalars.return_value.all.return_value = []

    mock_result_llm = MagicMock()
    mock_result_llm.scalars.return_value.all.return_value = []

    mock_db_session.execute.side_effect = [mock_result_stages, mock_result_llm]

    with patch("app.services.otel_exporter.OTelTraceExporter.export_run", AsyncMock(return_value=True)):
        response = await trigger_run_export_otel(run_id=run_id, db=mock_db_session)
        assert response["message"] == "Pipeline run exported successfully to OTLP collector."
