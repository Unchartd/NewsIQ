# logging.md — Logging Standards for NewsIQ

This standard defines formatting, log levels, contextual metadata, and secret filtering rules.

## 1. Structure & Format
- **Format**: All logs in production must be structured JSON logs.
- **Mandatory Fields**: Every log entry must include:
  - `timestamp`: UTC ISO 8601 format.
  - `level`: `INFO`, `WARNING`, `ERROR`, `CRITICAL`, or `DEBUG`.
  - `request_id`: Tracing correlation ID (OpenTelemetry/FastAPI middleware).
  - `module`: The origin file or class naming.

## 2. PII & Secret Masking
- **Filters**: Implement custom logging filters to scan log messages and dict payloads for fields like `password`, `token`, `secret`, `jwt`, `key`, and replace them with `[MASKED]`.
- **Trace logs**: Avoid printing full exception trace logs on standard `INFO` level. Use `logger.exception()` on `ERROR`/`CRITICAL` events only.
