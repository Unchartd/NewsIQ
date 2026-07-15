---
trigger: always_on
---

# coding.md — Coding Standards for NewsIQ

All code written or modified on this repository must strictly adhere to these standards.

## 1. Strong Typing & Validation
- **Backend (Python)**:
  - Must use strict type annotations for all function signatures and variables.
  - Utilize `pydantic` (v2+) for data validation, serialization, and settings management.
  - Never use dynamic or untyped `dict` where structured schema can be applied.
- **Frontend (TypeScript)**:
  - Prefer TypeScript (`.ts`, `.tsx`) over JavaScript.
  - Define explicit interfaces or types for all component props, API payloads, state, and context objects.
  - Avoid using the `any` type. If necessary, use `unknown` and type-narrow.

## 2. Engineering Principles
- **DRY (Don't Repeat Yourself)**: Extract common logic into reusable modules (e.g., helpers, hooks, utilities).
- **SOLID**: Follow single responsibility, open-closed, Liskov substitution, interface segregation, and dependency inversion principles.
- **Separation of Concerns**: Ensure logic is segmented. Business logic belongs in services/domain layers, database queries in repositories, routes/controllers in entrypoints, and presentation in components.
- **KISS & YAGNI**: Avoid over-engineering. Do not write abstractions for hypothetical future features.

## 3. Error Handling & Resilience
- Never use bare `except:` blocks in Python. Catch specific exceptions (e.g., `HTTPException`, `ValueError`).
- Implement proper logging for all exceptions using structured logs (avoid raw `print` statements).
- Include retry policies with backoff for unstable network operations (e.g., external API calls, LLM requests).
- Use timeouts on all external requests.

## 4. Linting, Formatting, & Quality
- **Python**: Apply formatting using `ruff` or `black`. Ensure imports are organized (`isort` rules).
- **Frontend**: Follow formatting rules set by Prettier/ESLint.
- Ensure all source code changes preserve existing comments and docstrings unless explicitly requested.
