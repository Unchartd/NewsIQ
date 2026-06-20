# NewsIQ Admin Dashboard

A standalone Next.js admin dashboard for the NewsIQ AI Observability Platform.
Deployable independently on a separate server from the main user-facing app.

## Features

- 🔐 **Standalone JWT Authentication** — Own login, no dependency on `apps/web`
- 📊 **System Health Overview** — Pipeline runs, cost today, story count, token usage
- 🔀 **Pipeline DAG** — Real-time stage visualization via Server-Sent Events (SSE)
- 📰 **Story Inspector** — Articles, entities, LLM traces, and replay triggers
- 💰 **Cost Analytics** — Recharts bar/pie charts for spend breakdown
- 🏷️ **Entity Debugger** — Wikidata override tool for NER corrections
- 🔗 **Cluster Debugger** — Manual split/merge operations
- 📝 **Prompt Viewer** — Versioned prompt templates by pipeline stage
- ✅ **Review Queue** — Human intervention audit log with before/after diffs

## Quick Start

```bash
# Install dependencies
npm install

# Copy and configure environment
cp .env.example .env.local
# Edit NEXT_PUBLIC_API_URL to point to your FastAPI backend

# Run dev server (port 3002)
npm run dev
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | FastAPI backend URL |
| `NEXT_PUBLIC_APP_NAME` | `NewsIQ Admin` | Display name |

## Docker

```bash
# Build the image
docker build -t newsiq-admin .

# Run the container
docker run -p 3002:3001 \
  -e NEXT_PUBLIC_API_URL=http://your-api:8000/api/v1 \
  newsiq-admin
```

Or via docker-compose:

```bash
docker compose --profile admin up admin
```

## Deployment

The app uses Next.js `output: "standalone"` mode — the Docker image is minimal (~150MB).

Deploy to any server running Node 20+. Set `NEXT_PUBLIC_API_URL` to your production API URL.

## Access

Default dev URL: `http://localhost:3002`

Login with your admin credentials (same as the FastAPI backend admin user).
