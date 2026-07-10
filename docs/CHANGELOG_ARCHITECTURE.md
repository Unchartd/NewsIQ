# Architecture Changelog: NewsIQ Platform

* **Baseline Version**: v1.0 (Production Baseline)
* **Status**: Approved & Frozen
* **Date**: 2026-07-10

This document tracks major architectural transitions, refactorings, and design decisions across the NewsIQ codebase leading to the frozen **v1.0 Production Baseline**.

---

## [v1.0.0] - 2026-07-10

### Added
- **Staged Story Synthesis Orchestrator (Pipeline C)**: Deployed a 7-stage sequential orchestration pipeline coordinating Knowledge Graph generation, Contradiction Detection, Source Comparison, Timeline Compiling, Summarization, QA Feedback evaluation, and Atomic Publishing.
- **Programmatic Quality Gates (Feedback Agent)**: Added HHI source diversity index scoring, clustering density checks, timeline chronological ordering checks, and automated section-level summarization corrections.
- **Immutable Artifact Offloading**: Split transient JSON payloads from the core database models into a dedicated `synthesis_artifacts` table, linked via UUID foreign keys in `story_versions`.
- **Administrative Telemetry Dashboard**: Deployed a Next.js 16 admin portal showcasing queue sizes, RSS ingestion throughput, latency waterfalls per stage, and provider availability precomputed asynchronously via Celery Beat tasks.
- **Centralized LLM Gateway**: Standardized all AI agent model invocations under the unified gateway for automatic rate-limiting, token tracking, backoff retries, and provider fallback routing.

### Changed
- **Timeline Compiler Consolidation**: Unified deterministic chronological timeline parsing into a single helper class (`TimelineCompiler`), removing duplicate legacy versions from `generate_story_content` and `update_story_incrementally`.
- **Converged Synthesis Invocations**: Bypassed parallel and redundant incremental update paths. Both batch and merge triggers now flow through the single orchestration pipeline.
- **Isolated Testing Boundaries**: Extracted timeline tests from DB/LLM dependencies to target `TimelineCompiler` directly.

### Removed
- **Unused Legacy Services**: Deleted `ner_service.py` (replaced by spaCy + LLM hybrid `ner_service_v2.py`).
- **Legacy Synthesis Code**: Deleted old `analyze_story` one-pass summarization prompts and associated sub-methods in `ai_service.py`.
- **Redundant Debug Scripts**: Pruned 38 temporary scratch check and test python files from the api root directory to keep the development space clean.

---

## [v0.2.0] - 2026-07-02
- Deployed Pipeline B (Event Identity, Lifecycle Management, and Canonical IDs).
- Introduced HDBSCAN clustering parameters validation.

## [v0.1.0] - 2026-06-15
- Initial release of Pipeline A (Ingestion, crawlers, and basic deduplication).
- Deployed baseline Broadsheet user interface.
