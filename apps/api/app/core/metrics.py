"""Prometheus metrics definition for the NewsIQ platform.

Provides Counters, Gauges, and Histograms to measure pipeline throughput,
latencies, costs, token usage, and queue depth.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Pipeline Metrics ─────────────────────────────────────────────────────────

newsiq_stories_total = Counter(
    "newsiq_stories_total",
    "Total number of stories clustered/created.",
    ["category"],
)

newsiq_articles_total = Counter(
    "newsiq_articles_total",
    "Total number of articles ingested.",
    ["source"],
)

newsiq_queue_depth = Gauge(
    "newsiq_queue_depth",
    "Current number of jobs in the queue.",
    ["queue_name"],
)

newsiq_failure_rate = Counter(
    "newsiq_failure_rate",
    "Total number of pipeline failures by stage.",
    ["stage", "error_type"],
)

newsiq_latency_seconds = Histogram(
    "newsiq_latency_seconds",
    "Latency of pipeline stage execution in seconds.",
    ["stage"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

# ── Discovery & Validation Metrics ───────────────────────────────────────────

newsiq_discovery_queue_size = Gauge(
    "newsiq_discovery_queue_size",
    "Current number of articles in the Discovery Queue by state.",
    ["state"],
)

newsiq_discovery_articles_total = Counter(
    "newsiq_discovery_articles_total",
    "Total number of articles sent to the Discovery Queue.",
    ["reason"],  # e.g., stage_a_fail, stage_b_fail, reflection_fail
)

newsiq_discovery_clusters_total = Counter(
    "newsiq_discovery_clusters_total",
    "Total number of new story clusters created by HDBSCAN.",
)

newsiq_reflection_requests_total = Counter(
    "newsiq_reflection_requests_total",
    "Total number of LLM reflection requests triggered.",
    ["outcome"],  # e.g., merged, rejected
)

newsiq_stage_a_validation_total = Counter(
    "newsiq_stage_a_validation_total",
    "Total number of Stage A validation checks.",
    ["outcome"],  # e.g., pass, maybe, rejected
)

# ── LLM & Cost Metrics ───────────────────────────────────────────────────────

newsiq_token_usage_total = Counter(
    "newsiq_token_usage_total",
    "Total token consumption by provider, model, and stage.",
    ["provider", "model", "stage", "token_type"],  # token_type: input or output
)

newsiq_provider_calls_total = Counter(
    "newsiq_provider_calls_total",
    "Total number of LLM provider API calls.",
    ["provider", "model", "stage", "status"],
)

newsiq_llm_cost_dollars = Counter(
    "newsiq_llm_cost_dollars",
    "Total LLM cost in USD by provider, model, and stage.",
    ["provider", "model", "stage"],
)

# ── Story-Level Cost Aggregation ─────────────────────────────────────────────

newsiq_story_cost_usd = Counter(
    "newsiq_story_cost_usd",
    "Cumulative LLM cost per story generation in USD.",
    ["category"],
)

newsiq_story_stages_total = Counter(
    "newsiq_story_stages_total",
    "Total number of pipeline stages executed per story.",
    ["stage", "status"],  # status: success, error, skipped, cache_hit
)

# ── Pipeline Cache Metrics ───────────────────────────────────────────────────

newsiq_pipeline_cache_operations = Counter(
    "newsiq_pipeline_cache_operations",
    "Pipeline-level cache operations (hit, miss, set, error).",
    ["stage", "operation"],  # operation: hit, miss, set, set_error, get_error
)

# ── Queue & Worker Metrics ───────────────────────────────────────────────────

newsiq_task_queue_time_seconds = Histogram(
    "newsiq_task_queue_time_seconds",
    "Time a Celery task spent waiting in the queue before execution started.",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float("inf")),
)

newsiq_task_worker_time_seconds = Histogram(
    "newsiq_task_worker_time_seconds",
    "Time a Celery task spent executing in the worker.",
    ["task_name"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, float("inf")),
)

# ── Event Validation Metrics ─────────────────────────────────────────────────

newsiq_event_validation_decisions_total = Counter(
    "newsiq_event_validation_decisions_total",
    "Total number of event validation decisions by stage and outcome.",
    ["stage", "outcome"],  # stage: stage_a, stage_b. outcome: PASS, FAIL, MAYBE
)

newsiq_event_validation_savings_total = Counter(
    "newsiq_event_validation_savings_total",
    "Costly operations avoided due to early event validation rejection.",
    ["resource"],  # resource: llm_calls, embeddings
)

newsiq_event_validation_latency_seconds = Histogram(
    "newsiq_event_validation_latency_seconds",
    "Latency of event validation stages.",
    ["stage"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, float("inf")),
)

# ── LLM Gateway Fallback Metrics ─────────────────────────────────────────────

newsiq_llm_fallback_attempts = Counter(
    "newsiq_llm_fallback_attempts",
    "Number of fallback attempts before a successful LLM call.",
    ["stage", "final_provider", "final_model"],
)

# ── Discovery Pipeline Quality Metrics ────────────────────────────────────────

newsiq_discovery_searches_succeeded = Counter(
    "newsiq_discovery_searches_succeeded_total",
    "Total number of successful discovery searches.",
)

newsiq_discovery_searches_failed = Counter(
    "newsiq_discovery_searches_failed_total",
    "Total number of failed discovery searches.",
)

newsiq_discovery_urls_decoded = Counter(
    "newsiq_discovery_urls_decoded_total",
    "Total number of successfully decoded Google News redirect URLs.",
)

newsiq_discovery_urls_decode_failed = Counter(
    "newsiq_discovery_urls_decode_failed_total",
    "Total number of Google News redirect URLs that failed to decode.",
)

newsiq_discovery_crawls_succeeded = Counter(
    "newsiq_discovery_crawls_succeeded_total",
    "Total number of successful discovery crawls.",
)

newsiq_discovery_crawls_failed = Counter(
    "newsiq_discovery_crawls_failed_total",
    "Total number of failed discovery crawls.",
    ["reason"],
)
