from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ExtractionFailure(StrEnum):
    SUCCESS = "SUCCESS"
    HTTP_ERROR = "HTTP_ERROR"
    HTTP_404 = "HTTP_404"
    HTTP_401 = "HTTP_401"
    HTTP_403 = "HTTP_403"
    TIMEOUT = "TIMEOUT"
    BOT_BLOCKED = "BOT_BLOCKED"
    EMPTY_HTML = "EMPTY_HTML"
    PARSER_FAILED = "PARSER_FAILED"
    PAYWALL = "PAYWALL"
    JS_REQUIRED = "JS_REQUIRED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractionDiagnostics:
    provider: str
    attempts: int
    latency_ms: float
    status_code: int | None
    bot_detected: bool
    notes: list[str]
    fetch_method: str | None = None


@dataclass
class ExtractionResult:
    success: bool
    provider: str
    failure: ExtractionFailure | None
    url: str
    title: str | None
    content: str
    author: str | None
    image_url: str | None
    published_at: datetime | None
    diagnostics: ExtractionDiagnostics

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation for caching/serialization."""
        return {
            "success": self.success,
            "provider": self.provider,
            "failure": self.failure.value if self.failure else None,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "image_url": self.image_url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "diagnostics": {
                "provider": self.diagnostics.provider,
                "attempts": self.diagnostics.attempts,
                "latency_ms": self.diagnostics.latency_ms,
                "status_code": self.diagnostics.status_code,
                "bot_detected": self.diagnostics.bot_detected,
                "notes": self.diagnostics.notes,
                "fetch_method": self.diagnostics.fetch_method,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExtractionResult:
        """Construct an ExtractionResult from a dictionary."""
        diag_data = data.get("diagnostics") or {}
        diagnostics = ExtractionDiagnostics(
            provider=diag_data.get("provider", ""),
            attempts=diag_data.get("attempts", 1),
            latency_ms=diag_data.get("latency_ms", 0.0),
            status_code=diag_data.get("status_code"),
            bot_detected=bool(diag_data.get("bot_detected", False)),
            notes=list(diag_data.get("notes") or []),
            fetch_method=diag_data.get("fetch_method"),
        )

        published_at = None
        pub_at_raw = data.get("published_at")
        if pub_at_raw:
            try:
                published_at = datetime.fromisoformat(pub_at_raw)
            except Exception:
                pass

        failure = None
        failure_raw = data.get("failure")
        if failure_raw:
            try:
                failure = ExtractionFailure(failure_raw)
            except Exception:
                pass

        return cls(
            success=bool(data.get("success", False)),
            provider=data.get("provider", ""),
            failure=failure,
            url=data.get("url", ""),
            title=data.get("title"),
            content=data.get("content", ""),
            author=data.get("author"),
            image_url=data.get("image_url"),
            published_at=published_at,
            diagnostics=diagnostics,
        )
