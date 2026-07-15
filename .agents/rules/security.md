---
trigger: always_on
---

# security.md — Security Rules for NewsIQ

These rules define security protocols, coding constraints, and vulnerability prevention guidelines.

## 1. Secrets & Env Configurations
- **Centralized Secrets**: Load all credentials, tokens, and DB connection details through environment variables (using Pydantic `Settings`).
- **No Hardcoded Keys**: Never check in passwords, API keys, JWT secret keys, or private SSH keys. Ensure `.env` is listed in `.gitignore`.

## 2. API Security & Input Protection
- **JWT Authentication**: Validate token signatures, verify claims, and enforce expiration times on every secure route.
- **Rate-Limiting**: Enforce IP-based and user-based rate-limits on all public endpoints.
- **Input Sanitization**: Always sanitize and validate client-supplied parameters using Pydantic models. Guard AI prompt interfaces against prompt injections.
