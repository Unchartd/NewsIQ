# ADR-005: RBAC Subscription System

## Status
Approved

## Context
NewsIQ operates under a freemium model. Free users get basic summaries, while premium subscribers get unlimited AI timelines, full publisher differences, and daily email digests.

## Decision
We enforce a role-based access control (RBAC) model at the route level in the FastAPI backend:
- **Database Schema**: The `users` table contains `role` (`guest`, `user`, `premium`, `admin`) and `subscription_plan` (`free`, `premium`).
- **Token Claims**: User roles and plans are encoded in the JWT access token payload, allowing the client frontend to hide premium-only UI elements.
- **FastAPI Dependencies**: Protected endpoints inject access control dependencies (e.g., `deps.get_current_active_premium_user`), validating plans before running database operations.

## Alternatives Considered
- **Client-Only Enforcement**: Relying on frontend visibility toggles. This is unsafe because users can easily bypass client-side checks and query endpoints directly.
- **Microservice Authorization Mesh**: Overly complex for a single-backend application.

## Trade-offs
- **Pros**:
  - **Secure**: Entitlements are validated server-side on every API call.
  - **Low Latency**: JWT claims allow the frontend to toggle UI states immediately without querying the backend user profile first.
- **Cons**:
  - **Token Expiry Lag**: If a user cancels their subscription, their current access token remains valid until it expires (up to 15 minutes).

## Consequences
- Upgrading or downgrading plans requires invalidating and forcing a refresh of the user's active session to update the JWT claims.
