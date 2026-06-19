# API Overview & Global Configurations

NewsIQ provides a REST API to support the frontend SPA and external integrations.

---

## 1. Global Parameters

- **Base URL**: `/api/v1` (locally: `http://localhost:8000/api/v1`, production: `https://api.newsiq.ai/api/v1`).
- **Content-Type**: Requests and responses must use `application/json`.
- **Authentication**: Bearer token via the HTTP `Authorization` header:
  ```http
  Authorization: Bearer <JWT_ACCESS_TOKEN>
  ```
  Additionally, endpoints accept cookies containing `access_token` and `refresh_token` for browser sessions.

---

## 2. Rate Limiting

The API implements a sliding window rate limiter per client IP:
- **Global Limit**: **100 requests per 60 seconds** per IP address.
- **Lockout Code**: Exceeding this rate returns a `429 Too Many Requests` response.
- **Lockout Headers**:
  - `X-RateLimit-Limit`: Maximum requests permitted in the window.
  - `X-RateLimit-Remaining`: Remaining requests.
  - `X-RateLimit-Reset`: Epoch timestamp when current window resets.

---

## 3. Standard Error Responses

Errors follow a consistent JSON schema matching FastAPI standard error signatures.

### Standard Error Shapes
```json
{
  "detail": "Descriptive error message string."
}
```

### Common HTTP Status Codes

| Code | Type | Description |
| :--- | :--- | :--- |
| `200` | OK | Request succeeded. |
| `201` | Created | Resource successfully created. |
| `400` | Bad Request | Validation error or invalid inputs. |
| `401` | Unauthorized | Session missing, expired, or invalid. |
| `403` | Forbidden | Insufficient permissions (e.g. premium role needed). |
| `404` | Not Found | Resource does not exist. |
| `422` | Unprocessable | Pydantic validation failure. |
| `429` | Too Many Requests | Rate limit exceeded. |
| `500` | Internal Error | Server-side crash or database outage. |

---

## 4. Standard Pagination

Endpoints returning lists (e.g., `/stories`) accept cursor-based or limit-offset parameters:
- **`limit`**: Integer limiting items returned (Default: `20`, Max: `100`).
- **`skip`**: Integer indicating offset items to skip.
