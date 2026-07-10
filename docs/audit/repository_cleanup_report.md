# NewsIQ Repository Audit & Cleanup Report

* **Version**: 1.0 (Audit Baseline)
* **Status**: Pending Review & Approval
* **Last Updated**: 2026-07-10
* **Author**: Antigravity (AI Coding Assistant)

This report provides a comprehensive analysis of the NewsIQ repository to align all code, documentation, files, and dependencies with the frozen **Architecture v1.0 (Production Baseline)**. No modifications have been made; this is a pure audit assessment.

---

## 1. Documentation Audit

An audit of all Markdown files (`*.md`) in the repository has been performed to classify them into action categories: **Keep**, **Merge**, **Archive**, or **Delete**.

### 1.1 Root Markdown Files
| Document Name | Purpose | Recommendation | Rationale |
| :--- | :--- | :--- | :--- |
| `README.md` | General landing and onboarding guide | **Keep & Update** | Needs update to reflect Pipeline A/B/C v1.0 structure and remove legacy references. |
| `interfaces_contract.md` | Shared interfaces contract between components | **Merge** | Merge into `docs/architecture/interfaces-contract.md` to consolidate architecture documentation. |
| `implementation_plan.md` | Historic Epic 7 (Multi-Stage Story Synthesis) plan | **Archive** | Move to `docs/archive/epic7-synthesis-plan.md` for historic record. |
| `newsiq_system_architecture.md` | Legacy system overview document | **Archive** | Move to `docs/archive/legacy-system-architecture.md` (superseded by v1.0 docs). |
| `NewsIQ Complete Product Audit & Gap Analysis.md` | Initial product gap analysis | **Archive** | Move to `docs/archive/product-audit-gap-analysis.md`. |
| `Product Requirements Document.md` | Baseline product specification | **Keep** | Retain as product baseline. |
| `Technical Requirements Document.md` | Baseline technical specification | **Keep** | Retain as technical baseline. |
| `UX Design Brief.md` | UX asset references | **Keep** | Retain as UI reference. |
| `UX Flow Document.md` | UX flow references | **Keep** | Retain as UX flow reference. |
| `data_pipeline_flowcharts.md` | Raw Mermaid pipeline flowcharts | **Archive** | Move to `docs/archive/data-pipeline-flowcharts.md`. |

### 1.2 `docs/` Root & Subdirectory Markdown Files
| Document Name | Path | Recommendation | Rationale |
| :--- | :--- | :--- | :--- |
| `consent-flow.md` | GDPR/Consent architecture | **Keep** | Regulatory compliance. |
| `cookie-architecture.md` | Cookie management design | **Keep** | Regulatory compliance. |
| `cookie-inventory.md` | Cookie list inventory | **Keep** | Regulatory compliance. |
| `cookies-technical.md` | Cookie technical specs | **Keep** | Regulatory compliance. |
| `documentation-audit.md` | Legacy documentation audit log | **Delete** | Temporary file, fully obsolete. |
| `drift-report.md` | Stale schema/prompt drift logs | **Delete** | Temporary file, fully obsolete. |
| `event_identity_architecture.md`| Pipeline B (Identity) frozen spec | **Keep** | Core v1.0 architecture. |
| `legal-audit.md` | Compliance audit details | **Keep** | Regulatory compliance. |
| `legal-implementation-checklist.md` | Compliance checklist | **Keep** | Regulatory compliance. |
| `privacy-compliance.md` | General privacy specs | **Keep** | Regulatory compliance. |
| `security-review.md` | General security review | **Keep** | Security compliance. |
| `docs/architecture/` files | Entire contents | **Keep** | All system overview and data-flow documents are active and useful. |
| `docs/decisions/` files | ADR-001 through ADR-005 | **Keep** | Historic architectural decision records. |
| `docs/runbooks/` files | Outage and recovery guides | **Keep** | Deployed operational guides. |
| `docs/ai/` files | Prompt versioning, Cache strategies, Roadmap | **Archive** | Replaced and consolidated by `story-synthesis-architecture.md` in v1.0. Move to `docs/archive/ai/`. |
| `docs/observability/` files | Tracing, Logging, Metrics, Replays | **Keep & Consolidate**| Active, but clean up duplicate references. |
| `docs/refactoring/` files | cleanup plans, dead code reports | **Archive / Delete** | Safe to delete temporary cleanups once Phase 2 completes. |
| `docs/remediation/` files | concurrency fixes, kg-redesign | **Archive** | Move to `docs/archive/remediation/` for historic reference. |

---

## 2. Code Audit

