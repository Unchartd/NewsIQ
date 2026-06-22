"""Application logging configuration.

Delegates to structlog-based structured logging (structured_logging.py).
Preserves the request_id context variable for the FastAPI middleware.
"""

from contextvars import ContextVar

# Context variable to store request ID across async calls.
# Used by the request_id_middleware in main.py.
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def setup_logging(debug: bool = False) -> None:
    """Initialize structured logging for the application.

    This is the main entry point called from main.py on startup.
    Configures structlog with trace context injection, JSON output,
    and stdlib logger integration.
    """
    from app.core.structured_logging import setup_structlog

    setup_structlog(debug=debug)

