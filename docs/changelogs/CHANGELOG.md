# Changelog

All notable changes to the NewsIQ platform will be documented in this file.

This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.9.0-dev] - 2026-07-02

### Added
- **Centralized Structured AI Gateway (`app/ai/`)**: Implemented a production-grade AI gateway supporting capability routing, API key rotation, circuit breaking, automatic failover, Redis caching, and Prometheus telemetry.
- **Robust Output Schema Validation**: Added automated JSON unnesting, camelCase/PascalCase to snake_case field mapping, and type coercion in `clean_json_for_schema` to handle variations in LLM outputs.
- **Circuit Breaker Circuit Telemetry**: Track consecutive provider errors and trip unhealthy channels for 5 minutes, with self-healing background heartbeat checks running every 2 minutes.
- **Daily Story Cost Budgeting**: Circuit breaker pattern to enforce strict daily USD budgets at the story synthesis level.
- **Batch Embedding Cache**: Wired Redis caching and batch execution into `EmbeddingService` to reduce latency and Gemini API costs.
- **Pipeline Health Dashboard**: Created a Grafana telemetry dashboard and alerting rules to monitor LLM token consumption, latencies, error rates, and costs.
- **Admin UI Pipeline Dashboard**: Built a Next.js admin page at `/admin/quality` to visualize pipeline execution health, cache statistics, and evaluation runs.
- **Golden Scenario Evaluation Runner**: Designed a 5-scenario evaluation runner with strict quality gates (average score target >= 80%) to test end-to-end processing quality.

### Fixed
- **Empty News Cards Pipeline Leak**: Resolved a production issue where stories with blank headlines/summaries were visible to clients:
  - Flipped initial story creation status to `pending` and only promoted to `active` after synthesis successfully runs.
  - Added strict SQL query guards to `/stories`, search, and feed endpoints to exclude pending/failed or empty headline/summary stories.
  - Ensured `GET /stories/{id}` returns `404 Not Found` for stories that are not active or are missing content.
  - Removed unsafe exception handler fallbacks that were writing empty strings to the database on parsing failures.

## [1.8.0-dev] - 2026-06-19

### Added
- **Consent Management Platform (CMP)**: Detailed technical specifications and sequence flows for GDPR, CCPA, CPRA, and DPDPA compliance.
- **CMP Database Schemas**: Added SQL tables `consent_preferences` and `consent_audit_logs`.
- **Anonymized Audits**: Implemented salted IP address hashing (`SHA-256`) to satisfy GDPR data minimization requirements in consent audit logging.
- **Centralized Documentation Hub**: Consolidated all technical specifications, database designs, API endpoints, and running configurations under `/docs`.
- **Drift Detection Tooling**: Added a automated python validation script (`drift-check.py`) to raise warning flags when API route annotations diverge from markdown documents.
- **AEO/GEO & SEO Optimizations**: Dynamic sitemaps, semantic Schema.json breadcrumbs and JSON-LD structural graphs, Speakable voice assistant tags, robots.txt bot rules, and Apple Touch icons, favicons, and manifest metadata configurations.
- **Key Entities UX Redesign**: Grouped story entities by type (`PERSON`, `ORG`, `LOCATION`, etc.) and deduplicated values case-insensitively. Added interactive, inline-expandable tags with a `+N more` toggle state.

### Fixed
- **Summary Depth Switcher Contrast**: Corrected button text visibility in dark mode by dynamically styling the active state using `var(--background)` to contrast against `var(--ink)`.
- **Source Name Deduplication**: Deduplicated source names in the story detail AI summary subheader using a Set to prevent repeated publisher names when multiple articles belong to the same source.

---

## [1.7.0] - 2026-05-12

### Added
- **Next-Generation Gemini SDK Integration**: Upgraded synthesis and embedding pipelines to `google-genai>=1.16.0` (using the new async client).
- **Model Fallback Chain**: Created automated fallback configurations (`gemini-2.5-flash-lite` ➡️ `gemini-2.5-flash` ➡️ `gemini-2.0-flash` ➡️ `gpt-4o-mini`) to handle `RESOURCE_EXHAUSTED` (429) API errors.
- **Tenacity Retry Policies**: Configured randomized jitter exponential backoffs on LLM calls to handle rate-limiting.
- **Distributed Synthesis Throttling**: Implemented a Redis-based rate limit of `8.0 seconds` between synthesis requests across all Celery workers.

### Fixed
- **Celery Prefork Connection Leak**: Resolved the asyncpg engine inheritance bug (`RuntimeError: Task got Future attached to a different loop`) inside Celery processes by programmatically disposing of SQLAlchemy sync engines inside tasks.
- **Cascading Deletes**: Added foreign key cascade triggers (`all, delete-orphan`) on user preferences and consent tables to support clean GDPR account deletion flows.

---

## [1.6.0] - 2026-03-24

### Added
- **Global Rate Limiting**: Mounted sliding-window rate limiters (100 requests / 60 seconds per IP) using Redis keys.
- **Named Entity Recognition**: Added spaCy `en_core_web_sm` model parsing with automatic download checks.
- **NER Regex Fallback**: Created regex proper-noun parser fallback for local developer setups without spaCy packages.
- **Scraper Boilerplate Filter**: Built hierarchical HTML cleaning stack (`newspaper4k` ➡️ `trafilatura` ➡️ `readability-lxml` ➡️ `custom-bs4`) to remove ads, menu selectors, and footer boilerplate from crawled text.

---

## [1.5.0] - 2026-01-15

### Added
- **Initial Setup**: Consolidated Next.js frontend app and FastAPI backend codebases inside a unified mono-repository.
- **PostgreSQL & Redis Integrations**: Initialized SQLAlchemy models, Alembic migrations, and Redis caching decorators.
- **Qdrant Vector DB Ingestion**: Added cosine vector indexing (768 dimensions) for article similarity analysis.
