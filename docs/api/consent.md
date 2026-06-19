# Consent Management Platform (CMP) API Reference

All routes are prefixed with `/api/v1/consent`.

---

## 1. Compliance Geolocation

### Detect Visitor Region
- **Endpoint**: `GET /region`
- **Authentication**: None (Public)
- **Heuristic headers supported**: `CF-IPCountry`, `X-Vercel-IP-Country`, `X-Consent-Region-Override`.
- **Response** (200 OK):
  ```json
  {
    "region": "EU",
    "ip": "192.168.1.xxx",
    "defaults": {
      "essential": true,
      "functional": false,
      "analytics": false,
      "marketing": false
    },
    "require_explicit_opt_in": true,
    "support_opt_out": false
  }
  ```

---

## 2. Preference Management

### A. Fetch Consent State
- **Endpoint**: `GET /preferences`
- **Query Parameters**:
  - `anonymous_id` (string, optional): Client-generated tracking visitor ID.
- **Authentication**: Bearer (optional)
- **Behavior**: Retrieves preferences. If the user is authenticated but does not have user-level preferences, searches for a matching anonymous record and automatically merges it (creating a `merge_anonymous_to_user` audit log).
- **Response** (200 OK):
  ```json
  {
    "id": "01982e1c-...",
    "user_id": "01982e1c-...",
    "anonymous_id": "anon-uuid",
    "essential": true,
    "functional": false,
    "analytics": false,
    "marketing": false,
    "region": "EU",
    "consent_version": "2026-06-v1",
    "accepted_at": "2026-06-19T11:27:00",
    "updated_at": "2026-06-19T11:30:00"
  }
  ```

### B. Save Consent Preferences
- **Endpoint**: `POST /preferences`
- **Request Body**:
  ```json
  {
    "anonymous_id": "anon-uuid",
    "functional": true,
    "analytics": false,
    "marketing": false,
    "region": "EU",
    "consent_version": "2026-06-v1"
  }
  ```
- **Response** (200 OK): Saved `ConsentPreference` entity.
- **Behavior**: Saves choices and creates a new transaction entry in `ConsentAuditLog` with a salted SHA-256 IP hash.

---

## 3. Consent Withdrawal & Audit Logs

### A. Withdraw Consent
- **Endpoint**: `POST /withdraw`
- **Query Parameters**: `anonymous_id=anon-uuid`
- **Behavior**: Resets all non-essential toggles (Functional, Analytics, Marketing) to `false` and records `withdraw_consent` in the audit log.

### B. Download Consent Audit Logs
- **Endpoint**: `GET /logs`
- **Authentication**: Required (User role)
- **Response** (200 OK):
  ```json
  [
    {
      "id": "01982e1c-...",
      "user_id": "01982e1c-...",
      "anonymous_id": "anon-uuid",
      "action": "accept_all",
      "old_value": null,
      "new_value": {
        "functional": true,
        "analytics": true,
        "marketing": true,
        "region": "EU",
        "consent_version": "2026-06-v1"
      },
      "ip_hash": "a4d3f5g2...",
      "timestamp": "2026-06-19T11:27:00",
      "consent_version": "2026-06-v1"
    }
  ]
  ```
