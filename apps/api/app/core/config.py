"""Application configuration loaded from environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings — all values sourced from environment variables.

    Never add a hardcoded default for secrets (API keys, passwords, tokens).
    Required secrets are validated at startup via validate_required_secrets().
    """

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "NewsIQ"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_SERVICE_ROLE: str = "monolith"
    USE_NEW_GATEWAY: bool = True
    MAX_PRO_MODEL_TOKENS: int = 30000

    # ── Database — Neon PostgreSQL ────────────────────────────────────────────
    # DATABASE_URL       → Pooled endpoint (PgBouncer). Used by FastAPI + Celery.
    # DATABASE_DIRECT_URL → Non-pooled direct connection. Used by Alembic only.
    #
    # For Neon:
    #   DATABASE_URL        = postgresql+asyncpg://...neon.tech/dbname?pgbouncer=true&sslmode=require
    #   DATABASE_DIRECT_URL = postgresql+asyncpg://...neon.tech/dbname?sslmode=require
    #
    # For local Docker (dev profile):
    #   DATABASE_URL = postgresql+asyncpg://newsiq:newsiq@postgres:5432/newsiq
    #   DATABASE_DIRECT_URL = (same as above)
    #
    DATABASE_URL: str = Field(default="postgresql+asyncpg://newsiq:newsiq@localhost:5432/newsiq")
    DATABASE_DIRECT_URL: str = Field(default="")  # Falls back to DATABASE_URL if empty
    DATABASE_SSL: bool = False  # Set to True in production (Neon requires SSL)

    # SQLAlchemy pool settings — tuned for Neon free tier (max 5 connections)
    # Scale up for paid Neon plans or self-hosted PostgreSQL
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_RECYCLE: int = 300  # Recycle connections every 5 min (serverless safety)

    # ── Redis — Upstash ───────────────────────────────────────────────────────
    # Upstash does not support multiple Redis DB indices.
    # Use 3 separate Upstash instances (all on free tier at MVP scale).
    #
    # TLS is automatic: if URL starts with "rediss://", SSL is enabled.
    #
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    # ── Object Storage ────────────────────────────────────────────────────────
    # STORAGE_BACKEND: r2 | s3 | minio | local
    STORAGE_BACKEND: Literal["r2", "s3", "minio", "local"] = "local"
    LOCAL_STORAGE_PATH: str = "./data/storage"

    # R2 / S3 / MinIO shared interface (provider selected by STORAGE_BACKEND)
    R2_ENDPOINT: str = ""
    R2_BUCKET: str = "newsiq"
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_PUBLIC_URL: str = ""

    # S3 / MinIO overrides (STORAGE_BACKEND=s3 or minio)
    S3_ENDPOINT: str = ""  # Leave empty for AWS S3; set for MinIO
    S3_BUCKET: str = "newsiq"
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "us-east-1"

    # ── Qdrant (kept local on VM) ──────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # ── Meilisearch (kept local on VM) ────────────────────────────────────────
    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_API_KEY: str = ""

    # ── Auth ─────────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(default="change-me-in-production-use-openssl-rand-hex-32")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"
    COOKIE_DOMAIN: str | None = None

    # ── OAuth — Google ────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── AI Models ─────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_EMBEDDING: str = ""
    GEMINI_API_KEY_SYNTH: str = ""
    NVIDIA_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    AWS_BEDROCK_BASE_URL: str = "https://bedrock-mantle.us-east-1.api.aws/v1"
    AWS_BEDROCK_API_KEY: str = ""
    EMBEDDING_MODEL: str = "gemini-embedding-2"
    SUMMARIZATION_MODEL: str = "gemini-3.1-flash-lite"

    # ── Pipeline Optimization ─────────────────────────────────────────────────
    PIPELINE_VERSION: str = "1.0.0"
    PIPELINE_CACHE_ENABLED: bool = True
    ENTITY_LINKING_MODE: str = "hybrid"  # hybrid | deterministic | llm
    INCREMENTAL_STORY_UPDATES: bool = True
    CONTEXT_EXTRACTOR_ENABLED: bool = True
    EMBEDDING_CACHE_ENABLED: bool = True
    MODEL_ROUTING_TABLE: dict[str, dict[str, str]] = {}

    # ── Cost Budget ───────────────────────────────────────────────────────────
    STORY_COST_BUDGET_DEFAULT: float = 0.005
    STORY_COST_BUDGET_HIGH_STAKES: float = 0.015
    STORY_COST_BUDGET_BREAKING: float = 0.020

    # ── News APIs ─────────────────────────────────────────────────────────────
    NEWSAPI_KEY: str = ""
    GNEWS_API_KEY: str = ""

    # ── News Discovery Pipeline Configuration ────────────────────────────────
    DISCOVERY_PROVIDER: str = "google_rss"
    DISCOVERY_MAX_RESULTS: int = 7
    DISCOVERY_CACHE_TTL: int = 6 * 3600  # 6 hours in seconds
    DISCOVERY_LOCK_TTL: int = 10 * 60  # 10 minutes in seconds
    DISCOVERY_MAX_CONCURRENT_DOWNLOADS: int = 5
    DISCOVERY_SCORE_THRESHOLD: float = 0.50
    DISCOVERY_DAILY_SEARCH_BUDGET: int = 1000
    DISCOVERY_DAILY_DOWNLOAD_BUDGET: int = 5000
    DISCOVERY_MAX_RETRIES: int = 3

    # ── Multi-Provider Extraction Configuration ──────────────────────────────
    TAVILY_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""
    TAVILY_BATCH_SIZE: int = 5
    TAVILY_BATCH_TIMEOUT_SECONDS: int = 2
    EXTRACTION_RESULT_TTL_SECONDS: int = 600
    EXTRACTION_PROVIDER_TIMEOUT: int = 30
    CRAWLER_MAX_CONCURRENT_REQUESTS: int = 5

    # Discovery Candidate Scoring Weights
    DISCOVERY_FRESHNESS_WEIGHT: float = 0.20
    DISCOVERY_TRUST_WEIGHT: float = 0.30
    DISCOVERY_ENTITY_WEIGHT: float = 0.30
    DISCOVERY_CONTENT_WEIGHT: float = 0.20

    # Trusted Publishers and their weights
    DISCOVERY_TRUSTED_PUBLISHERS: dict[str, float] = {
        "reuters": 1.0,
        "apnews": 1.0,
        "associated press": 1.0,
        "bbc": 0.95,
        "guardian": 0.9,
        "cnn": 0.9,
        "bloomberg": 0.95,
        "nytimes": 0.9,
        "new york times": 0.9,
        "washington post": 0.9,
        "independent": 0.8,
        "techcrunch": 0.8,
        "the verge": 0.8,
    }

    # ── SMTP ─────────────────────────────────────────────────────────────────
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 1025
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@newsiq.io"
    SMTP_FROM_NAME: str = "NewsIQ"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
    ]

    # ── Observability — Langfuse ──────────────────────────────────────────────
    # Langfuse Cloud: https://cloud.langfuse.com
    # Self-hosted:    http://langfuse:3000
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # ── Error Tracking — Sentry ───────────────────────────────────────────────
    SENTRY_DSN: str | None = None

    # ── Computed helpers ──────────────────────────────────────────────────────

    @property
    def database_direct_url(self) -> str:
        """Return the direct (non-pooled) DB URL for Alembic migrations.

        Falls back to DATABASE_URL when DATABASE_DIRECT_URL is not set.
        """
        return self.DATABASE_DIRECT_URL or self.DATABASE_URL

    @property
    def redis_uses_tls(self) -> bool:
        """True when REDIS_URL uses the rediss:// scheme (Upstash, etc.)."""
        return self.REDIS_URL.startswith("rediss://")

    @property
    def celery_broker_uses_tls(self) -> bool:
        """True when CELERY_BROKER_URL uses the rediss:// scheme."""
        return self.CELERY_BROKER_URL.startswith("rediss://")

    # ── Startup validation ────────────────────────────────────────────────────

    _INSECURE_DEFAULT_KEY = "change-me-in-production-use-openssl-rand-hex-32"

    def validate_required_secrets(self) -> list[str]:
        """Validate required secrets are set. Returns list of error messages.

        Call at startup. If any critical secret is missing/insecure in
        production, the application should refuse to start.
        """
        errors: list[str] = []

        if not self.DEBUG:
            if self.SECRET_KEY == self._INSECURE_DEFAULT_KEY:
                errors.append(
                    "SECRET_KEY is the insecure default. Generate with: openssl rand -hex 32"
                )
            if not self.DATABASE_URL or "localhost" in self.DATABASE_URL:
                errors.append(
                    "DATABASE_URL appears to be pointing at localhost in production. "
                    "Set it to your Neon/managed PostgreSQL endpoint."
                )

        return errors

    def emit_startup_report(self) -> None:
        """Print a startup configuration summary to stdout."""
        import logging

        log = logging.getLogger(__name__)

        log.info(
            "NewsIQ startup configuration:\n"
            "  Role:             %s\n"
            "  Debug:            %s\n"
            "  Database:         %s\n"
            "  Database SSL:     %s\n"
            "  Redis (cache):    %s\n"
            "  Redis (broker):   %s\n"
            "  Storage backend:  %s\n"
            "  Langfuse host:    %s\n"
            "  Langfuse enabled: %s\n"
            "  Sentry enabled:   %s\n"
            "  Gemini key:       %s\n"
            "  OpenRouter key:   %s\n"
            "  Bedrock key:      %s",
            self.BACKEND_SERVICE_ROLE,
            self.DEBUG,
            self.DATABASE_URL.split("@")[-1] if "@" in self.DATABASE_URL else self.DATABASE_URL,
            self.DATABASE_SSL,
            self.REDIS_URL.split("@")[-1] if "@" in self.REDIS_URL else self.REDIS_URL,
            self.CELERY_BROKER_URL.split("@")[-1]
            if "@" in self.CELERY_BROKER_URL
            else self.CELERY_BROKER_URL,
            self.STORAGE_BACKEND,
            self.LANGFUSE_HOST,
            bool(self.LANGFUSE_PUBLIC_KEY and self.LANGFUSE_SECRET_KEY),
            bool(self.SENTRY_DSN),
            "set" if self.GEMINI_API_KEY else "not set",
            "set" if self.OPENROUTER_API_KEY else "not set",
            "set" if self.AWS_BEDROCK_API_KEY else "not set",
        )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
