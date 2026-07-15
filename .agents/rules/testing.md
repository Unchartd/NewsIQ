---
trigger: always_on
---

# testing.md — Testing & Verification Rules for NewsIQ

These rules govern the development, configuration, and execution of test suites across services.

## 1. Test Architecture & Naming
- **Framework**: Use `pytest` as the primary testing framework for backend code.
- **Naming Conventions**: Test files must be prefixed with `test_`, and test functions must start with `test_`.
- **AAA Pattern**: Structure tests clearly around Arrange, Act, and Assert.

## 2. Mock Isolation & CI Integrations
- **External Mocking**: Mock out external API dependencies (e.g. OpenAI calls, RSS feed network targets) to avoid network dependencies and unexpected cost changes during automated CI runs.
- **Database Isolation**: Utilize transactions or separate test databases (e.g. Postgres schema, separate Redis DB index, distinct Qdrant test collection) to ensure tests do not pollute production data.
