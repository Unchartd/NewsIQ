from typing import Any
from pydantic import BaseModel

class RCAReport(BaseModel):
    category: str
    confidence: float
    description: str
    remediation: str

class RootCauseAnalysisService:
    """Classifies pipeline errors and tracebacks to output actionable fixes."""

    @staticmethod
    def classify_error(
        error_msg: str | None,
        error_type: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> RCAReport | None:
        if not error_msg and not error_type:
            return None

        msg_lower = (error_msg or "").lower()
        type_lower = (error_type or "").lower()
        meta = metadata or {}

        # Rule 1: LLM Rate Limits
        if any(w in msg_lower for w in ["429", "rate limit", "quota exceeded", "ratelimiterror", "too many requests"]):
            return RCAReport(
                category="LLM_RATE_LIMIT",
                confidence=0.95,
                description="LLM provider rejected the request due to token or request per minute (RPM/TPM) rate limit exhaustion.",
                remediation="Configure exponential backoff jitter on LLM clients, increase Langfuse/provider organization tier limits, or switch to low-cost fallback models (e.g. Gemini-2.5-flash).",
            )

        # Rule 2: LLM Context Window
        if any(w in msg_lower for w in ["context length", "max tokens", "context window", "too long", "token limit"]):
            return RCAReport(
                category="LLM_CONTEXT_WINDOW_EXCEEDED",
                confidence=0.90,
                description="The input payload injected into the prompt templates exceeded the model's context window budget.",
                remediation="Apply adaptive token budgeting, summarize large documents before embedding/extracting, or route to models with larger context windows (e.g. Gemini-1.5-pro).",
            )

        # Rule 3: Database Connection Pools / Timeout
        if any(w in msg_lower for w in ["timeout", "connection pool", "operationalerror", "interfaceerror", "too many connections"]):
            return RCAReport(
                category="DATABASE_TIMEOUT",
                confidence=0.85,
                description="PostgreSQL asyncpg connection pool exhausted or queries timed out under high ingestion load.",
                remediation="Optimize SQLAlchemy pool size / max_overflow settings, index slow query columns, or scale PostgreSQL max_connections configuration.",
            )

        # Rule 4: Vector Database Unavailable
        if any(w in msg_lower for w in ["qdrant", "connectionrefused", "vector db", "cannot connect to vector"]):
            return RCAReport(
                category="VECTOR_DB_UNAVAILABLE",
                confidence=0.95,
                description="Unable to establish a gRPC or HTTP connection to the Qdrant vector database service.",
                remediation="Ensure the newsiq-qdrant docker container is running, check network bridges, or retry Qdrant client connection initialization.",
            )

        # Rule 5: Resource OOM (Out of Memory)
        memory_usage = meta.get("resource_usage", {}).get("memory_percent", 0.0)
        if memory_usage > 95.0 or "memoryerror" in msg_lower or "oom" in msg_lower:
            return RCAReport(
                category="OUT_OF_MEMORY",
                confidence=0.90,
                description="Stage worker terminated due to Out-Of-Memory (OOM) error, consuming maximum container resources.",
                remediation="Enable generator chunking on batch processing steps, reduce batch sizes, or increase system RAM allocations in docker-compose limits.",
            )

        # Rule 6: Ingestion RSS Parsing Failure
        if any(w in msg_lower for w in ["feedparser", "xml parsing", "beautifulsoup", "newspaper4k", "crawling failed"]):
            return RCAReport(
                category="RSS_INGESTION_FAILURE",
                confidence=0.80,
                description="Failed to parse the target XML feed payload or download raw article HTML content.",
                remediation="Configure a proxy router (e.g. scrape-ops), sanitize feed XML encodings, or skip transient invalid content.",
            )

        # Default fallback
        return RCAReport(
            category="UNKNOWN_PIPELINE_ERROR",
            confidence=0.50,
            description="The stage threw an unhandled runtime exception.",
            remediation="Review stack trace logs for specific line numbers, verify function signatures, and validate environment secrets configuration.",
        )
