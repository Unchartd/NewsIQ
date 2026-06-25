"""Storage provider factory.

Reads STORAGE_BACKEND from config and instantiates the correct provider.
This is the single entry point for obtaining a StorageProvider instance.

Usage:
    from app.infrastructure.storage.factory import get_storage_provider

    storage = get_storage_provider()  # Returns the configured provider
    await storage.upload("images/foo.jpg", data, "image/jpeg")

Environment variables:
    STORAGE_BACKEND=local   → LocalStorage (development default)
    STORAGE_BACKEND=r2      → Cloudflare R2
    STORAGE_BACKEND=s3      → AWS S3
    STORAGE_BACKEND=minio   → MinIO (same as s3 but with S3_ENDPOINT set)
"""

from __future__ import annotations

import logging

from app.infrastructure.storage.base import StorageProvider

logger = logging.getLogger(__name__)

_provider_instance: StorageProvider | None = None


def get_storage_provider() -> StorageProvider:
    """Return the singleton StorageProvider configured by STORAGE_BACKEND.

    The instance is created once on first call and reused (lazy singleton).
    Thread-safe for the purposes of an async single-process FastAPI app.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    from app.core.config import settings

    backend = settings.STORAGE_BACKEND

    if backend == "local":
        from app.infrastructure.storage.local import LocalStorage

        _provider_instance = LocalStorage(base_path=settings.LOCAL_STORAGE_PATH)
        logger.info("Storage backend: local (path=%s)", settings.LOCAL_STORAGE_PATH)

    elif backend == "r2":
        if not all(
            [settings.R2_ENDPOINT, settings.R2_ACCESS_KEY_ID, settings.R2_SECRET_ACCESS_KEY]
        ):
            raise RuntimeError(
                "STORAGE_BACKEND=r2 requires R2_ENDPOINT, R2_ACCESS_KEY_ID, "
                "and R2_SECRET_ACCESS_KEY to be set."
            )
        from app.infrastructure.storage.r2 import R2Storage

        _provider_instance = R2Storage(
            endpoint=settings.R2_ENDPOINT,
            bucket=settings.R2_BUCKET,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            public_url=settings.R2_PUBLIC_URL,
        )
        logger.info("Storage backend: Cloudflare R2 (bucket=%s)", settings.R2_BUCKET)

    elif backend in ("s3", "minio"):
        if not all([settings.S3_ACCESS_KEY_ID, settings.S3_SECRET_ACCESS_KEY]):
            raise RuntimeError(
                f"STORAGE_BACKEND={backend} requires S3_ACCESS_KEY_ID "
                "and S3_SECRET_ACCESS_KEY to be set."
            )
        from app.infrastructure.storage.s3 import S3Storage

        _provider_instance = S3Storage(
            bucket=settings.S3_BUCKET,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
            endpoint=settings.S3_ENDPOINT,
        )
        logger.info(
            "Storage backend: %s (bucket=%s, endpoint=%s)",
            backend,
            settings.S3_BUCKET,
            settings.S3_ENDPOINT or "AWS default",
        )

    else:
        raise ValueError(
            f"Unknown STORAGE_BACKEND: {backend!r}. Must be one of: local, r2, s3, minio"
        )

    return _provider_instance


def reset_storage_provider() -> None:
    """Reset the singleton — for use in tests only."""
    global _provider_instance
    _provider_instance = None
