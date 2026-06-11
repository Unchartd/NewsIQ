# Backend Schema Document

# AI News Intelligence Platform

---

# Database Choice

### Primary Database

PostgreSQL 17

Reason:

- ACID compliance
- Full-text search support
- JSONB support
- High scalability
- Excellent indexing

---

# Entity Relationship Diagram

```text
Users
 ├── UserPreferences
 ├── Sessions
 ├── Bookmarks
 ├── SearchHistory
 ├── Notifications
 ├── DigestSubscriptions
 └── UserEvents

Stories
 ├── StoryArticles
 ├── StoryTimelineEvents
 ├── StoryEntities
 ├── StorySourceCoverage
 ├── StoryDifferences
 ├── StoryMetrics
 └── StoryTags

Articles
 ├── Embeddings
 └── Sources

Categories
Locations
Sources
```

---

# Naming Convention

### Table names

Plural

```sql
users
stories
articles
bookmarks
```

---

### IDs

UUID v7

Example:

```text
01982e1c-6e93-75f4-80db-95a5f6d1e2b7
```

---

# USERS

Stores user accounts.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    image_url TEXT,
    password_hash TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    role VARCHAR(30) DEFAULT 'user',
    subscription_plan VARCHAR(30) DEFAULT 'free',
    status VARCHAR(30) DEFAULT 'active',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

## Indexes

```sql
CREATE UNIQUE INDEX idx_users_email
ON users(email);
```

---

# USER_PREFERENCES

One-to-one relationship.

```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY,
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    preferred_summary_type VARCHAR(20),

    theme VARCHAR(20),

    language VARCHAR(20),

    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

Relationship:

```text
users 1 ---- 1 user_preferences
```

---

# USER_CATEGORIES

Many-to-many.

```sql
CREATE TABLE user_categories (
    user_id UUID REFERENCES users(id),
    category_id UUID REFERENCES categories(id),

    PRIMARY KEY(user_id, category_id)
);
```

---

# USER_LOCATIONS

```sql
CREATE TABLE user_locations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),

    country_code VARCHAR(10),
    state_name VARCHAR(100),
    city_name VARCHAR(100)
);
```

---

# SESSIONS

Better Auth session table.

```sql
CREATE TABLE sessions (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    token TEXT UNIQUE,

    ip_address TEXT,

    user_agent TEXT,

    expires_at TIMESTAMP,

    created_at TIMESTAMP
);
```

---

Index

```sql
CREATE INDEX idx_sessions_user
ON sessions(user_id);
```

---

# OAUTH_ACCOUNTS

```sql
CREATE TABLE oauth_accounts (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    provider VARCHAR(50),

    provider_account_id TEXT,

    access_token TEXT,

    refresh_token TEXT,

    expires_at TIMESTAMP
);
```

---

# CATEGORIES

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY,

    slug VARCHAR(100) UNIQUE,

    name VARCHAR(100),

    icon VARCHAR(100),

    created_at TIMESTAMP
);
```

Examples

```text
technology
politics
sports
business
health
science
weather
```

---

# SOURCES

News publishers.

```sql
CREATE TABLE sources (
    id UUID PRIMARY KEY,

    name VARCHAR(255),

    slug VARCHAR(255) UNIQUE,

    website_url TEXT,

    logo_url TEXT,

    country_code VARCHAR(10),

    rss_url TEXT,

    active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMP
);
```

---

Indexes

```sql
CREATE UNIQUE INDEX idx_sources_slug
ON sources(slug);
```

---

# ARTICLES

Raw articles.

```sql
CREATE TABLE articles (
    id UUID PRIMARY KEY,

    source_id UUID REFERENCES sources(id),

    title TEXT,

    description TEXT,

    content TEXT,

    url TEXT UNIQUE,

    author VARCHAR(255),

    language VARCHAR(20),

    image_url TEXT,

    published_at TIMESTAMP,

    crawled_at TIMESTAMP,

    embedding_status VARCHAR(30),

    created_at TIMESTAMP
);
```

