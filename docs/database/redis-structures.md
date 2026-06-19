# Redis Cache Key Schema

NewsIQ utilizes Redis 7 for high-speed session management, response caching, rate limiting, and message queuing. This document lists all key namespaces, data types, and TTL configurations.

---

## 1. Key Namespaces & Prefixes

| Key Prefix | Data Type | Purpose | TTL | Eviction Policy |
| :--- | :---: | :--- | :---: | :--- |
| `session:<token_hash>` | String | Caches logged-in user session data. | 30 Days | `noeviction` |
| `session_user:<user_id>` | Set | Set of active session hashes belonging to a user. Used to revoke all devices on password reset or token reuse detection. | 30 Days | `noeviction` |
| `story:<story_uuid>` | String (JSON) | Caches fully serialized `StoryDetailResponse` payloads. | 15 Minutes | `volatile-lru` |
| `trending:<scope_slug>` | String (JSON) | Caches first-page list responses for the trending feeds (e.g. `trending:global` or `trending:technology`). | 5 Minutes | `volatile-lru` |
| `rate_limit:<ip>` | String | Sliding window integer counter for API requests. | 60 Seconds | `volatile-lru` |
| `rate_limit:resend:<email>` | String | Cooldown lock to restrict resending email verification requests. | 60 Seconds | `volatile-lru` |
| `rate_limit:resend:ip:<ip>` | String | Rate limits total verification emails dispatched per IP. | 1 Hour | `volatile-lru` |
| `celery` | List / Set | Internal queues and schedules managed by Celery worker processes. | Managed | N/A |

---

## 2. Key Structures Detail

### A. Session Caching
- **Key**: `session:a4d3f5g2...` (Salted SHA-256 hash of the `refresh_token`).
- **Value**:
  ```json
  {
    "session_id": "01982e1c-...",
    "user_id": "01982e1c-...",
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "expires_at": "2026-07-19T11:27:00",
    "created_at": "2026-06-19T11:27:00"
  }
  ```

### B. User Active Sessions Tracker
- **Key**: `session_user:01982e1c-6e93-75f4-80db-95a5f6d1e2b7` (User ID).
- **Value**: Set of session hashes:
  ```text
  { "session:hashA", "session:hashB" }
  ```
- **Usage**: When a user updates their password or when session theft is flagged, the system issues a `DEL` command for every session hash registered in this set, logging the user out across all client devices.

---

## 3. Eviction & Resource Protection

- **Production Configuration**: The Redis instance runs with a `maxmemory` limit.
- **Eviction Rule**: `volatile-lru` (Least Recently Used among keys with an expire set).
- **Protected Keys**: Keys without an explicit expire set (such as critical sessions tracking) will not be evicted during low-memory conditions, protecting active logins from termination.
