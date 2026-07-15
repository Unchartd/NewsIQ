# api_contracts.md — API Contracts and Route Reference

This reference lists the major REST endpoints exposed by `apps/api`.

## 1. Core Endpoints
- **GET** `/api/v1/stories`
  - Retrieves paginated list of canonical stories.
- **GET** `/api/v1/stories/{id}`
  - Retrieves a specific canonical story with its timeline and events.
- **GET** `/api/v1/stories/{id}/diff`
  - Invokes the difference engine to show timeline updates or text changes.
- **POST** `/api/v1/admin/ingest`
  - Triggers RSS feed scanning (Admin only).
- **POST** `/api/v1/admin/cluster`
  - Forces clustering execution (Admin only).

## 2. Inbound Payloads
- Input payloads utilize Pydantic validations. For example, search queries require standard parameters:
  - `query` (string)
  - `limit` (integer, default 20)
  - `similarity_threshold` (float, default 0.80)