---

Indexes

```sql
CREATE UNIQUE INDEX idx_articles_url
ON articles(url);

CREATE INDEX idx_articles_published
ON articles(published_at DESC);

CREATE INDEX idx_articles_source
ON articles(source_id);
```

---

# STORIES

AI-generated event clusters.

```sql
CREATE TABLE stories (
    id UUID PRIMARY KEY,

    headline TEXT,

    one_line_summary TEXT,

    short_summary TEXT,

    detailed_summary TEXT,

    category_id UUID REFERENCES categories(id),

    location_country VARCHAR(100),

    location_state VARCHAR(100),

    location_city VARCHAR(100),

    trend_score NUMERIC(10,2),

    story_status VARCHAR(30),

    first_seen_at TIMESTAMP,

    updated_at TIMESTAMP
);
```

---

Indexes

```sql
CREATE INDEX idx_stories_trend
ON stories(trend_score DESC);

CREATE INDEX idx_stories_category
ON stories(category_id);

CREATE INDEX idx_stories_updated
ON stories(updated_at DESC);
```

---

# STORY_ARTICLES

Many-to-many.

```sql
CREATE TABLE story_articles (
    story_id UUID REFERENCES stories(id) ON DELETE CASCADE,

    article_id UUID REFERENCES articles(id),

    PRIMARY KEY(story_id, article_id)
);
```

Relationship

```text
stories ----< story_articles >---- articles
```

---

# STORY_TIMELINE_EVENTS

```sql
CREATE TABLE story_timeline_events (
    id UUID PRIMARY KEY,

    story_id UUID REFERENCES stories(id),

    event_time TIMESTAMP,

    description TEXT,

    created_at TIMESTAMP
);
```

---

Index

```sql
CREATE INDEX idx_story_timeline_story
ON story_timeline_events(story_id);
```

---

# STORY_SOURCE_COVERAGE

Stores focus areas.

```sql
CREATE TABLE story_source_coverage (
    id UUID PRIMARY KEY,

    story_id UUID REFERENCES stories(id),

    source_id UUID REFERENCES sources(id),

    focus_area TEXT,

    published_at TIMESTAMP
);
```

---

# STORY_DIFFERENCES

```sql
CREATE TABLE story_differences (
    id UUID PRIMARY KEY,

    story_id UUID REFERENCES stories(id),

    source_id UUID REFERENCES sources(id),

    unique_information TEXT,

    missing_information TEXT,

    contradictions TEXT
);
```

---

# STORY_TAGS

```sql
CREATE TABLE story_tags (
    id UUID PRIMARY KEY,

    story_id UUID REFERENCES stories(id),

    tag_name VARCHAR(100)
);
```

---

# STORY_ENTITIES

NER extraction.

```sql
CREATE TABLE story_entities (
    id UUID PRIMARY KEY,

    story_id UUID REFERENCES stories(id),

    entity_type VARCHAR(30),

    entity_value VARCHAR(255)
);
```

Types

```text
PERSON
ORG
LOCATION
EVENT
COUNTRY
```

---

# STORY_METRICS

Analytics.

```sql
CREATE TABLE story_metrics (
    story_id UUID PRIMARY KEY REFERENCES stories(id),

    views BIGINT DEFAULT 0,

    bookmarks BIGINT DEFAULT 0,

    shares BIGINT DEFAULT 0,

    clicks BIGINT DEFAULT 0
);
```

---

# BOOKMARKS

Many-to-many.

```sql
CREATE TABLE bookmarks (
    user_id UUID REFERENCES users(id),

    story_id UUID REFERENCES stories(id),

    created_at TIMESTAMP,

    PRIMARY KEY(user_id, story_id)
);
```

---

Indexes

```sql
CREATE INDEX idx_bookmarks_user
ON bookmarks(user_id);
```

---

