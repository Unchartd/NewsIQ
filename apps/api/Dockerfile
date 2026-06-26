FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv and upgrade setuptools to patch CVE-2025-47273 path traversal vuln
RUN pip install --no-cache-dir uv && pip install --no-cache-dir -U "setuptools>=78.1.1"

# ── Dependency layer (cached unless pyproject.toml changes) ──────────────────

COPY pyproject.toml .

# Pre-install CPU-only PyTorch to avoid massive CUDA dependencies (~5 GB saved)
RUN uv pip install --system --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining project dependencies
RUN uv pip install --system --no-cache-dir -e ".[dev]"

# Pre-download spaCy model to avoid runtime network downloads
RUN python -m spacy download en_core_web_sm

# ── Application layer ─────────────────────────────────────────────────────────

COPY . .

# Create storage and prometheus directories
RUN mkdir -p /app/data/storage /tmp/prometheus_multiproc

EXPOSE 8000

# Health check — verifies the API is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default: production uvicorn (no --reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
