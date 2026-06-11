Below is a Technical Requirements Document (TRD) from the perspective of a senior software architect. It focuses on building an MVP that is scalable, AI-native, and cost-efficient.

---

# Technical Requirements Document (TRD)

# AI News Intelligence Platform

---

# 1. System Overview

The platform ingests articles from multiple sources, clusters articles describing the same event, generates AI summaries, extracts facts, detects differences between sources, and serves structured stories through APIs consumed by a Next.js frontend.

### High-Level Flow

```text
RSS Feeds / News APIs / Crawlers
            ↓
      Ingestion Service
            ↓
         Kafka Queue
            ↓
       Article Storage
         PostgreSQL
            ↓
      Embedding Service
            ↓
          Qdrant
            ↓
      Clustering Engine
            ↓
       Story Generator
            ↓
      Fact Extractor
            ↓
      Difference Engine
            ↓
      Trending Engine
            ↓
         API Gateway
            ↓
       Next.js Frontend
```

---

# 2. Frontend Stack

## Framework

### Next.js 15

Reason:

* SSR + SSG
* SEO-friendly
* App Router
* Server Components
* Edge rendering support

---

## Language

### TypeScript

Reason:

* Type safety
* Better maintainability
* Prevent runtime errors

---

## Styling

### TailwindCSS v4

Reason:

* Fast development
* Small bundle size
* Design consistency

---

## UI Components

### shadcn/ui

Reason:

* Accessible
* Customizable
* No dependency lock-in

---

## State Management

### Zustand

Reason:

* Lightweight
* Easier than Redux
* Minimal boilerplate

Use for:

* Filters
* User preferences
* Theme

---

## Server State

### TanStack Query

Reason:

* Caching
* Automatic revalidation
* Infinite scrolling

---

## Charts

### Recharts

For:

* Trending charts
* Timeline visualization

---

## Authentication

### Better Auth

Reason:

* Type-safe
* Supports OAuth
* Session-based authentication

---

## Search

### URL search params

Reason:

Search pages should remain shareable and SEO-friendly.

Example:

```text
/news?category=tech&country=india
```

---

# 3. Backend Stack

## Framework

### FastAPI

Reason:

* Extremely fast
* Async support
* Python AI ecosystem
* Automatic OpenAPI docs

---

## Why FastAPI?

AI pipelines and NLP libraries are Python-first.

Libraries:

* sentence-transformers
* scikit-learn
* HDBSCAN
* spaCy
* LangChain
* Agno
* OpenAI SDK

---

## API Style

REST API

Reason:

Simple and cacheable.

GraphQL can be introduced later.

---

# 4. AI Services

Split into separate services.

---

## Embedding Service

Purpose:

Convert articles into vectors.

Models:

### OpenAI text-embedding-3-small

or

### Gemini Embeddings

Future:

BGE-M3

Deployment:

Independent container.

---

## Summarization Service

Produces:

* Headline
* One-line summary
* Short summary
* Detailed summary

Model:

GPT-4o-mini

or

Gemini 2.5 Flash

---

## Fact Extraction Service

Extract:

* Location
* Time
* People
* Organizations
* Numbers

Libraries:

```python
spaCy
Presidio
PydanticAI
```

---

## Difference Engine

Compares sources.

Returns:

```json
{
 "missingFacts": [],
 "contradictions": [],
 "focusAreas": []
}
```

---

## Trend Engine

Computes:

```python
trend_score =
recency +
source_count +
user_engagement
```

---

# 5. Agent Architecture

Using Agno.

---

## Collector Agent

Responsibilities:

* Fetch RSS feeds
* Fetch APIs
* Normalize articles

---

## Cluster Agent

Responsibilities:

* Similarity search
* Group articles

---

## Summarizer Agent

Responsibilities:

Generate:

* Headline
* Summaries

---

## Fact Agent

Responsibilities:

Extract:

* Location
* Date
* Organizations

---

## Difference Agent

Responsibilities:

Compare sources.

---

## Trend Agent

Responsibilities:

Ranking stories.

---

# 6. Database Stack

## PostgreSQL

Primary database.

Reason:

* Reliable
* ACID
* JSON support
* Mature ecosystem

---

### Tables

---

#### users

```sql
id
email
name
image
created_at
```

---

#### articles

```sql
id
title
content
source
author
url
published_at
language
embedding_status
created_at
```

---

#### stories

```sql
id
headline
short_summary
long_summary
category
location
trend_score
created_at
```

---

#### story_articles

```sql
story_id
article_id
```

---

#### story_timelines

```sql
id
story_id
event_time
description
```

---

#### source_differences

```sql
id
story_id
source_name
focus_area
unique_information
```

---

#### user_preferences

```sql
user_id
categories
countries
cities
```

---

# 7. Vector Database

## Qdrant

Purpose:

Semantic similarity.

Stores:

```text
Article embedding
Metadata
Article ID
```

Reason:

* Open source
* Fast
* Scalable
* Metadata filtering

---

# 8. Caching Layer

## Redis

Purpose:

### Hot Stories

```text
story:123
```

TTL:

15 minutes

---

### Trending News

```text
trending:india
```

TTL:

5 minutes

---

### Search Results

TTL:

30 minutes

---

Reason:

Reduce PostgreSQL load.

---

# 9. Message Queue

## Apache Kafka

Purpose:

Event-driven architecture.

Topics:

### article-ingested

```text
New article fetched
```

