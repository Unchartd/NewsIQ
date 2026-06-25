"""Application startup validation and report generation.

Called during the FastAPI lifespan startup event. Verifies all required
infrastructure is reachable and configured before accepting traffic.

Design:
  - Critical services (DB, Redis) → fail hard if unreachable (raises RuntimeError)
  - Non-critical services (Langfuse, Storage) → log warning, continue
  - Missing secrets in production → fail hard

Usage:
    async with lifespan(app):
        await run_startup_validation()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    name: str
    status: str  # "ok" | "degraded" | "error" | "disabled"
    latency_ms: float = 0.0
    detail: str = ""
    critical: bool = True


@dataclass
class StartupReport:
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    services: list[ServiceStatus] = field(default_factory=list)

    @property
    def all_critical_ok(self) -> bool:
        return all(s.status == "ok" for s in self.services if s.critical)

    def log(self) -> None:
        lines = [f"\n{'═' * 60}", "  NewsIQ Startup Report", f"{'═' * 60}"]
        for svc in self.services:
            icon = "✓" if svc.status == "ok" else ("⚠" if svc.status == "degraded" else "✗")
            line = f"  {icon} {svc.name:<20} {svc.status:<10}"
            if svc.latency_ms:
                line += f" ({svc.latency_ms:.1f}ms)"
            if svc.detail:
                line += f"  — {svc.detail}"
            lines.append(line)
        lines.append(f"{'═' * 60}\n")
        logger.info("\n".join(lines))


async def run_startup_validation() -> StartupReport:
    """Run all startup checks and return a StartupReport.

    Raises:
        RuntimeError: if any critical service is unavailable or misconfigured.
    """
    from app.core.config import settings

    report = StartupReport()

    # ── 1. Secrets validation ─────────────────────────────────────────────────
    errors = settings.validate_required_secrets()
    if errors:
        for e in errors:
            logger.critical("STARTUP VALIDATION FAILED: %s", e)
        raise RuntimeError(
            f"Critical configuration errors at startup ({len(errors)} issues):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # ── 2. Emit startup configuration summary ────────────────────────────────
    settings.emit_startup_report()

    # ── 3. Database ───────────────────────────────────────────────────────────
    db_status = await _check_database()
    report.services.append(db_status)

    # ── 4. Redis / Cache ──────────────────────────────────────────────────────
    redis_status = await _check_redis()
    report.services.append(redis_status)

    # ── 5. Qdrant (non-critical: vector search degrades gracefully) ────────────
    qdrant_status = await _check_qdrant()
    report.services.append(qdrant_status)

    # ── 6. Meilisearch (non-critical: falls back to PG ILIKE search) ──────────
    meili_status = await _check_meilisearch()
    report.services.append(meili_status)

    # ── 7. Storage (non-critical: operations skip if unconfigured) ─────────────
    storage_status = await _check_storage()
    report.services.append(storage_status)

    # ── 8. Langfuse (non-critical) ─────────────────────────────────────────────
    langfuse_status = await _check_langfuse()
    report.services.append(langfuse_status)

    # ── Print report ──────────────────────────────────────────────────────────
    report.log()

    # ── Fail if critical services are down ────────────────────────────────────
    if not report.all_critical_ok:
        critical_failures = [s for s in report.services if s.critical and s.status != "ok"]
        raise RuntimeError(
            "Critical services failed startup checks: "
            + ", ".join(f"{s.name} ({s.detail})" for s in critical_failures)
        )

    return report


# ── Individual checkers ────────────────────────────────────────────────────────


async def _check_database() -> ServiceStatus:
    try:
        from app.infrastructure.database import database_provider

        result = await database_provider.health_check()
        return ServiceStatus(
            name="PostgreSQL",
            status=result["status"],
            latency_ms=result.get("latency_ms", 0),
            detail=result.get("error", ""),
            critical=True,
        )
    except Exception as e:
        return ServiceStatus(name="PostgreSQL", status="error", detail=str(e), critical=True)


async def _check_redis() -> ServiceStatus:
    try:
        from app.infrastructure.cache import cache_provider

        result = await cache_provider.health_check()
        return ServiceStatus(
            name="Redis",
            status=result["status"],
            latency_ms=result.get("latency_ms", 0),
            detail=result.get("error", ""),
            critical=True,
        )
    except Exception as e:
        return ServiceStatus(name="Redis", status="error", detail=str(e), critical=True)


async def _check_qdrant() -> ServiceStatus:
    try:
        from app.services.vector_service import vector_service

        await vector_service.init_collection()
        return ServiceStatus(name="Qdrant", status="ok", critical=False)
    except Exception as e:
        return ServiceStatus(name="Qdrant", status="degraded", detail=str(e)[:80], critical=False)


async def _check_meilisearch() -> ServiceStatus:
    try:
        from app.services.search_service import search_service

        await search_service.init_index()
        status = "ok" if search_service.enabled else "disabled"
        return ServiceStatus(name="Meilisearch", status=status, critical=False)
    except Exception as e:
        return ServiceStatus(
            name="Meilisearch", status="degraded", detail=str(e)[:80], critical=False
        )


async def _check_storage() -> ServiceStatus:
    from app.core.config import settings

    try:
        from app.infrastructure.storage import get_storage_provider

        provider = get_storage_provider()
        result = await provider.health_check()
        return ServiceStatus(
            name=f"Storage({settings.STORAGE_BACKEND})",
            status=result["status"],
            latency_ms=result.get("latency_ms", 0),
            detail=result.get("error", ""),
            critical=False,
        )
    except Exception as e:
        return ServiceStatus(
            name=f"Storage({settings.STORAGE_BACKEND})",
            status="degraded",
            detail=str(e)[:80],
            critical=False,
        )


async def _check_langfuse() -> ServiceStatus:
    try:
        from app.infrastructure.observability import observability_provider

        result = await observability_provider.health_check()
        return ServiceStatus(
            name="Langfuse",
            status=result["status"],
            latency_ms=result.get("latency_ms", 0),
            detail="" if result["status"] == "ok" else "keys not set or connection failed",
            critical=False,
        )
    except Exception as e:
        return ServiceStatus(name="Langfuse", status="degraded", detail=str(e)[:80], critical=False)
