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

# ── Crawler Hardening Metrics (Phase 2A) ──────────────────────────────────────

newsiq_crawler_http_success_total = Counter(
    "newsiq_crawler_http_success_total",
    "Total number of successful HTTP crawler fetches.",
)

newsiq_crawler_http_failure_total = Counter(
    "newsiq_crawler_http_failure_total",
    "Total number of failed HTTP crawler fetches.",
    ["reason"],  # status code or exception class name
)

newsiq_crawler_bot_block_total = Counter(
    "newsiq_crawler_bot_block_total",
    "Total number of times a crawl was blocked by anti-bot protections.",
)

newsiq_crawler_timeout_total = Counter(
    "newsiq_crawler_timeout_total",
    "Total number of times a crawl timed out.",
)

newsiq_crawler_empty_html_total = Counter(
    "newsiq_crawler_empty_html_total",
    "Total number of times a crawl returned empty HTML.",
)

newsiq_crawler_extraction_success_total = Counter(
    "newsiq_crawler_extraction_success_total",
    "Total number of successful text extractions.",
    ["extractor"],  # e.g., newspaper, trafilatura, readability, custom-bs4
)

newsiq_crawler_extraction_failure_total = Counter(
    "newsiq_crawler_extraction_failure_total",
    "Total number of failed text extractions.",
)

newsiq_crawler_persisted_total = Counter(
    "newsiq_crawler_persisted_total",
    "Total number of crawled articles successfully persisted to the database.",
)

# ── Multi-Provider Extraction Metrics ────────────────────────────────────────

newsiq_crawler_attempts_total = Counter(
    "newsiq_crawler_attempts_total",
    "Total number of crawl orchestration attempts.",
)

newsiq_crawler_provider_attempts_total = Counter(
    "newsiq_crawler_provider_attempts_total",
    "Total number of attempts per extraction provider.",
    ["provider"],  # e.g., local, tavily, firecrawl
)

newsiq_crawler_provider_success_total = Counter(
    "newsiq_crawler_provider_success_total",
    "Total number of successful extractions per provider.",
    ["provider"],
)

newsiq_crawler_provider_failure_total = Counter(
    "newsiq_crawler_provider_failure_total",
    "Total number of failed extractions per provider.",
    ["provider"],
)

newsiq_crawler_provider_latency_seconds = Histogram(
    "newsiq_crawler_provider_latency_seconds",
    "Latency of extraction per provider in seconds.",
    ["provider"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, float("inf")),
)

newsiq_crawler_tavily_batch_requests_total = Counter(
    "newsiq_crawler_tavily_batch_requests_total",
    "Total number of batched API requests made to Tavily.",
)

newsiq_crawler_tavily_urls_processed_total = Counter(
    "newsiq_crawler_tavily_urls_processed_total",
    "Total number of URLs processed inside Tavily Extract batches.",
)

newsiq_crawler_firecrawl_requests_total = Counter(
    "newsiq_crawler_firecrawl_requests_total",
    "Total number of scrape requests made to Firecrawl.",
)

newsiq_crawler_local_success_rate = Counter(
    "newsiq_crawler_local_success_rate",
    "Total number of crawl tasks resolved entirely by the local crawler.",
)

newsiq_crawler_fallback_rate = Counter(
    "newsiq_crawler_fallback_rate",
    "Total number of times crawls had to fallback to external APIs.",
)

newsiq_crawler_batch_wait_time_seconds = Histogram(
    "newsiq_crawler_batch_wait_time_seconds",
    "Time spent by workers waiting in the Tavily batch polling loop.",
    buckets=(0.1, 0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, float("inf")),
)

newsiq_crawler_redis_batch_flush_total = Counter(
    "newsiq_crawler_redis_batch_flush_total",
    "Total number of times a Redis queue batch flush was triggered by a leader.",
)

newsiq_crawler_provider_cost_total = Counter(
    "newsiq_crawler_provider_cost_total",
    "Estimated dollar cost incurred by extraction provider API calls.",
    ["provider"],
)

newsiq_crawler_provider_attempts_total_v2 = Counter(
    "newsiq_crawler_provider_attempts_total_v2",
    "Total number of extraction attempts per provider and domain.",
    ["provider", "domain"],
)

newsiq_crawler_provider_success_total_v2 = Counter(
    "newsiq_crawler_provider_success_total_v2",
    "Total number of successful extractions per provider and domain.",
    ["provider", "domain"],
)

newsiq_crawler_provider_failure_total_v2 = Counter(
    "newsiq_crawler_provider_failure_total_v2",
    "Total number of failed extractions by provider, failure reason, and domain.",
    ["provider", "failure_reason", "domain"],
)

newsiq_crawler_provider_latency_seconds_v2 = Histogram(
    "newsiq_crawler_provider_latency_seconds_v2",
    "Latency of extraction by provider and domain.",
    ["provider", "domain"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, float("inf")),
)

newsiq_crawler_provider_cost_total_v2 = Counter(
    "newsiq_crawler_provider_cost_total_v2",
    "Estimated cost of extraction per provider and domain.",
    ["provider", "domain"],
)

newsiq_crawler_fallback_count_v2 = Counter(
    "newsiq_crawler_fallback_count_v2",
    "Total fallback count to external providers by domain.",
    ["domain"],
)

newsiq_crawler_failure_reason_total = Counter(
    "newsiq_crawler_failure_reason_total",
    "Total count of failure reasons by provider and domain.",
    ["provider", "failure_reason", "domain"],
)

# ── Story Clustering Hardening Metrics (Section 3) ───────────────────────────

newsiq_reflection_triggered_total = Counter(
    "newsiq_reflection_triggered_total",
    "Total number of reflection triggers by reason type.",
    ["reason_type"],
)

newsiq_reflection_timeout_total = Counter(
    "newsiq_reflection_timeout_total",
    "Total number of reflection timeouts by agent type.",
    ["agent_type"],
)

newsiq_reflection_fallback_total = Counter(
    "newsiq_reflection_fallback_total",
    "Total number of reflection fallbacks by type.",
    ["fallback_type"],
)

newsiq_reflection_cache_reused_total = Counter(
    "newsiq_reflection_cache_reused_total",
    "Total number of times cached Gemini reflection decisions were reused.",
)

newsiq_stage_a_pass_total = Counter(
    "newsiq_stage_a_pass_total",
    "Total number of Stage A checks that passed or borderline passed.",
    ["outcome"],
)

newsiq_stage_b_pass_total = Counter(
    "newsiq_stage_b_pass_total",
    "Total number of Stage B checks that passed or borderline passed.",
    ["outcome"],
)

