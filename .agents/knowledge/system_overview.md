# system_overview.md — NewsIQ System Overview

This document provides a high-level overview of the NewsIQ system design and storage layer mappings.

## 1. Storage Distribution & Databases
NewsIQ splits its storage systems based on accessibility, scalability, and content schemas:
- **PostgreSQL**: Stores relational structured metadata, discovery tables, user accounts, and configuration states. Migrations are managed via Alembic.
- **MongoDB**: Acts as the document payload store, holding raw article payloads, feeds, and rich metadata outputs.
- **Qdrant**: The vector database containing generated text embeddings, used for similarity search and clustering.
- **Redis**: The in-memory cache and task queue broker.

## 2. Component Layout
- **REST API (`apps/api`)**: Developed with FastAPI, routing incoming HTTP traffic, user interactions, and admin panel commands.
- **Background Tasks**: Long-running background processes (like RSS feed ingestion, story clustering, and AI reflections) run on async worker threads managed by Redis.
