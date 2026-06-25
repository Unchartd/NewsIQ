# Cloudflare R2 Storage Setup Guide

## Overview

NewsIQ uses [Cloudflare R2](https://developers.cloudflare.com/r2/) as its object storage provider. R2 provides:
- S3-compatible API (works with boto3 without modification)
- Zero egress fees (unlike AWS S3)
- Free tier: 10 GB storage, 1M Class A ops, 10M Class B ops per month
- Optional public bucket with custom domain

---

## 1. Create an R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **R2 Object Storage**
3. Click **Create bucket**
4. Name it `newsiq-prod`
5. Select the closest location policy

---

## 2. Create R2 API Credentials

1. In the Cloudflare Dashboard → **R2** → **Manage R2 API tokens**
2. Click **Create API token**
3. Set permissions: **Object Read & Write** for bucket `newsiq-prod`
4. Copy:
   - **Access Key ID** → `R2_ACCESS_KEY_ID`
   - **Secret Access Key** → `R2_SECRET_ACCESS_KEY`
5. Your R2 endpoint is: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

---

## 3. Environment Variables

```bash
# .env or Coolify environment variables
STORAGE_BACKEND=r2
R2_ENDPOINT=https://ACCOUNT_ID.r2.cloudflarestorage.com
R2_BUCKET=newsiq-prod
R2_ACCESS_KEY_ID=your-access-key-id
R2_SECRET_ACCESS_KEY=your-secret-access-key

# Optional: Set R2_PUBLIC_URL if the bucket has a public custom domain
# This returns a direct URL instead of a pre-signed URL
R2_PUBLIC_URL=https://assets.newsiq.io
```

---

## 4. Optional: Configure Public Access

To serve assets (images, exports) publicly without pre-signed URLs:

1. In R2 → your bucket → **Settings** → **Public access**
2. Enable **R2.dev subdomain** (free) or connect a custom domain
3. Set `R2_PUBLIC_URL` to your custom domain or `https://<bucket>.r2.dev`

---

## 5. CORS Configuration (if serving frontend assets)

In R2 → your bucket → **Settings** → **CORS**:

```json
[
  {
    "AllowedOrigins": ["https://newsiq.io", "http://localhost:3000"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## 6. Storage Provider Interface

The storage provider is accessed via:
```python
from app.infrastructure.storage import get_storage_provider

storage = get_storage_provider()
await storage.upload("exports/pipeline-run-123.json", data, "application/json")
url = await storage.signed_url("exports/pipeline-run-123.json", expires_in=3600)
```

Switching backends requires only env var changes.

---

## 7. Rollback to Self-Hosted MinIO

```bash
# Start MinIO locally
docker run -d \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

# Update env vars — no code changes required
STORAGE_BACKEND=minio
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=newsiq
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_REGION=us-east-1
```

---

## 8. Rollback to Local Filesystem

```bash
# Development default — no external service required
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=./data/storage
```
