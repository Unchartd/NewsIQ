# NewsIQ API Documentation Drift Report


## Audit Summary

- **Audit Execution Time**: 19-06-2026
- **Total Registered Endpoints**: 61
- **Documented Coverage**: 61 (100.0% if 61 > 0 else 0)
- **Undocumented Endpoints**: 0

---

This report is generated automatically by `docs/scripts/drift-check.py` to identify
missing or outdated references in `/docs/api/` compared to registered FastAPI endpoints.

| Source Router | Endpoint | Expected Doc File | Status |
| :--- | :--- | :--- | :---: |
| `auth.py` | `POST /api/v1/auth/register` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/login` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/refresh` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/logout` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/logout-all` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `GET /api/v1/auth/me` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/verify-email` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/resend-verification` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/forgot-password` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/verify-reset-token` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/reset-password` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `GET /api/v1/auth/sessions` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `DELETE /api/v1/auth/sessions/{session_id}` | `docs/api/auth.md` | ✅ Documented |
| `auth.py` | `POST /api/v1/auth/change-password` | `docs/api/auth.md` | ✅ Documented |
| `oauth.py` | `GET /api/v1/auth/google` | `docs/api/auth.md` | ✅ Documented |
| `oauth.py` | `GET /api/v1/auth/google/callback` | `docs/api/auth.md` | ✅ Documented |
| `consent.py` | `GET /api/v1/consent/region` | `docs/api/consent.md` | ✅ Documented |
| `consent.py` | `GET /api/v1/consent/preferences` | `docs/api/consent.md` | ✅ Documented |
| `consent.py` | `POST /api/v1/consent/preferences` | `docs/api/consent.md` | ✅ Documented |
| `consent.py` | `POST /api/v1/consent/withdraw` | `docs/api/consent.md` | ✅ Documented |
| `consent.py` | `GET /api/v1/consent/logs` | `docs/api/consent.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/profile` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `PATCH /api/v1/users/profile` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/preferences` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `PATCH /api/v1/users/preferences` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/onboarding` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `DELETE /api/v1/users/account` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/notifications` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `PATCH /api/v1/users/notifications/{notification_id}/read` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `DELETE /api/v1/users/notifications/{notification_id}` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/digests` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `PATCH /api/v1/users/digests` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/digests/setup` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `DELETE /api/v1/users/digests/unsubscribe` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/digests/latest` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/events` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/digests/trigger-delivery` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `PATCH /api/v1/users/notifications/read-all` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/history` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `DELETE /api/v1/users/history/{event_id}` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `DELETE /api/v1/users/history` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/subscription/upgrade` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/subscription/cancel` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `GET /api/v1/users/export-data` | `docs/api/users.md` | ✅ Documented |
| `users.py` | `POST /api/v1/users/clear-personalisation` | `docs/api/users.md` | ✅ Documented |
| `sources.py` | `GET /api/v1/sources/{source_id}` | `docs/api/sources.md` | ✅ Documented |
| `sources.py` | `PATCH /api/v1/sources/{source_id}` | `docs/api/sources.md` | ✅ Documented |
| `sources.py` | `DELETE /api/v1/sources/{source_id}` | `docs/api/sources.md` | ✅ Documented |
| `sources.py` | `POST /api/v1/sources/trigger-ingestion` | `docs/api/sources.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/search` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/categories` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/feed/personalized` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/trending-widgets` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/bookmarks` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/{story_id}` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `POST /api/v1/stories/{story_id}/bookmark` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `DELETE /api/v1/stories/{story_id}/bookmark` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/trending` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `GET /api/v1/stories/{story_id}/comparison` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `POST /api/v1/stories/internal/fetch-news` | `docs/api/stories.md` | ✅ Documented |
| `stories.py` | `POST /api/v1/stories/internal/process-story` | `docs/api/stories.md` | ✅ Documented |
