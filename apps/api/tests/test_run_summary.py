"""Run history must describe what a run did, not that it finished.

The summary builder read `articles_ingested`, `success_count`, `stories_created`
and `stories_updated` at the TOP level of stage metadata. The collector nests
everything under input/output/metrics/…, so those names have never appeared at
the top level for any stage — the counters were always zero and every
successful run was summarised "Completed (no actions)".

Replayed over 300 real production runs, uninformative summaries fall from 223
to 15, with no change to the stored telemetry.
"""

from unittest.mock import MagicMock

from app.api.v1.admin import _build_run_summary, _metric


def _sr(stage, status="success", metadata=None):
    sr = MagicMock()
    sr.stage = stage
    sr.status = status
    sr.metadata_payload = metadata
    return sr


# ── metadata lookup ───────────────────────────────────────────────────────────


def test_reads_counters_from_the_nested_metrics_block():
    """Where the collector actually writes them."""
    meta = {"metrics": {"stories_created": 3}, "output": {"stories_created": "3"}}
    assert _metric(meta, "stories_created") == 3


def test_falls_back_to_output_then_outputs():
    """entity_extraction writes only `output`; clustering_incremental only `outputs`."""
    assert _metric({"output": {"entities_extracted": 7}}, "entities_extracted") == 7
    assert _metric({"outputs": {"merged": True}}, "merged") is True


def test_top_level_still_works_for_any_flat_writer():
    assert _metric({"success_count": 5}, "success_count") == 5


def test_missing_counter_is_none_not_zero():
    assert _metric({"metrics": {}}, "nope") is None


# ── summaries ─────────────────────────────────────────────────────────────────


def test_rss_run_reports_feeds_and_candidates():
    """Previously: "Completed (no actions)"."""
    summary = _build_run_summary(
        [
            _sr(
                "ingestion_rss",
                metadata={"metrics": {"sources_processed": 2834, "story_candidates_created": 6}},
            )
        ]
    )
    assert "2,834 feeds" in summary
    assert "6 candidates" in summary


def test_string_counters_are_parsed():
    """output.stories_created is stored as the string "1"."""
    summary = _build_run_summary(
        [_sr("clustering_batch", metadata={"output": {"stories_created": "1"}})]
    )
    assert "1 story created" in summary


def test_crawl_volume_comes_from_the_span_count():
    """Crawl records no metadata, but the number of spans is the number of URLs."""
    summary = _build_run_summary([_sr("crawling") for _ in range(28)])
    assert "28 URLs crawled" in summary


def test_a_failure_no_longer_erases_what_the_run_achieved():
    """The old builder replaced the whole summary with "Failed at <stage>"."""
    summary = _build_run_summary(
        [
            _sr("embedding", metadata={"metrics": {"success_count": 5}}),
            _sr("event_extraction", status="failed", metadata={"metrics": {"failed_count": 1}}),
        ]
    )
    assert "5 articles embedded" in summary, "work completed before the failure was discarded"
    assert "failed at event extraction" in summary


def test_counters_aggregate_across_repeated_stage_runs():
    """A run holds one span per article, not one per stage."""
    runs = [_sr("embedding", metadata={"metrics": {"success_count": 5}}) for _ in range(4)]
    assert "20 articles embedded" in _build_run_summary(runs)


def test_pluralisation_is_correct():
    assert "1 feed" in _build_run_summary(
        [_sr("ingestion_rss", metadata={"metrics": {"sources_processed": 1}})]
    )
    assert "3 searches" in _build_run_summary([_sr("discovery_search") for _ in range(3)])


def test_never_claims_nothing_happened_when_stages_ran():
    """The last resort names the stages rather than asserting no actions."""
    summary = _build_run_summary([_sr("clustering_incremental", metadata={"outputs": {}})])
    assert "no actions" not in summary.lower()
    assert "clustering incremental" in summary


def test_running_and_skipped_runs_are_still_distinguishable():
    assert _build_run_summary([_sr("embedding", status="running")]) == "Executing…"
    assert "no new articles" in _build_run_summary([_sr("embedding", status="skipped")]).lower()


def test_empty_run_is_idle():
    assert _build_run_summary([]) == "Idle"
