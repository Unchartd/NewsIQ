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

# ── LLM Gateway Fallback Metrics ─────────────────────────────────────────────

newsiq_llm_fallback_attempts = Counter(
    "newsiq_llm_fallback_attempts",
    "Number of fallback attempts before a successful LLM call.",
    ["stage", "final_provider", "final_model"],
)