# SEARCH_HISTORY

```sql
CREATE TABLE search_history (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    query TEXT,

    searched_at TIMESTAMP
);
```

---

# NOTIFICATIONS

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    title TEXT,

    body TEXT,

    notification_type VARCHAR(50),

    is_read BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP
);
```

---

Index

```sql
CREATE INDEX idx_notifications_user
ON notifications(user_id);
```

---

# DIGEST_SUBSCRIPTIONS

```sql
CREATE TABLE digest_subscriptions (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    frequency VARCHAR(30),

    delivery_channel VARCHAR(30),

    enabled BOOLEAN DEFAULT TRUE
);
```

---

# USER_EVENTS

Analytics.

```sql
CREATE TABLE user_events (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    story_id UUID REFERENCES stories(id),

    event_type VARCHAR(50),

    metadata JSONB,

    created_at TIMESTAMP
);
```

---

Types

```text
view_story
bookmark_story
share_story
search
```

---

Index

```sql
CREATE INDEX idx_user_events_user
ON user_events(user_id);

CREATE INDEX idx_user_events_story
ON user_events(story_id);
```

---

# API_KEYS

Enterprise users.

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,

    user_id UUID REFERENCES users(id),

    key_hash TEXT,

    plan VARCHAR(30),

    expires_at TIMESTAMP,

    created_at TIMESTAMP
);
```

---

# ROLE SYSTEM

```text
guest
user
premium
admin
```

---

# PERMISSIONS

## Guest

Can

- View stories
- Search
- Trending

Cannot

- Bookmark
- Preferences
- Digest

---

## User

Can

- Bookmark
- Preferences
- Notifications

---

## Premium

Can

- AI chat
- Unlimited summaries
- Personalized digest

---

## Admin

Can

- Manage stories
- Manage users
- Recompute clusters
- Delete sources

---

# Ownership Rules

---

## Users

Own:

```text
preferences
bookmarks
sessions
notifications
search history
```

Only owner or admin can access.

---

## Stories

Owned by system.

Users cannot modify.

Admins can reprocess.

---

## Articles

Owned by ingestion pipeline.

Immutable.

---

## Sources

Admin-owned.

---

# Session Handling

---

Access Token

JWT

Lifetime:

```text
15 minutes
```

---

Refresh Token

```text
30 days
```

Stored:

HTTP-only cookie.

---

Session Table

Tracks:

- Device
- IP
- Browser
- Expiration

---

Multiple sessions allowed.

---

Logout

Deletes session row.

---

Logout All Devices

Deletes:

```sql
DELETE FROM sessions
WHERE user_id = ?
```

---

# Redis Cache Keys

### Story

```text
story:{storyId}
```

TTL

15 minutes

---

### Trending

```text
trending:global
trending:india
```

TTL

5 minutes

---

### Search

```text
search:{hash}
```

TTL

30 minutes

---

# Vector Database (Qdrant)

Collection

### article_embeddings

Payload

```json
{
  "article_id": "uuid",
  "source_id": "uuid",
  "category": "technology",
  "country": "india",
  "published_at": "timestamp"
}
```

Dimension

```text
1536
```

Similarity

Cosine.

---

# Recommended Production Schema Improvements

### Use partitioning for

- articles
- user_events
- notifications

By month.

---

### Use materialized views for

Trending stories.

---

### Use TimescaleDB extension for

Timeline analytics.

---

# Final Relationship Summary

```text
users
│
├── user_preferences
├── sessions
├── bookmarks
├── notifications
├── search_history
├── digest_subscriptions
├── user_events
│
stories
│
├── story_articles
├── story_timeline_events
├── story_entities
├── story_source_coverage
├── story_differences
├── story_metrics
├── story_tags
│
articles
│
└── sources
```

This schema comfortably supports **100M+ articles**, **millions of users**, AI-generated story clustering, personalization, analytics, and future premium/enterprise capabilities without requiring major redesign.
