# NewsIQ Observability Metrics Spec

This document details the metrics dashboard, Prometheus labels, and Prometheus exposition format exposed by the `/metrics` endpoint.

---

## 1. Metric Types and Labels

To support dashboard visualizations in Grafana, we publish metrics annotated with standard labels:
*   `stage`: The pipeline stage name.
*   `provider`: The AI/Embedding provider name.
*   `model`: The specific LLM model version.
*   `status`: The result status of the operation (`success`, `failed`, `skipped`).
*   `source`: The name of the news source or feed domain.
*   `queue`: The Celery queue name.

---

## 2. Ingestion & Pre-processing Metrics

#### `newsiq_articles_ingested_total`
*   **Type:** Counter
*   **Description:** Total count of raw articles ingested from sources.
*   **Labels:** `source` (e.g. `bbc-news`), `type` (`rss`, `gnews`)

#### `newsiq_crawler_latency_seconds`
*   **Type:** Histogram
*   **Description:** HTTP request and parser duration for crawling full-text pages.
*   **Labels:** `source`, `extractor` (`newspaper4k`, `trafilatura`, `readability`, `custom-bs4`)

#### `newsiq_dedup_duplicates_total`
*   **Type:** Counter
*   **Description:** Count of duplicate articles blocked.
*   **Labels:** `source`, `method` (`url_exact`, `semantic_title`)

---

## 3. Core Pipeline Stage Metrics

#### `newsiq_pipeline_stage_latency_seconds`
*   **Type:** Histogram
*   **Description:** Time spent in each pipeline stage.
*   **Labels:** `stage`, `status`

#### `newsiq_pipeline_runs_total`
*   **Type:** Counter
*   **Description:** Number of triggered pipeline runs.
*   **Labels:** `trigger` (`celery_beat`, `manual`, `replay`), `status`

#### `newsiq_story_clusters_created_total`
*   **Type:** Counter
*   **Description:** Number of story clusters formed during batch clustering.
*   **Labels:** `method` (`hdbscan`, `incremental_merge`)

---

## 4. LLM & Token Metrics

#### `newsiq_llm_tokens_consumed_total`
*   **Type:** Counter
*   **Description:** Total token usage.
*   **Labels:** `provider`, `model`, `stage`, `type` (`input`, `output`)

#### `newsiq_llm_cost_usd_total`
*   **Type:** Counter
*   **Description:** Aggregated dollar spending.
*   **Labels:** `provider`, `model`, `stage`

#### `newsiq_provider_availability_ratio`
*   **Type:** Gauge
*   **Description:** Average success rate of LLM completions.
*   **Labels:** `provider`, `model`

---

## 5. Queue & Worker Health Metrics

#### `newsiq_queue_depth_jobs`
*   **Type:** Gauge
*   **Description:** Number of waiting tasks in the broker.
*   **Labels:** `queue`

#### `newsiq_worker_active_threads`
*   **Type:** Gauge
*   **Description:** Active execution threads.
*   **Labels:** `worker_name`

---

## 6. Grafana Dashboards

The `/metrics` endpoint exposes this data directly for Prometheus scraping. In Grafana, SREs monitor these panels in real-time:
1.  **AI Pipeline Command Center:** Visualizes overall active runs, latency histograms, and recent failures.
2.  **Model Cost & Token Budgets:** Displays cumulative cost trends, token consumption rates, and dollar distributions across providers.
3.  **Crawler & Ingestion Throughput:** Tracks news source fetch counts, canonicalization rates, and page extraction fallback ratios.
