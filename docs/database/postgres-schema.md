# PostgreSQL Schema Catalog

This document details active table columns, keys, indexes, and constraints in the PostgreSQL 17 primary database.

---

## 1. Table Index Reference

### A. User Management

#### `users`
- **Columns**:
  - `id` (UUID, Primary Key): Time-ordered UUID.
  - `email` (VARCHAR(255), Not Null): Unique login identifier.
  - `name` (VARCHAR(255), Nullable): Full user name.
  - `image_url` (TEXT, Nullable): Profile avatar link.
  - `password_hash` (TEXT, Nullable): Encrypted using `bcrypt`.
  - `email_verified` (BOOLEAN, Default: `false`): Verification status.
  - `role` (VARCHAR(30), Default: `'user'`): `guest`, `user`, `premium`, `admin`.
  - `subscription_plan` (VARCHAR(30), Default: `'free'`): Subscription status.
  - `status` (VARCHAR(30), Default: `'active'`): `active` or `deactivated`.
  - `failed_login_attempts` (INT, Default: `0`): Lockout counter.
  - `locked_until` (TIMESTAMP, Nullable): Temporary login lockout expiry.
  - `email_verification_token` (VARCHAR(255), Nullable)
  - `password_reset_token` (VARCHAR(255), Nullable)
- **Indexes**:
  - `idx_users_email` (UNIQUE): On `email`.

#### `user_preferences`
- **Columns**:
  - `id` (UUID, Primary Key)
  - `user_id` (UUID, FK: `users.id`, ON DELETE CASCADE, Unique)
  - `preferred_summary_type` (VARCHAR(20)): `short`, `long`, `timeline`.
  - `theme` (VARCHAR(20)): Light / dark / system mode.
  - `language` (VARCHAR(20))

#### `user_categories` & `user_locations`
- Join tables for personalized feed filtering. `user_categories` has primary composite keys `(user_id, category_id)`.

---

### B. Core Content Elements

#### `sources`
- **Columns**:
  - `id` (UUID, Primary Key)
  - `name` (VARCHAR(255))
  - `slug` (VARCHAR(255), Unique, Index)
  - `website_url` (TEXT)
  - `logo_url` (TEXT)
  - `active` (BOOLEAN, Default: `true`): Deactivated instead of deleted.

#### `articles`
- **Columns**:
  - `id` (UUID, Primary Key)
  - `source_id` (UUID, FK: `sources.id`)
  - `title` (TEXT)
  - `description` (TEXT)
  - `content` (TEXT): Full article text.
  - `url` (TEXT, Unique, Index)
  - `published_at` (TIMESTAMP, Index)
  - `embedding_status` (VARCHAR(30), Default: `'pending'`): Ingestion status.
- **Indexes**:
  - `idx_articles_published` (Descending): Optimized for feed queries.
  - `idx_articles_source`: Fast source filter lookups.

---

### C. Story Clusters & Summaries

#### `stories`
- **Columns**:
  - `id` (UUID, Primary Key)
  - `headline` (TEXT)
  - `one_line_summary` (TEXT)
  - `short_summary` (TEXT)
  - `detailed_summary` (TEXT)
  - `key_facts` (JSONB): Bullet-points array.
  - `category_id` (UUID, FK: `categories.id`, Index)
  - `trend_score` (NUMERIC(10, 6), Index): Ranked score.
  - `created_at` (TIMESTAMP, Default: UTC, Index)

#### `story_articles`
- Many-to-many join table mapping `story_id` (FK: `stories.id`, CASCADE) and `article_id` (FK: `articles.id`).

#### `story_timeline_events`
- Chronological sub-events linked to a story. Contains `event_time` (TIMESTAMP) and `description` (TEXT).

#### `story_differences`
- Publisher specific difference engine outputs. Contains `story_id`, `source_id`, `unique_information` (TEXT), `missing_information` (TEXT), and `contradictions` (TEXT).

#### `story_metrics`
- Counter cache table tracking engagements: `views`, `bookmarks`, `shares`, `clicks`.

---

### D. CMP Consent Management

#### `consent_preferences`
- Current consent settings. Columns: `id`, `user_id` (Unique, FK users, CASCADE), `anonymous_id` (Unique), `essential`, `functional`, `analytics`, `marketing`, `region`, `consent_version`, `accepted_at`, `updated_at`.

#### `consent_audit_logs`
- Log ledger. Columns: `id`, `user_id` (FK users, SET NULL), `anonymous_id`, `action`, `old_value` (JSONB), `new_value` (JSONB), `ip_hash` (VARCHAR(64)), `timestamp`, `consent_version`.
