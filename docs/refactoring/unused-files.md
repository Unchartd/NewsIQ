# Unused & Temporary Files Report

The following files are unused by the production app runtime and represent dead code, obsolete scripts, or duplicate implementations.

## 1. Dead Code / Services
- **`apps/api/app/services/ner_service.py`**
  - *Status*: Unused. Replaced by `ner_service_v2.py`.
  - *Recommendation*: Delete. Update references in `tests/test_clustering.py`.

## 2. Temporary Debugging & Helper Scripts
The following scripts at the root and in the api root are temporary scripts used in development that should not remain in a clean production repository:
- **`apps/api/check_db.py`**
  - *Status*: Used to verify database connection and counts. Unused in production.
  - *Recommendation*: Delete or move to `scripts/` folder.
- **`apps/api/check_pipeline_errors.py`**
  - *Status*: Script to check pipeline status. Unused in production.
  - *Recommendation*: Delete.
- **`apps/api/check_stages.py`**
  - *Status*: Script to check tracing stages. Unused in production.
  - *Recommendation*: Delete.
- **`apps/api/check_traceback.py`**
  - *Status*: Unused.
  - *Recommendation*: Delete.
- **`apps/api/test_query.py`**
  - *Status*: Temporary search query test script.
  - *Recommendation*: Delete.
- **`apps/api/extract_pdfs.py`**
  - *Status*: Temporary PDF extraction helper.
  - *Recommendation*: Delete.
- **`extract_pdfs.py`** (at workspace root)
  - *Status*: Duplicate of above.
  - *Recommendation*: Delete.
- **`profile.html`**, **`landing.html`**, **`index.html`** (at workspace root)
  - *Status*: HTML dumps / static designs.
  - *Recommendation*: Move to a design/ or UI mocks folder if needed, or delete.
- **`profile_settings_styles.css`**, **`profile_settings_append.css`**, **`profile_styles_dump.css`** (at workspace root)
  - *Status*: Static styling assets.
  - *Recommendation*: Delete or move.
