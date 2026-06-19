# Sources & Publishers API Reference

All routes are prefixed with `/api/v1/sources`.

---

## 1. Public Source References

### A. List News Sources
- **Endpoint**: `GET /`
- **Query Parameters**:
  - `active_only` (boolean, default: `true`): If true, returns only active publishers.
- **Response** (200 OK):
  ```json
  [
    {
      "id": "01982e1c-6e93-75f4-80db-95a5f6d1e2b0",
      "name": "Reuters",
      "slug": "reuters",
      "website_url": "https://reuters.com",
      "logo_url": "https://logo.reuters.com",
      "country_code": "US",
      "rss_url": "https://reuters.com/rss",
      "active": true,
      "created_at": "2026-06-19T11:27:00"
    }
  ]
  ```

### B. Fetch Source Details
- **Endpoint**: `GET /{source_id}`
- **Response**: Source entity matching the ID.

---

## 2. Source Configuration (Admin Only)

### A. Create Source
- **Endpoint**: `POST /`
- **Authentication**: Required (Admin role)
- **Request Body**:
  ```json
  {
    "name": "Associated Press",
    "slug": "ap-news",
    "website_url": "https://apnews.com",
    "logo_url": "https://logo.apnews.com",
    "country_code": "US",
    "rss_url": "https://apnews.com/rss",
    "active": true
  }
  ```

### B. Update Source Parameters
- **Endpoint**: `PATCH /{source_id}`
- **Authentication**: Required (Admin role)
- **Request Body**: Partial mapping of the fields.

### C. Deactivate Source
- **Endpoint**: `DELETE /{source_id}`
- **Authentication**: Required (Admin role)
- **Behavior**: Sets `active = false` on the source record. **Note**: The source record is deactivated rather than deleted from PostgreSQL to preserve article integrity.

---

## 3. Ingestion Trigger

- **Endpoint**: `POST /trigger-ingestion`
- **Authentication**: Required (User role)
- **Behavior**: Triggers the Celery news ingestion queue task `ingest_news_task` immediately for developer testing.
- **Response** (202 Accepted):
  ```json
  {
    "message": "Ingestion task queued.",
    "task_id": "celery-task-uuid"
  }
  ```