A search of the Python codebase (`apps/api/app/`) shows redundant, unused, or duplicate components.

### 2.1 Verified Dead Code
* **`apps/api/app/services/ner_service.py`**: Legacy spaCy NER extractor. Completely bypassed by `ner_service_v2.py`.
  * *Cleanup Action*: Update the single legacy import in `tests/test_clustering.py` and delete this file.
* **`ai_service.analyze_story`**: Single one-pass story analysis method inside `apps/api/app/services/ai_service.py`. Bypassed by the multi-stage pipeline.
  * *Cleanup Action*: Remove this method and its sub-helpers (`_analyze_with_gemini`, `_analyze_with_openai`, `_generate_mock_response`, `_normalize_gemini_response`) from `ai_service.py`. Update tests to mock the active `summarize_story_from_kg` method.
* **`update_story_incrementally`**: Bypassed incremental synthesis method inside `apps/api/app/services/clustering_service.py`. Fully replaced by `story_synthesis_orchestrator.synthesize_story`.
  * *Cleanup Action*: Delete this method.

### 2.2 Deprecated Interfaces & Client Initializations
* **Scattered Client Initializations**: `ner_service_v2.py`, `event_service.py`, `entity_linker.py`, `source_comparison_service.py`, and `contradiction_service.py` all define their own `_gemini_client` or `_openai_client` and call raw clients directly instead of using the `llm_gateway`.
  * *Cleanup Action*: Refactor these classes to import `llm_gateway` and execute requests via `llm_gateway.execute_request` to ensure proper rate-limiting, observability, and fallback routing.
* **TODO/FIXME/HACK Comments**: Codebase is clean of `TODO` or `FIXME` comments. The only `HACK` reference is in the event taxonomy mapping (`"hacked": "ATTACK"`), which is active and correct.

---

## 3. File Audit

An audit of files in the workspace root and the `apps/api` directory was performed.

### 3.1 Temporary Scripts (Safe to Delete)
These scripts were used for local debugging and are obsolete in a production baseline:
* **Workspace Root**:
  - `get_head.py` (simple debug script)
  - `extract_pdfs.py` (duplicate of apps/api script)
  - `profile.html`, `landing.html`, `index.html` (static HTML dumps)
  - `profile_settings_styles.css`, `profile_settings_append.css`, `profile_styles_dump.css` (static CSS assets)
* **`apps/api/` Root**:
  - `check_db.py`, `check_meta.py`, `drop_db.py`, `drop_schema.py` (temporary DB verification scripts)
  - `run_clustering.py`, `search_admin_endpoints.py` (temporary CLI helpers)
  - `scratch_check_*.py` (22 separate scratch checking scripts: `check_qdrant.py`, `debug_clustering.py`, `monitor.py`, etc.)
  - `verify_canonical_ids.py` (redundant CLI checking script)

### 3.2 Old Generated Artifacts & Reports (Safe to Delete or Move)
* `apps/api/benchmark_baseline.json` & `apps/api/benchmark_baseline.py` (rebuilt dynamically by the replay suite)
* `apps/api/evaluation_report.json` & `apps/api/pipeline_benchmark_report.md` (rebuilt during validation)
* `apps/api/pipeline_replay_history.json` (historic replay scores; back up before pruning)

---

## 4. Dependency Audit

Dependencies are defined cleanly in their respective directories, with versions pinned and locked:

### 4.1 Python Dependencies (`apps/api/pyproject.toml`)
* **Unused Packages**: Spacy dependency `en_core_web_sm` is active for NER fallback. `sentence-transformers` is active for clustering. All other packages listed in `pyproject.toml` are imported and active.
* **Version conflicts**: Zero conflicts found; local testing runs cleanly under the locked virtual environment `uv.lock`.

### 4.2 npm Dependencies (`apps/admin/package.json` & `apps/web/package.json`)
* Both React next-generation frontends are cleanly aligned:
  - `newsiq-admin`: Next.js 16.2.9, React 19.0.0, Recharts 3.8.1, Zustand 5.0.3, Lucide React 0.469.0.
  - `web`: Next.js 16.2.9, React 19.2.4, Vaul 1.1.2, Framer Motion 12.40.0, Lucide React 1.17.0.
* **Recommendation**: Prune `node_modules` and run package lock audits to confirm no outstanding dependency vulnerabilities exist.

---

## 5. Next Steps & Approval Gate

Upon receiving your approval on this report, we will execute **Phase 2 (Cleanup)** and **Phase 3 (Documentation Refresh)** in atomic, compile-passing commits as specified in the clean-up plan.
