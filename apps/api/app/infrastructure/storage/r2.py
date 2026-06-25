"""Cloudflare R2 storage provider (S3-compatible).

Uses boto3 with the S3-compatible R2 endpoint. All operations are run
in a thread pool to remain non-blocking in the async event loop.

Required environment variables:
  R2_ENDPOINT        → https://<ACCOUNT_ID>.r2.cloudflarestorage.com
  R2_BUCKET          → newsiq-prod
  R2_ACCESS_KEY_ID   → R2 API token ID
  R2_SECRET_ACCESS_KEY → R2 API token secret
  R2_PUBLIC_URL      → https://assets.newsiq.io (optional, for public signed-like URLs)

Migration to MinIO or S3:
  Point R2_ENDPOINT at your MinIO/S3 endpoint. Same code, same interface.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from app.infrastructure.storage.base import StorageProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class R2Storage(StorageProvider):
    """Cloudflare R2 storage via the S3-compatible API (boto3)."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        public_url: str = "",
        region: str = "auto",
    ) -> None:
        self._bucket = bucket
        self._public_url = public_url.rstrip("/")
        self._endpoint = endpoint
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region
        self._client = None  # Lazy-initialized

    def _get_client(self):
        """Lazy-initialize boto3 S3 client (avoids import cost at module load)."""
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=self._endpoint,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
                region_name=self._region,
                config=Config(
                    retries={"max_attempts": 3, "mode": "adaptive"},
                    connect_timeout=10,
                    read_timeout=30,
                ),
            )
        return self._client

    async def _run(self, func, *args, **kwargs):
        """Run a synchronous boto3 call in a thread pool."""
        return await asyncio.to_thread(func, *args, **kwargs)

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        client = self._get_client()
        import io

        await self._run(
            client.upload_fileobj,
            io.BytesIO(data),
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.debug("R2Storage: uploaded s3://%s/%s (%d bytes)", self._bucket, key, len(data))

    async def download(self, key: str) -> bytes:
        import io

        client = self._get_client()
        buf = io.BytesIO()
        try:
            await self._run(client.download_fileobj, self._bucket, key, buf)
        except Exception as e:
            error_str = str(e)
            if "NoSuchKey" in error_str or "404" in error_str:
                raise FileNotFoundError(f"R2Storage: key not found: {key}") from e
            raise
        return buf.getvalue()

    async def delete(self, key: str) -> None:
        client = self._get_client()
        await self._run(client.delete_object, Bucket=self._bucket, Key=key)
        logger.debug("R2Storage: deleted s3://%s/%s", self._bucket, key)

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for temporary read access.

        If R2_PUBLIC_URL is set and the bucket is public, returns a direct
        public URL instead of a signed URL (faster, no expiry).
        """
        if self._public_url:
            return f"{self._public_url}/{key}"

        client = self._get_client()
        url = await self._run(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )
        return url

    async def exists(self, key: str) -> bool:
        client = self._get_client()
        try:
            await self._run(client.head_object, Bucket=self._bucket, Key=key)
            return True
        except Exception as e:
            if "404" in str(e) or "NoSuchKey" in str(e) or "Not Found" in str(e):
                return False
            raise

    async def health_check(self) -> dict:
        t0 = time.monotonic()
        try:
            client = self._get_client()
            # List at most 1 object to verify connectivity
            await self._run(
                client.list_objects_v2,
                Bucket=self._bucket,
                MaxKeys=1,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            return {
                "status": "ok",
                "backend": "r2",
                "bucket": self._bucket,
                "latency_ms": round(latency_ms, 2),
            }
        except Exception as e:
            return {
                "status": "error",
                "backend": "r2",
                "bucket": self._bucket,
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
