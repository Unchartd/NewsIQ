# NewsIQ Release & Validation Report

* **Version**: v1.0.0 (Production Baseline)
* **Timestamp**: 2026-07-10
* **Status**: Passed & Ready for PR

This validation report summarizes the testing, quality gates, and database migration alignment performed to establish the NewsIQ **v1.0 Production Baseline**.

---

## 1. Quality Gates & Test Execution

### 1.1 Full Test Suite (pytest)
- **Result**: `SUCCESS`
- **Total Tests Run**: 173
- **Passed**: 173
- **Warnings**: 57 (minor deprecations and XML parsing warnings)
- **Execution Time**: 130.94s

### 1.2 Golden Dataset Evaluation (`test_golden_eval.py`)
- **Result**: `SUCCESS`
- **Passed**: 1 (runs comprehensive LLM-grounded semantic quality checks on the golden news dataset)
- **Execution Time**: 28.68s

### 1.3 Pipeline Replay Benchmark (`pipeline_replay.py`)
- **Result**: `SUCCESS`
- **Dataset Mode**: historical (Mocked Offline)
- **Articles Processed**: 10
- **Success Rate**: 100.0%
- **Clustering Latency**: 106.2ms
- **Direct Merges**: 0
- **Sent to Discovery Queue**: 10

---

## 2. Code Quality & Standards

### 2.1 Linter & Formatter (Ruff)
- Ruff linter checks were run across the entire backend code.
- Deployed automatic fixes for **525 warnings** (import sorting, trailing whitespace, and basic formatting).
- Fixed the undefined `logger` bug in `apps/api/app/services/auth_service.py` and moved its initialization below the imports to satisfy module-level checks (`E402`).
- Fixed the undefined `settings` bug in `apps/api/app/ai/gateway.py` by importing `settings` locally within the token truncation method.
- Cleaned up the unused `anchor` variable warning (`F841`) in `apps/api/app/services/clustering_service.py`.

---

## 3. Database Migration Status

### 3.1 Migration Head
- **Alembic Head**: `5bdb4b86da16` (epic7_synthesis_schema)
- **Database Status**: `Up-to-date`
- **Correction Applied**: Fixed a bug in `apps/api/alembic/env.py` where DDL changes and migrations for non-fresh database runs were not being committed (connection lacked `connection.commit()`), causing migrations to fail to persist. Applied `connection.commit()` so all tables (`synthesis_artifacts`, `story_versions`, `story_reviews`, `pipeline_traces`) and column schema updates (`stories.current_version_id`) are now fully persisted.

---

## 4. Repository Cleanup Summary

- **Archived Docs**: Moved historical PRD, requirements, UX designs, and early AI/remediation design briefs to `docs/archive/`.
- **Relocated Contracts**: Moved root `interfaces_contract.md` to `docs/architecture/interfaces-contract.md`.
- **Deleted Scratch Files**: Removed 38 local scratch scripts (`scratch_*.py`), temporary HTML/CSS mockup dumps from the root, and unused database drop scripts.
- **Removed Dead Code**: Confirmed dead code services (`ner_service.py`) are deleted and test files updated to use production-standard modules (`ner_service_v2.py`).
