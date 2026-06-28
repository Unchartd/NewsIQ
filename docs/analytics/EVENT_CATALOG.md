# NewsIQ Event Catalog

This document details all strongly-typed events supported by the NewsIQ analytics layer, including parameters and code invocation examples.

---

## 1. User Lifecycle Events

### `user_signup`
Fired when a user successfully registers a new account.
- **Parameters**: 
  - `method`: `"email" | "google"`
- **Example**:
  ```typescript
  analytics.track("user_signup", { method: "email" });
  ```

### `user_login`
Fired when a user successfully logs in or a login attempt fails.
- **Parameters**:
  - `method`: `"email" | "google"`
  - `success`: `boolean`
- **Example**:
  ```typescript
  analytics.track("user_login", { method: "google", success: true });
  ```

### `logout`
Fired when a user explicitly logs out or their token expires.
- **Parameters**: None
- **Example**:
  ```typescript
  analytics.track("logout", {});
  ```

---

## 2. Story Content Events

### `story_view`
Fired when a user views a story page.
- **Parameters**:
  - `story_id`: `string`
  - `headline`: `string`
  - `category`: `string` (optional)
  - `tags`: `string[]` (optional)
  - `source_count`: `number` (optional)
  - `article_count`: `number` (optional)
- **Example**:
  ```typescript
  analytics.track("story_view", {
    story_id: "story-123",
    headline: "Markets Hit Record High",
    category: "Business",
    tags: ["stocks", "inflation"],
    source_count: 5,
    article_count: 8
  });
  ```

### `story_scroll`
Fired when a user reaches specific scroll thresholds on a story detail page.
- **Parameters**:
  - `story_id`: `string`
  - `depth_percentage`: `25 | 50 | 75 | 90 | 100`
- **Example**:
  ```typescript
  analytics.track("story_scroll", { story_id: "story-123", depth_percentage: 50 });
  ```

### `story_complete`
Fired when a user scrolls to the bottom (90%+) and reads for a significant duration.
- **Parameters**:
  - `story_id`: `string`
  - `read_time_seconds`: `number`
- **Example**:
  ```typescript
  analytics.track("story_complete", { story_id: "story-123", read_time_seconds: 45 });
  ```

### `story_share`
Fired when the share button is clicked.
- **Parameters**:
  - `story_id`: `string`
  - `platform`: `string` (e.g. `"copy_link"`, `"twitter"`, `"linkedin"`)
- **Example**:
  ```typescript
  analytics.track("story_share", { story_id: "story-123", platform: "copy_link" });
  ```

### `story_bookmark`
Fired when a story is saved or removed from saved list.
- **Parameters**:
  - `story_id`: `string`
  - `action`: `"add" | "remove"`
- **Example**:
  ```typescript
  analytics.track("story_bookmark", { story_id: "story-123", action: "add" });
  ```

---

## 3. AI Feature Events

### `summary_view`
Fired when a user switches the active summary depth tab.
- **Parameters**:
  - `story_id`: `string`
  - `summary_type`: `"one_line" | "short" | "detailed"`
- **Example**:
  ```typescript
  analytics.track("summary_view", { story_id: "story-123", summary_type: "detailed" });
  ```

### `summary_expand`
Fired when detailed summary is chosen (expansion event).
- **Parameters**:
  - `story_id`: `string`
- **Example**:
  ```typescript
  analytics.track("summary_expand", { story_id: "story-123" });
  ```

### `difference_engine_open`
Fired when a story detail page contains and renders the source contradiction differences engine table.
- **Parameters**:
  - `story_id`: `string`
  - `conflict_count`: `number`
- **Example**:
  ```typescript
  analytics.track("difference_engine_open", { story_id: "story-123", conflict_count: 2 });
  ```

### `timeline_open`
Fired when a story timeline is rendered and viewed.
- **Parameters**:
  - `story_id`: `string`
  - `timeline_length`: `number`
- **Example**:
  ```typescript
  analytics.track("timeline_open", { story_id: "story-123", timeline_length: 5 });
  ```

---

## 4. Search Events

### `search_started`
Fired when loading starts for a search query.
- **Parameters**:
  - `search_term`: `string`
- **Example**:
  ```typescript
  analytics.track("search_started", { search_term: "AI regulations" });
  ```

### `search_completed`
Fired when search successfully completes with matches.
- **Parameters**:
  - `search_term`: `string`
  - `result_count`: `number`
- **Example**:
  ```typescript
  analytics.track("search_completed", { search_term: "AI regulations", result_count: 14 });
  ```

### `search_no_results`
Fired when search completes and returns 0 matches.
- **Parameters**:
  - `search_term`: `string`
- **Example**:
  ```typescript
  analytics.track("search_no_results", { search_term: "unfindablequery" });
  ```

### `search_filter_applied`
Fired when a search results category filter chip is selected.
- **Parameters**:
  - `filter_name`: `string`
- **Example**:
  ```typescript
  analytics.track("search_filter_applied", { filter_name: "technology" });
  ```

---

## 5. Performance & Errors

### `web_vital_metric`
Fired when Core Web Vitals report speeds.
- **Parameters**:
  - `metric_name`: `string` (e.g. `"FCP"`, `"LCP"`, `"CLS"`, `"INP"`, `"TTFB"`)
  - `metric_value`: `number`
  - `metric_id`: `string`
  - `metric_rating`: `"good" | "needs-improvement" | "poor"`
- **Example**:
  ```typescript
  analytics.track("web_vital_metric", {
    metric_name: "LCP",
    metric_value: 1250,
    metric_id: "v4-12345-67890",
    metric_rating: "good"
  });
  ```

### `api_error`
Fired automatically when backend queries return non-2xx status errors.
- **Parameters**:
  - `endpoint`: `string`
  - `status_code`: `number` (optional)
  - `error_message`: `string`
- **Example**:
  ```typescript
  analytics.track("api_error", {
    endpoint: "/stories/feed/personalized",
    status_code: 500,
    error_message: "Database connection timeout"
  });
  ```
