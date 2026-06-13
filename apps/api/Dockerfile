FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Copy project files
COPY pyproject.toml .

# Pre-install CPU-only PyTorch to avoid massive CUDA dependencies (saves ~5+ GB)
RUN uv pip install --system --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining project dependencies without caching wheels in the image
RUN uv pip install --system --no-cache-dir -e ".[dev]"

# Pre-download spaCy model to avoid runtime downloads
RUN python -m spacy download en_core_web_sm

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
