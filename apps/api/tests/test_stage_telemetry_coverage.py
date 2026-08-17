"""Stages must record what they did, and every live stage must be reachable.

Three gaps from the observability audit:

* `crawling` (23,216 spans, 73% of all stage_runs) and `discovery_search`
  (5,002) recorded 0.0% metadata — only a traceback, and only on failure. Every
  field the Crawl inspector is specified to show was already in
  crawl_article's return value and was thrown away.

* Synthesis wrote only to pipeline_traces. The dashboard's DAG reads stage_runs,
  so all seven synthesis stages had zero rows and the SYNTHESIS, FEEDBACK and
  PUBLISHER nodes were permanently empty — opening one 404'd and its log key
  never existed, which is the "No logs available" report.

* event_extraction (899 spans, 886 failures) and ingestion_gnews (157) were in
  no frontend mapping, so the worst-performing stage in the pipeline was never
  drawn at all.
"""

import inspect
import re
from pathlib import Path

import pytest

from app.services.story_synthesis_service import StorySynthesisOrchestrator
from app.workers import tasks

# tests/ -> apps/api -> apps
PIPELINE_PAGE = (
    Path(__file__).resolve().parents[2]
    / "admin"
    / "src"
    / "app"
    / "admin"
    / "pipeline"
    / "page.tsx"
)


# ── crawl / discovery telemetry ───────────────────────────────────────────────


def test_crawl_records_the_fields_the_inspector_needs():
    src = inspect.getsource(tasks.discovery_crawl_task)
    for field in (
        "status_code",
        "fetch_method",
        "extractor",
        "content_length",
        "failure_reason",
        "duration_ms",
        "host",
    ):
        assert field in src, f"crawl telemetry is missing {field}"


def test_crawl_records_metadata_on_failure_not_only_success():
    """A crawl that fails is exactly the one worth inspecting."""
    src = inspect.getsource(tasks.discovery_crawl_task)
    # The recording call sits before the failure branch raises.
    record_idx = src.index(
        "_record(\n                    span,\n                    url=target_url"
    )
    raise_idx = src.index('raise ValueError(f"Crawl failed:')
    assert record_idx < raise_idx, "telemetry must be written before the failure path returns"


def test_crawl_records_terminal_outcomes():
    src = inspect.getsource(tasks.discovery_crawl_task)
    for outcome in ("BUDGET_EXCEEDED", "BLOOM_SKIP", "DUPLICATE_URL", "SUCCESS"):
        assert outcome in src


def test_crawl_span_is_passed_into_the_runner():
    """The span is created in the wrapper; without threading it through, nothing can record."""
    src = inspect.getsource(tasks.discovery_crawl_task)
    assert "as crawl_span" in src and "_run(crawl_span)" in src


def test_discovery_records_query_provider_and_counts():
    src = inspect.getsource(tasks.dispatch_story_candidate_task)
    for field in ("query", "provider", "urls_found", "urls_queued", "urls_rejected"):
        assert field in src, f"discovery telemetry is missing {field}"


# ── synthesis coverage ────────────────────────────────────────────────────────


def test_synthesis_mirrors_every_stage_into_stage_runs():
    src = inspect.getsource(StorySynthesisOrchestrator.record_trace)
    assert "_mirror_trace_to_stage_run" in src, (
        "the DAG reads stage_runs; synthesis wrote only pipeline_traces"
    )


def test_mirror_skips_when_there_is_no_pipeline_run():
    """stage_runs.run_id is a non-null FK — an orphan would abort the transaction."""
    src = inspect.getsource(StorySynthesisOrchestrator._mirror_trace_to_stage_run)
    assert "run_id_ctx" in src
    assert "return" in src
    assert "PipelineRunModel" in src, "the FK target must be confirmed to exist"


def test_mirror_never_breaks_synthesis():
    src = inspect.getsource(StorySynthesisOrchestrator._mirror_trace_to_stage_run)
    assert "except Exception" in src and "logger.warning" in src


def test_mirror_maps_decisions_onto_stage_status():
    src = inspect.getsource(StorySynthesisOrchestrator._mirror_trace_to_stage_run)
    assert '"failed"' in src and '"skipped"' in src and '"success"' in src


def test_mirror_still_writes_the_original_trace():
    """pipeline_traces has other consumers; this must be additive."""
    src = inspect.getsource(StorySynthesisOrchestrator.record_trace)
    assert "PipelineTraceModel" in src
    assert src.index("session.add(trace)") < src.index("_mirror_trace_to_stage_run")


# ── DAG reachability ──────────────────────────────────────────────────────────


@pytest.mark.skipif(not PIPELINE_PAGE.exists(), reason="admin app not present")
@pytest.mark.parametrize(
    "backend_stage", ["event_extraction", "ingestion_gnews", "entity_extraction"]
)
def test_live_backend_stages_are_mapped_in_the_dag(backend_stage):
    """An unmapped stage falls through to .toUpperCase() and matches no node."""
    text = PIPELINE_PAGE.read_text(encoding="utf-8")
    assert f"{backend_stage}:" in text, (
        f"{backend_stage} produces stage_runs in production but is not in "
        f"BACKEND_TO_FRONTEND_STAGE, so it is never drawn"
    )


@pytest.mark.skipif(not PIPELINE_PAGE.exists(), reason="admin app not present")
def test_every_mapped_frontend_stage_has_a_dag_node():
    """A mapping that points at no node is as invisible as no mapping."""
    text = PIPELINE_PAGE.read_text(encoding="utf-8")
    node_ids = set(re.findall(r'\{ id: "([A-Z_]+)"', text))
    mapped = set(re.findall(r'^\s+[a-z_]+: "([A-Z_]+)",', text, re.MULTILINE))
    missing = mapped - node_ids
    assert not missing, f"mapped to non-existent DAG nodes: {sorted(missing)}"
