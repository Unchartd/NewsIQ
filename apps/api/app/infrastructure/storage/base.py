"""Storage provider abstract base class.

All storage backends implement this interface. Business logic should depend
only on StorageProvider — never on boto3, R2, or any cloud SDK directly.

Interface:
  upload(key, data, content_type)  → None
  download(key)                    → bytes
  delete(key)                      → None
  signed_url(key, expires_in)      → str
  exists(key)                      → bool

Switching backends:
  Change STORAGE_BACKEND env var. No business logic changes required.
  r2    → Cloudflare R2 (S3-compatible)
  s3    → AWS S3 (or any S3-compatible endpoint)
  minio → MinIO (set S3_ENDPOINT to MinIO URL)
  local → Local filesystem (development)
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract storage provider interface."""

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Upload data to the storage backend under the given key.

        Args:
            key:          Object key / path (e.g. "images/article-123.jpg")
            data:         Raw bytes to store
            content_type: MIME type (e.g. "image/jpeg", "application/json")
        """

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download and return the raw bytes for the given key.

        Raises:
            FileNotFoundError: if the key does not exist
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete the object at the given key. No-op if it does not exist."""

    @abstractmethod
    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a pre-signed URL that grants temporary read access.

        Args:
            key:        Object key
            expires_in: URL validity in seconds (default: 1 hour)
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if an object exists at the given key."""

    @abstractmethod
    async def health_check(self) -> dict:
        """Return a health status dict for the storage provider.

        Returns:
            {"status": "ok"|"error", "backend": str, "latency_ms": float}
        """
