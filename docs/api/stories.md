# Stories & Timelines API Reference

All routes are prefixed with `/api/v1/stories`.

---

## 1. Stories Feed & Discovery

### A. List Stories
- **Endpoint**: `GET /`
- **Query Parameters**:
  - `category` (string, optional): Category slug to filter by (e.g. `technology`).
  - `country` / `state` / `city` (string, optional): Geolocation filters.
  - `q` (string, optional): Case-insensitive keyword filter.
  - `trending` (boolean, default: `false`): Rank by trend score instead of updated timestamp.
  - `limit` (int, default: `20`): Page size.
  - `offset` (int, default: `0`): Page offset.
- **Response** (200 OK):
  ```json
  [
    {
      "id": "01982e1c-6e93-75f4-80db-95a5f6d1e2b7",
      "headline": "OpenAI Releases GPT-5",
      "one_line_summary": "OpenAI launches GPT-5 featuring advanced reasoning.",
      "short_summary": "GPT-5 has been officially released by OpenAI...",
      "location_country": "US",
      "location_state": "CA",
      "location_city": "San Francisco",
      "trend_score": 98.5,
      "first_seen_at": "2026-06-19T11:27:00",
      "updated_at": "2026-06-19T11:30:00",
      "category": {
        "id": "01982e1c-6e93-75f4-80db-95a5f6d1e2a1",
        "slug": "technology",
        "name": "Technology",
        "icon": "cpu"
      },
      "article_count": 14,
      "source_count": 5,
      "source_logos": [
        "https://logo.reuters.com",
        "https://logo.bbc.com"
      ]
    }
  ]
  ```

### B. Fetch Trending Stories (Cached)
- **Endpoint**: `GET /trending`
- **Query Parameters**: `category`, `limit`, `offset`
- **Behavior**: Retrieves stories ranked by trend score, caching results in Redis for 5 minutes (per category). Only the first page (offset=0) is cached.

### C. Search Stories
- **Endpoint**: `GET /search`
- **Query Parameters**:
  - `q` (string, required): Query term (e.g. `GPT-5`).
  - `category` (string, optional): Filter by category slug.
- **Behavior**: Leverages Meilisearch ranking for fast results. Automatically falls back to PostgreSQL ILIKE queries if Meilisearch is offline.

### D. Fetch Categories
- **Endpoint**: `GET /categories`
- **Response**: List of category entities.

### E. Fetch Trending Widgets
- **Endpoint**: `GET /trending-widgets`
- **Purpose**: Sidebar list of top 4 tags/topics and top 3 publisher rating stats.

---

## 2. Personalized Feed

- **Endpoint**: `GET /feed/personalized`
- **Authentication**: Required (User role)
- **Behavior**: Intersects the user's preferred categories and geolocations (`user_categories`, `user_locations`). Falls back to global trending if preferences are empty.

---

## 3. Story Detail & Visual Components

### A. Story Detail Data
- **Endpoint**: `GET /{story_id}`
- **Response**: Full story details including list of articles, timeline events, source coverages, entity sets, and metrics.
- **Cache**: Cached in Redis for 15 minutes. Increments views in PostgreSQL in the background.

### B. Source Comparison (Difference Engine)
- **Endpoint**: `GET /{story_id}/comparison`
- **Response**: Differences parsed by AI:
  ```json
  {
    "story_id": "01982e1c-...",
    "headline": "OpenAI Releases GPT-5",
    "source_count": 3,
    "sources": [
      {
        "source": { "name": "Reuters", "slug": "reuters" },
        "focus_area": "Focuses on enterprise pricing and release dates.",
        "unique_information": "Reported that Microsoft got early beta access.",
        "missing_information": "Did not detail safety audit results.",
        "contradictions": "Claims release is immediate; BBC claims rolling release."
      }
    ],
    "source_coverage": []
  }
  ```

---

## 4. Bookmarks Management

### A. List Bookmarks
- **Endpoint**: `GET /bookmarks`
- **Authentication**: Required (User role)

### B. Add Bookmark
- **Endpoint**: `POST /{story_id}/bookmark`
- **Authentication**: Required (User role)

### C. Remove Bookmark
- **Endpoint**: `DELETE /{story_id}/bookmark`
- **Authentication**: Required (User role)

---

## 5. Background Task Triggers (Admin Only)

### A. Manual Ingestion Trigger
- **Endpoint**: `POST /internal/fetch-news`
- **Request Body**: `{ "gnews": true, "rss": true }`

### B. Manual Processing Trigger
- **Endpoint**: `POST /internal/process-story`
- **Behavior**: Immediately queues Celery tasks for embedding and clustering.
