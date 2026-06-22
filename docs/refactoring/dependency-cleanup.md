# Dependency Cleanup Report

An audit of dependencies in `pyproject.toml`.

## Identified Unused Libraries
- **`hdbscan`**: Wait, HDBSCAN is used in `clustering_service.py` to group article vectors! It is active and MUST be kept.
- **`spacy`**: spaCy is used as a fallback in `ner_service_v2.py`. It is active and MUST be kept.
- **`scikit-learn`**: Scikit-learn is used in event/vector logic (like cosine similarity or dimension reduction if any).
- **`sentence-transformers`**: Used to generate embeddings if local mode is selected.
- **`python-multipart`**: Used by FastAPI for file/form uploads.
- **`readability-lxml`**, `trafilatura`, `newspaper4k`, `beautifulsoup4`: RSS/ingestion dependencies.
- **`uuid7`**: Used to generate UUID v7 primary keys.
- **`langfuse`**, `sentry-sdk`, `prometheus-client`: Observability package dependencies.

## Confirmed Duplicate Packages
None.

## Deprecated Libraries
- `spacy-legacy` (not in `pyproject.toml` but referenced in `uv.lock` as a transitive dependency of spaCy): Keep.
