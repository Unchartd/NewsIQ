from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.models.observability_models import LLMTraceModel, PipelineRunModel, StageRunModel


class OTelTraceExporter:
    """Exports historical pipeline runs to an OTLP/HTTP compliant collector (Jaeger/Tempo)."""

    def __init__(self, endpoint: str = settings.OTEL_EXPORTER_OTLP_ENDPOINT):
        self.endpoint = endpoint

    def _to_otel_span(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        start_time: datetime,
        end_time: datetime,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        status_code: int = 1,
    ) -> dict[str, Any]:
        # traceId must be 32 character hex, spanId must be 16 character hex
        t_id = trace_id.replace("-", "")
        s_id = span_id.replace("-", "")[:16]

        span = {
            "traceId": t_id,
            "spanId": s_id,
            "name": name,
            "kind": 1,  # SPAN_KIND_INTERNAL
            "startTimeUnixNano": str(int(start_time.timestamp() * 1e9)),
            "endTimeUnixNano": str(int(end_time.timestamp() * 1e9)),
            "attributes": [
                {"key": k, "value": self._to_otel_value(v)}
                for k, v in (attributes or {}).items()
            ],
            "status": {"code": status_code},
        }
        if parent_span_id:
            span["parentSpanId"] = parent_span_id.replace("-", "")[:16]
        return span

    def _to_otel_value(self, val: Any) -> dict[str, Any]:
        if isinstance(val, bool):
            return {"boolValue": val}
        if isinstance(val, int):
            return {"intValue": str(val)}
        if isinstance(val, float):
            return {"doubleValue": val}
        return {"stringValue": str(val)}

    async def export_run(
        self,
        run: PipelineRunModel,
        stages: list[StageRunModel],
        llm_traces: list[LLMTraceModel],
    ) -> bool:
        """Construct OTLP trace payload and dispatch to OTLP collector."""
        if not settings.OTEL_EXPORTER_ENABLED and not settings.DEBUG:
            return False

        # 1. Map Pipeline Run to Root Span
        run_span_id = str(run.id)
        meta = run.metadata_payload or {}
        run_attributes = {
            "pipeline.type": run.pipeline_type,
            "pipeline.trigger": run.trigger,
            "pipeline.status": run.status,
            "pipeline.cost_usd": meta.get("cost_usd", 0.0),
            "pipeline.total_tokens": meta.get("total_tokens", 0),
            "pipeline.success_count": meta.get("success_count", 0),
            "pipeline.failure_count": meta.get("failure_count", 0),
        }
        if run.metadata_payload:
            for k, v in run.metadata_payload.items():
                if isinstance(v, (str, bool, int, float)):
                    run_attributes[f"pipeline.meta.{k}"] = v

        spans = [
            self._to_otel_span(
                trace_id=str(run.trace_id),
                span_id=run_span_id,
                name=f"pipeline:{run.pipeline_type}",
                start_time=run.started_at,
                end_time=run.completed_at or run.started_at,
                attributes=run_attributes,
                status_code=1 if run.status == "success" else 2,
            )
        ]

        # 2. Map Stages to Child Spans
        for stage in stages:
            stage_span_id = str(stage.id)
            stage_attributes = {
                "stage.name": stage.stage,
                "stage.status": stage.status,
                "stage.latency_ms": stage.latency_ms or 0.0,
                "stage.retry_count": stage.retry_count or 0,
            }
            if stage.error:
                stage_attributes["error.message"] = stage.error
            if stage.error_type:
                stage_attributes["error.type"] = stage.error_type
            if stage.metadata_payload:
                for k, v in stage.metadata_payload.items():
                    if isinstance(v, (str, bool, int, float)):
                        stage_attributes[f"stage.meta.{k}"] = v

            spans.append(
                self._to_otel_span(
                    trace_id=str(run.trace_id),
                    span_id=stage_span_id,
                    name=f"stage:{stage.stage}",
                    start_time=stage.started_at,
                    end_time=stage.completed_at or stage.started_at,
                    parent_span_id=run_span_id,
                    attributes=stage_attributes,
                    status_code=1 if stage.status == "success" else 2,
                )
            )

            # 3. Map LLM Traces to Leaf Spans
            stage_llms = [t for t in llm_traces if t.stage == stage.stage]
            for llm in stage_llms:
                llm_span_id = str(llm.id)
                llm_attributes = {
                    "llm.model": llm.model,
                    "llm.provider": llm.provider,
                    "llm.input_tokens": llm.input_tokens or 0,
                    "llm.output_tokens": llm.output_tokens or 0,
                    "llm.total_tokens": llm.total_tokens or 0,
                    "llm.cost_usd": llm.cost_usd or 0.0,
                    "llm.latency_ms": llm.latency_ms or 0.0,
                }
                parent_id = str(llm.parent_llm_trace_id) if llm.parent_llm_trace_id else stage_span_id

                spans.append(
                    self._to_otel_span(
                        trace_id=str(run.trace_id),
                        span_id=llm_span_id,
                        name=f"llm:{llm.model}",
                        start_time=llm.created_at,
                        end_time=llm.created_at,
                        parent_span_id=parent_id,
                        attributes=llm_attributes,
                        status_code=1 if llm.status == "success" else 2,
                    )
                )

        # 4. Construct OTLP JSON Payload
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": "newsiq-pipeline-processor"}}
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "newsiq-observability"},
                            "spans": spans,
                        }
                    ],
                }
            ]
        }

        # 5. POST to endpoint
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5.0,
                )
                return response.status_code in (200, 202)
            except Exception:
                return False
