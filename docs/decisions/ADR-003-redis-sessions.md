# ADR-003: Redis Sessions & Revocable Tokens

## Status
Approved

## Context
NewsIQ requires a secure authentication model. Standard stateless JWTs (stored in cookies or local storage) are vulnerable to theft and cannot be revoked before their expiration time without complex blacklist structures.

## Decision
We implement a hybrid session management architecture:
- **Tokens**: Clients authenticate using a short-lived `access_token` (stored strictly in client memory) and a long-lived `refresh_token` (stored in HTTP-Only, Secure cookies).
- **Session Records**: All active sessions are stored in PostgreSQL (`sessions` table) and cached in Redis 7 (`session:<token_hash>`) for fast lookup.
- **Revocation**: Password updates or clicking "Logout All Devices" deletes matching tokens from Redis and PostgreSQL, instantly invalidating those sessions.
- **Token Rotation**: Every refresh cycle deletes the old refresh token and issues a new one.
- **Replay Protection**: If a previously deleted refresh token is reused, the session manager immediately invalidates *all* active sessions for that user ID.

## Alternatives Considered
- **Stateless JWTs**: No server-side session checks. Low overhead, but impossible to revoke tokens instantly if compromised.
- **Stateful Cookie Sessions (Postgres Only)**: Simplifies session invalidation, but performing database lookups on every API request introduces performance bottlenecks.

## Trade-offs
- **Pros**:
  - **Instant Revocation**: Compromised accounts can be locked out immediately.
  - **Token Theft Detection**: Rotation reuse checks detect and stop replay attacks.
  - **High Performance**: Redis caches reduce database load to $O(1)$ lookups.
- **Cons**:
  - **Dependency**: Session validation depends entirely on Redis availability.
  - **Storage Overhead**: Server memory scales with active user sessions.

## Consequences
- Redis must be configured with a persistent disk append-only file (AOF) to survive system restarts without terminating active user sessions.
- In-memory client storage means refreshing the page forces the client to make a silent `/auth/refresh` request to recover the access token.
