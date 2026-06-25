"""AWS S3 / MinIO storage provider.

Identical interface to R2Storage but targets AWS S3 or a MinIO endpoint.

For MinIO: set S3_ENDPOINT to http://minio:9000
For AWS S3: leave S3_ENDPOINT empty (uses default AWS endpoint)

Required environment variables:
  S3_ENDPOINT       → http://minio:9000 (MinIO) or empty (AWS S3)
  S3_BUCKET         → newsiq
  S3_ACCESS_KEY_ID  → IAM access key or MinIO root user
  S3_SECRET_ACCESS_KEY → IAM secret or MinIO root password
  S3_REGION         → us-east-1 (or your AWS region)
"""

from __future__ import annotations

import asyncio
import io
import logging
import time

from app.infrastructure.storage.base import StorageProvider

logger = logging.getLogger(__name__)


class S3Storage(StorageProvider):
    """AWS S3 / MinIO storage provider via boto3."""

    def __init__(
        self,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "us-east-1",
        endpoint: str = "",  # Empty = AWS S3; set for MinIO / custom S3
        public_url: str = "",
    ) -> None:
        self._bucket = bucket
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._region = region
        self._endpoint = endpoint or None  # boto3 expects None for AWS default
        self._public_url = public_url.rstrip("/")
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            kwargs: dict = {
                "aws_access_key_id": self._access_key_id,
                "aws_secret_access_key": self._secret_access_key,
                "region_name": self._region,
                "config": Config(
                    retries={"max_attempts": 3, "mode": "adaptive"},
                    connect_timeout=10,
                    read_timeout=30,
                ),
            }
            if self._endpoint:
                kwargs["endpoint_url"] = self._endpoint
            self._client = boto3.client("s3", **kwargs)
        return self._client

    async def _run(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        client = self._get_client()
        await self._run(
            client.upload_fileobj,
            io.BytesIO(data),
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    async def download(self, key: str) -> bytes:
        client = self._get_client()
        buf = io.BytesIO()
        try:
            await self._run(client.download_fileobj, self._bucket, key, buf)
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise FileNotFoundError(f"S3Storage: key not found: {key}") from e
            raise
        return buf.getvalue()

    async def delete(self, key: str) -> None:
        client = self._get_client()
        await self._run(client.delete_object, Bucket=self._bucket, Key=key)

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        if self._public_url:
            return f"{self._public_url}/{key}"
        client = self._get_client()
        return await self._run(
            client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def exists(self, key: str) -> bool:
        client = self._get_client()
        try:
            await self._run(client.head_object, Bucket=self._bucket, Key=key)
            return True
        except Exception as e:
            if "404" in str(e) or "NoSuchKey" in str(e):
                return False
            raise

    async def health_check(self) -> dict:
        t0 = time.monotonic()
        backend = "minio" if self._endpoint else "s3"
        try:
            client = self._get_client()
            await self._run(client.list_objects_v2, Bucket=self._bucket, MaxKeys=1)
            return {
                "status": "ok",
                "backend": backend,
                "bucket": self._bucket,
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
        except Exception as e:
            return {
                "status": "error",
                "backend": backend,
                "bucket": self._bucket,
                "error": str(e),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