---

### embedding-created

```text
Vector ready
```

---

### story-created

```text
Story generated
```

---

### trend-updated

```text
Ranking recalculated
```

---

Reason:

Loose coupling.

---

# 10. Search Engine

## Meilisearch

Reason:

Simple and lightweight.

Searches:

* Headlines
* Categories
* Locations

Future:

Elasticsearch.

---

# 11. API Design

---

## News APIs

### Get Stories

```http
GET /api/v1/stories
```

Filters:

```text
country
state
city
category
trending
```

---

### Story Details

```http
GET /api/v1/stories/:id
```

Returns:

```json
{
  "headline":"",
  "summary":"",
  "timeline":[],
  "sources":[],
  "differences":[]
}
```

---

### Search

```http
GET /api/v1/search
```

---

### Trending

```http
GET /api/v1/trending
```

---

### Categories

```http
GET /api/v1/categories
```

---

### Source Comparison

```http
GET /api/v1/stories/:id/comparison
```

---

# User APIs

---

### Register

```http
POST /api/v1/auth/register
```

---

### Login

```http
POST /api/v1/auth/login
```

---

### User Preferences

```http
PATCH /api/v1/users/preferences
```

---

### Saved Stories

```http
GET /api/v1/users/bookmarks
```

---

# 12. Authentication

## Better Auth + Google OAuth

Methods:

* Google
* GitHub
* Email

---

## Session Storage

Redis.

---

## JWT

Short-lived access token.

```text
15 minutes
```

Refresh token:

```text
30 days
```

---

## RBAC

Roles:

```text
guest
user
premium
admin
```

---

# 13. Security Requirements

---

## HTTPS Everywhere

TLS 1.3

---

## Input Validation

Pydantic.

Prevent:

* SQL injection
* Invalid requests

---

## Rate Limiting

Redis-based.

Example:

```text
100 requests/minute
```

---

## CORS

Allow only:

```text
frontend domain
```

---

## Secrets Management

Never inside source code.

Use:

```text
AWS Secrets Manager
```

or

```text
Doppler
```

---

## SQL Injection Protection

Prisma ORM.

---

## XSS Protection

Content Security Policy.

---

## CSRF Protection

Session cookies.

---

## DDoS Protection

Cloudflare.

---

## Bot Protection

Cloudflare Turnstile.

---

# 14. File Storage

## S3

Stores:

* User avatars
* Generated images

Future:

Audio summaries.

---

# 15. Observability

## OpenTelemetry

Tracing.

---

## Prometheus

Metrics.

---

## Grafana

Dashboards.

---

## Sentry

Frontend and backend errors.

---

# 16. Deployment

---

## Frontend

Vercel

Reason:

Excellent Next.js support.

---

## Backend

AWS ECS Fargate

Reason:

Serverless containers.

---

## Database

AWS RDS PostgreSQL

Multi-AZ enabled.

---

## Redis

Elasticache Redis.

---

## Vector Database

Qdrant Cloud.

---

## Object Storage

AWS S3.

---

## CDN

Cloudflare.

---

# 17. CI/CD

GitHub Actions.

Pipeline:

```text
Push
 ↓
Tests
 ↓
Lint
 ↓
Build
 ↓
Docker Image
 ↓
Deploy
```

---

# 18. Monitoring

### Health Checks

```http
GET /health
```

---

### Readiness

```http
GET /ready
```

---

### Metrics

```http
GET /metrics
```

---

# 19. Scalability Strategy

### Horizontal Scaling

Each service independently scalable.

```text
Summarizer
Embedding
Fact Extraction
Trend Engine
```

---

### Stateless APIs

Multiple replicas.

---

### Redis Cache

Reduces database load.

---

### CDN

Static assets globally cached.

---

### Kafka

Handles millions of events.

---

# 20. Cost Optimization for MVP

Avoid microservices initially.

Instead:

```text
Next.js
↓
FastAPI Monolith
↓
Postgres
↓
Redis
↓
Qdrant
```

AI workers:

```text
Celery + Redis Queue
```

This architecture is sufficient for:

* 100K+ DAU
* Millions of articles
* Low infrastructure cost

---

# Recommended Final Stack

| Layer            | Technology                    |
| ---------------- | ----------------------------- |
| Frontend         | Next.js 15                    |
| Language         | TypeScript                    |
| Styling          | Tailwind v4                   |
| Components       | shadcn/ui                     |
| State            | Zustand                       |
| Server State     | TanStack Query                |
| Backend          | FastAPI                       |
| AI Framework     | Agno                          |
| ORM              | Prisma                        |
| Database         | PostgreSQL                    |
| Vector DB        | Qdrant                        |
| Cache            | Redis                         |
| Search           | Meilisearch                   |
| Queue            | Redis Queue → Kafka later     |
| Auth             | Better Auth                   |
| Storage          | AWS S3                        |
| Monitoring       | Prometheus + Grafana + Sentry |
| Frontend Hosting | Vercel                        |
| Backend Hosting  | AWS ECS                       |
| CDN              | Cloudflare                    |
| CI/CD            | GitHub Actions                |

---

## Architectural Decision

For an MVP, **do not start with 10 microservices**. Start with a **modular FastAPI monolith + background workers**, and only evolve into event-driven microservices (Kafka) when scale demands it. This minimizes cost and complexity while preserving a clean migration path toward becoming a full-fledged **AI News Intelligence Engine**.
