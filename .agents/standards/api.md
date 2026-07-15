# api.md — API Standards for NewsIQ

This standard defines the route structure, response envelopes, and versioning rules for REST APIs.

## 1. URI Paths & Versioning
- **Prefixing**: All routes must start with `/api/v1/`.
- **Resource Naming**: Use plural nouns for resources (e.g. `/api/v1/stories`, `/api/v1/articles`).
- **HTTP Methods**:
  - `GET`: Retrieve resource or collections.
  - `POST`: Create a resource.
  - `PUT`: Update a resource entirely.
  - `PATCH`: Partially update a resource.
  - `DELETE`: Remove a resource.

## 2. Response Wrappers & Envelopes
All responses must return a standardized JSON structure:

### Success Response
```json
{
  "status": "success",
  "data": {
    "id": "123",
    "title": "Example Story"
  }
}
```

### Error Response
```json
{
  "status": "error",
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested story does not exist.",
    "details": {}
  }
}
```
