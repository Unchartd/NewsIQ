# Environment Variables Reference

All environment variables used by NewsIQ. Copy `.env.example` to `.env` and populate.

---

## Database

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://newsiq:newsiq@localhost:5432/newsiq` | SQLAlchemy async URL (Neon pooled or local) |
| `DATABASE_DIRECT_URL` | ⚠️ | Same as `DATABASE_URL` | Non-pooled URL for Alembic migrations (Neon direct endpoint) |
| `DATABASE_SSL` | ⚠️ | `false` | Set `true` for Neon and any production database |
| `DB_POOL_SIZE` | ❌ | `5` | SQLAlchemy pool size (5 for Neon free tier) |
| `DB_MAX_OVERFLOW` | ❌ | `2` | Max additional connections above pool_size |
| `DB_POOL_RECYCLE` | ❌ | `300` | Recycle connections every N seconds |

## Redis / Cache

| Variable | Required | Default | Description |
|---|---|---|---|
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` | App cache (stories, trending, rate limits) |
| `CELERY_BROKER_URL` | ✅ | `redis://localhost:6379/1` | Celery task queue broker |
| `CELERY_RESULT_BACKEND` | ✅ | `redis://localhost:6379/2` | Celery task result storage |

> [!NOTE]
> **Upstash Free Tier Limitation:** Since Upstash free tier does not support multiple database indices, and allows only 1 database per account, you can point `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` to the **exact same Upstash Redis URL** (using database `/0`). They will share the single database safely because their keyspaces do not overlap.
> TLS is automatic: use `rediss://` for Upstash / encrypted Redis.

## Object Storage

| Variable | Required | Default | Description |
|---|---|---|---|
| `STORAGE_BACKEND` | ❌ | `local` | `r2` \| `s3` \| `minio` \| `local` |
| `LOCAL_STORAGE_PATH` | ❌ | `./data/storage` | Path for local backend |
| `R2_ENDPOINT` | If `r2` | — | `https://ACCOUNT.r2.cloudflarestorage.com` |
| `R2_BUCKET` | If `r2` | `newsiq` | R2 bucket name |
| `R2_ACCESS_KEY_ID` | If `r2` | — | R2 API token access key |
| `R2_SECRET_ACCESS_KEY` | If `r2` | — | R2 API token secret |
| `R2_PUBLIC_URL` | ❌ | — | Public CDN URL for direct asset links |
| `S3_ENDPOINT` | If `minio` | — | MinIO endpoint (empty for AWS S3) |
| `S3_BUCKET` | If `s3/minio` | `newsiq` | Bucket name |
| `S3_ACCESS_KEY_ID` | If `s3/minio` | — | Access key |
| `S3_SECRET_ACCESS_KEY` | If `s3/minio` | — | Secret key |
| `S3_REGION` | If `s3` | `us-east-1` | AWS region |

## Auth / Security

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | insecure default | JWT signing key — generate with `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `15` | JWT access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ❌ | `30` | Refresh token TTL |
| `ALGORITHM` | ❌ | `HS256` | JWT signing algorithm |

## OAuth

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_CLIENT_ID` | ⚠️ | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ⚠️ | — | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | ❌ | localhost callback | OAuth callback URL |

## AI / LLM

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ | — | Primary Gemini API key |
| `GEMINI_API_KEY_EMBEDDING` | ⚠️ | — | Dedicated embedding key (falls back to `GEMINI_API_KEY`) |
| `GEMINI_API_KEY_SYNTH` | ⚠️ | — | Synthesis/summarization key |
| `OPENAI_API_KEY` | ⚠️ | — | OpenAI fallback for embeddings |
| `GROQ_API_KEY` | ❌ | — | Groq fast inference |
| `CEREBRAS_API_KEY` | ❌ | — | Cerebras inference |
| `NVIDIA_API_KEY` | ❌ | — | NVIDIA NIM inference |
| `EMBEDDING_MODEL` | ❌ | `text-embedding-004` | Default embedding model |
| `SUMMARIZATION_MODEL` | ❌ | `gemini-2.5-flash` | Default summarization model |

## News APIs

| Variable | Required | Default | Description |
|---|---|---|---|
| `NEWSAPI_KEY` | ⚠️ | — | NewsAPI.org for RSS discovery |
| `GNEWS_API_KEY` | ⚠️ | — | GNews API for international news |

## Observability

| Variable | Required | Default | Description |
|---|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | ⚠️ | — | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | ⚠️ | — | Langfuse project secret key |
| `LANGFUSE_HOST` | ❌ | `https://cloud.langfuse.com` | Langfuse host (cloud or self-hosted) |
| `SENTRY_DSN` | ⚠️ | — | Sentry error tracking DSN |

## Infrastructure

| Variable | Required | Default | Description |
|---|---|---|---|
| `QDRANT_HOST` | ❌ | `localhost` | Qdrant vector DB host |
| `QDRANT_PORT` | ❌ | `6333` | Qdrant port |
| `MEILISEARCH_URL` | ❌ | `http://localhost:7700` | Meilisearch URL |
| `MEILISEARCH_API_KEY` | ❌ | — | Meilisearch admin key |
| `PROMETHEUS_MULTIPROC_DIR` | ❌ | — | Required for Prometheus multiprocess mode |

## Application

| Variable | Required | Default | Description |
|---|---|---|---|
| `DEBUG` | ❌ | `false` | Enable debug mode (shows docs, verbose logging) |
| `APP_NAME` | ❌ | `NewsIQ` | Application name |
| `APP_VERSION` | ❌ | `0.1.0` | Application version |
| `BACKEND_SERVICE_ROLE` | ❌ | `monolith` | Role tag for metrics (`user`, `processing`, `monolith`) |
| `CORS_ORIGINS` | ❌ | `["http://localhost:3000"]` | JSON array of allowed CORS origins |
| `FRONTEND_URL` | ❌ | `http://localhost:3000` | Frontend URL (for email links) |

## SMTP

| Variable | Required | Default | Description |
|---|---|---|---|
| `SMTP_HOST` | ⚠️ | — | SMTP server hostname |
| `SMTP_PORT` | ❌ | `1025` | SMTP port |
| `SMTP_USER` | ⚠️ | — | SMTP username |
| `SMTP_PASSWORD` | ⚠️ | — | SMTP password |
| `SMTP_FROM_EMAIL` | ❌ | `noreply@newsiq.io` | Sender email address |
| `SMTP_FROM_NAME` | ❌ | `NewsIQ` | Sender display name |

---

**Legend:**
- ✅ Required — app will not start without this
- ⚠️ Recommended — feature will be degraded without this  
- ❌ Optional — has a sensible default
