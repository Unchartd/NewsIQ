"""Local filesystem storage provider for development and testing.

Files are stored under LOCAL_STORAGE_PATH (default: ./data/storage).
Signed URLs are synthetic local paths — they are not HTTP URLs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.infrastructure.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class LocalStorage(StorageProvider):
    """Local filesystem storage — for development only."""

    def __init__(self, base_path: str = "./data/storage") -> None:
        self._base = Path(base_path).resolve()
        self._base.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage initialized at: %s", self._base)

    def _path(self, key: str) -> Path:
        """Resolve a storage key to an absolute filesystem path safely."""
        # Prevent path traversal
        resolved = (self._base / key).resolve()
        if not str(resolved).startswith(str(self._base)):
            raise ValueError(f"Invalid storage key (path traversal attempt): {key}")
        return resolved

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        logger.debug("LocalStorage: uploaded %s (%d bytes)", key, len(data))

    async def download(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(f"LocalStorage: key not found: {key}")
        return await asyncio.to_thread(path.read_bytes)

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            await asyncio.to_thread(path.unlink)
            logger.debug("LocalStorage: deleted %s", key)

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a file:// URL pointing to the local file."""
        path = self._path(key)
        return f"file://{path}"

    async def exists(self, key: str) -> bool:
        path = self._path(key)
        return path.exists()

    async def health_check(self) -> dict:
        t0 = time.monotonic()
        try:
            exists = self._base.exists() and self._base.is_dir()
            latency_ms = (time.monotonic() - t0) * 1000
            return {
                "status": "ok" if exists else "error",
                "backend": "local",
                "path": str(self._base),
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {
                "status": "error",
                "backend": "local",
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
