# NewsIQ — AI News Intelligence Platform

> Understand any major story in under 30 seconds, with transparency, neutrality, and trust.

## Architecture

```text
apps/web    → Next.js 15 (TypeScript, Tailwind v4, shadcn/ui)
apps/api    → FastAPI (Python, SQLAlchemy, Celery)
```

## Infrastructure (Docker Compose)

| Service      | Port  | Purpose             |
|-------------|-------|---------------------|
| PostgreSQL  | 5432  | Primary database    |
| Redis       | 6379  | Cache + task queue  |
| Qdrant      | 6333  | Vector database     |
| Meilisearch | 7700  | Full-text search    |

## Quick Start

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Start infrastructure
docker-compose up -d

# 3. Start backend
cd apps/api
pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload --port 8000

# 4. Start frontend
cd apps/web
npm install
npm run dev
```

## API Endpoints

- Health: `GET /health`
- Readiness: `GET /ready`
- API v1: `GET /api/v1/ping`
- Docs: `GET /docs`

## License

Private — All rights reserved.
