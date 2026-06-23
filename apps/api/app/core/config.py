"""Application configuration loaded from environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings."""

    # App
    APP_NAME: str = "NewsIQ"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_SERVICE_ROLE: str = "monolith"

    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://newsiq:newsiq@localhost:5432/newsiq")

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # Meilisearch
    MEILISEARCH_URL: str = "http://localhost:7700"
    MEILISEARCH_API_KEY: str = ""

    # Auth
    SECRET_KEY: str = Field(default="change-me-in-production-use-openssl-rand-hex-32")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    # OAuth - Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/api/auth/callback/google"

    # AI Models
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_EMBEDDING: str = ""
    GEMINI_API_KEY_SYNTH: str = ""
    GROQ_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    NVIDIA_API_KEY: str = ""  # NVIDIA NIM Build API (nvapi-...)
    EMBEDDING_MODEL: str = "text-embedding-004"
    SUMMARIZATION_MODEL: str = "gemini-2.5-flash"       # No daily quota exhaustion, confirmed working

    # News APIs
    NEWSAPI_KEY: str = ""
    GNEWS_API_KEY: str = ""

    # SMTP Settings
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 1025
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "noreply@newsiq.io"
    SMTP_FROM_NAME: str = "NewsIQ"
    FRONTEND_URL: str = "http://localhost:3000"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Monitoring
    SENTRY_DSN: str | None = None

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
