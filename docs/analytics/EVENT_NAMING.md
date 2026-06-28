# Event Naming & Catalog Extension Guide

To ensure that the news telemetry catalog remains clean and readable as NewsIQ grows, all new events must follow these strict naming conventions.

---

## 1. Naming Format

- **Lower Snake Case only**: Always use lowercase characters separated by underscores (e.g. `story_view`, not `storyView` or `story-view`).
- **Standard Verb Suffixes**:
  - `_open` / `_close`: Used for modular overlay overlays (e.g. `menu_open`, `timeline_open`).
  - `_click`: Used for click-through transitions that redirect (e.g. `citation_click`).
  - `_view`: Used when a page or section becomes visible (e.g. `story_view`, `summary_view`).
  - `_started` / `_completed` / `_failed`: Used for transactional operations or API processes (e.g. `search_started`, `search_completed`).

---

## 2. Parameter Naming Guidelines

- Always suffix numerical intervals with measurement units:
  - Time durations: `_seconds` or `_milliseconds` (e.g. `duration_seconds`).
  - Percentages: `_percentage` (e.g. `depth_percentage`).
- Keep identifiers standard:
  - Story IDs must always be named `story_id`.
  - User identifiers in `identify` must be named `user_id`.

---

## 3. Registering New Events

If you need to log a new event, follow this workflow:

1. **Add to `types.ts`**:
   - Register the event name in the `EventName` union type in [types.ts](file:///c:/Users/zakau/NewsIQ/apps/web/src/lib/analytics/types.ts).
   - Define the strictly typed parameters in the `EventPayloadMap` interface.
2. **Document in `EVENT_CATALOG.md`**:
   - Add the description and code examples inside [EVENT_CATALOG.md](file:///c:/Users/zakau/NewsIQ/docs/analytics/EVENT_CATALOG.md).
3. **Deploy in Code**:
   - Call `analytics.track("my_new_event", { ... })` in components.
