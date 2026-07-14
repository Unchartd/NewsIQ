# Multi-Provider Extraction Layer

This document details the architecture, typed contracts, fallback mechanisms, metrics, and domain-level telemetry of the NewsIQ extraction layer.

---

## 1. Extraction Pipeline Flow

When full content is requested for an article, the extraction layer routes the request through a progressive fallback chain:

```
                  LocalCrawlerProvider
                     (newspaper4k)
                          ↓
                [if failed/unsubstantial]
                          ↓
                 TavilyExtractProvider
                  (Batch 5 URL Buffer)
                          ↓
                      [if failed]
                          ↓
                  FirecrawlProvider
                  (JS/Scrape Fallback)
                          ↓
                      [if failed]
                          ↓
                 RSS Summary Fallback
```

---

## 2. Typed Extraction Contracts

All extraction providers implement the `ExtractionProvider` base class and return a strongly typed `ExtractionResult` dataclass (`app/services/extraction/types.py`).

### `ExtractionFailure` (Enum)
Represents the exact reason for an extraction failure:
- `SUCCESS`: Successfully extracted content.
- `HTTP_ERROR`: Non-200 HTTP response.
- `HTTP_404` / `HTTP_401` / `HTTP_403`: Specific client errors.
- `TIMEOUT`: Request timed out.
- `BOT_BLOCKED`: Bot protection (Cloudflare, etc.) detected.
- `EMPTY_HTML` / `PARSER_FAILED`: Extraction failed to get substantial content.
- `UNKNOWN`: General catch-all error.

### `ExtractionDiagnostics` (Dataclass)
Stores execution telemetry:
- `provider`: String name of the provider.
- `attempts`: Count of attempts made.
- `latency_ms`: Duration of the fetch/extraction.
- `status_code`: Received HTTP status code.
- `bot_detected`: Flag indicating if anti-bot measures blocked the request.
- `fetch_method`: Impersonation method used (e.g. `curl_cffi_chrome`).
- `notes`: List of contextual notes.

---

## 3. Domain Metrics Persistence (`DomainExtractionPolicy`)

The `DomainExtractionPolicy` model records domain-level extraction statistics in the database:

- **EMA Averages**: Success rates and latencies are calculated using Exponential Moving Averages (EMA) with an alpha of `0.1` (10% weight on the newest attempt).
- **Fallback Metrics**: Tracks fallback rates and success rates for each specific provider (`local_success_rate`, `tavily_success_rate`, `firecrawl_success_rate`).
- **Adaptive Routing Ready**: Persisted scores and success indicators lay the groundwork for future domain-aware intelligent extraction routing.
