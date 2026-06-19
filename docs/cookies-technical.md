# NewsIQ Cookies & Browser Storage Technical Reference

This document serves as the authoritative technical reference for developers, security engineers, and privacy auditors on how cookies, local storage, session caching, and consent lifecycle are managed within the NewsIQ platform.

---

## 1. Core Architecture

NewsIQ uses a decoupled cookie and consent architecture. Session states are stored in server-side Redis and PostgreSQL caches, linked to client browsers via secure HTTP-only cookies, while granular privacy preferences are handled by the Consent Management Platform (CMP) on both client and backend layers.

```
       +-------------------------------------------------------------+
       |                        Client Browser                       |
       |                                                             |
       |  +------------------+  +-----------------+  +------------+  |
       |  |   Auth Cookies   |  |   LocalStorage  |  |  Tracking  |  |
       |  |  (access/refresh)|  |  (anon_id, UI)  |  |  Scripts   |  |
       |  +--------+---------+  +--------+--------+  +-----+------+  |
       +-----------|---------------------|-----------------|---------+
                   |                     |                 |
                   | REST API Requests   |                 | Block / Inject
                   v                     v                 | (CMP Guard)
       +---------------------------------+                 |
       |             FastAPI / Uvicorn Server              |                 |
       |                                 |                 |
       |  +---------------------------+  |                 |
       |  |   Consent Preferences API |<-------------------+
       |  +-------------+-------------+  |
       +----------------|----------------+
                        |
                        +--------+------------------+
                                 |                  |
                                 v                  v
                       +-------------------+  +-----------+
                       | PostgreSQL DB     |  | Redis     |
                       | (Preferences,     |  | (Session  |
                       |  Audit Logs)      |  |  Cache)   |
                       +-------------------+  +-----------+
```

---

## 2. Storage Specifications & Configurations

Every cookie set by the NewsIQ domain strictly adheres to security best practices to prevent Cross-Site Scripting (XSS), Cross-Site Request Forgery (CSRF), and Session Hijacking.

### A. Authentication & Session Cookies
These cookies are managed strictly by the backend and have the following attributes:

1. **`access_token`**
   - **Type**: Cookie
   - **Lifetime**: 15 minutes (short-lived)
   - **Attributes**: `HttpOnly`, `Secure` (production), `SameSite=Lax`, `Path=/`
   - **Purpose**: Temporary JWT credential used for authenticating stateless API requests.
   
2. **`refresh_token`**
   - **Type**: Cookie
   - **Lifetime**: 30 days
   - **Attributes**: `HttpOnly`, `Secure` (production), `SameSite=Lax`, `Path=/`
   - **Purpose**: High-security rotating credential used to generate new `access_token` pairs.

### B. Client-Side Preferences & Identifiers
These values are stored in the client browser to optimize user experience and track compliance state:

1. **`niq_anonymous_id`**
   - **Type**: LocalStorage
   - **Lifetime**: Persistent (re-generated on deletion)
   - **Purpose**: Time-ordered UUID v4 assigned to anonymous visitors to persist consent configurations and merge configurations upon sign-in.

2. **`newsiq-auth`**
   - **Type**: LocalStorage (Zustand persist)
   - **Lifetime**: Persistent
   - **Purpose**: Stores non-sensitive user metadata (ID, email, name, role) to avoid layout flashing before initial authentication check finishes.

3. **`newsiq-ui`**
   - **Type**: LocalStorage (Zustand persist)
   - **Lifetime**: Persistent
   - **Purpose**: User interface preferences (sidebar state, preferred summary length, selected filters).

4. **`theme` & `next-theme`**
   - **Type**: LocalStorage
   - **Lifetime**: Persistent
   - **Purpose**: Active theme styling (dark, light, or system).

---

## 3. Database Schema Reference

Backend tables are defined inside [consent.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/models/consent.py).

### A. Active Preferences
The `consent_preferences` table holds the current target states for active visitor sessions.

```sql
CREATE TABLE consent_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    anonymous_id VARCHAR(255) UNIQUE NOT NULL,
    essential BOOLEAN DEFAULT TRUE NOT NULL,
    functional BOOLEAN DEFAULT FALSE NOT NULL,
    analytics BOOLEAN DEFAULT FALSE NOT NULL,
    marketing BOOLEAN DEFAULT FALSE NOT NULL,
    region VARCHAR(50) NOT NULL,
    consent_version VARCHAR(50) NOT NULL,
    accepted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);
CREATE INDEX idx_consent_preferences_anon ON consent_preferences(anonymous_id);
```

### B. Consent Audit Trail
To prove compliance under **GDPR Art. 7(1)**, the immutable `consent_audit_logs` table logs all historical preference transitions.

```sql
CREATE TABLE consent_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    anonymous_id VARCHAR(255) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_value JSONB,
    new_value JSONB NOT NULL,
    ip_hash VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    consent_version VARCHAR(50) NOT NULL
);
CREATE INDEX idx_consent_audit_logs_user ON consent_audit_logs(user_id);
CREATE INDEX idx_consent_audit_logs_anon ON consent_audit_logs(anonymous_id);
```

---

## 4. API Endpoints Reference

All CMP API endpoints are prefixed with `/api/v1/consent` and registered in the core router.

### 1. Detect Compliance Region
- **Route**: `GET /api/v1/consent/region`
- **Authentication**: None (Public)
- **Response Schema**:
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

### 2. Fetch Consent Preferences
- **Route**: `GET /api/v1/consent/preferences`
- **Query Params**: `anonymous_id=UUID` (optional)
- **Authentication**: Bearer (optional)
- **Behavior**: Auto-merges matching anonymous records to the user account if authenticated but user record is absent.
- **Response**: Returns matching `ConsentPreference` row or `null`.

### 3. Save / Update Preferences
- **Route**: `POST /api/v1/consent/preferences`
- **Payload**:
  ```json
  {
    "anonymous_id": "anon-uuid",
    "functional": true,
    "analytics": true,
    "marketing": false,
    "region": "EU",
    "consent_version": "2026-06-v1"
  }
  ```
- **Behavior**: Saves state, calculates difference, hashes client IP, and commits audit logs.

### 4. Withdraw All Consent
- **Route**: `POST /api/v1/consent/withdraw`
- **Query Params**: `anonymous_id=anon-uuid`
- **Behavior**: Sets all non-essential preferences to `false` and records `withdraw_consent` in the audit log.

### 5. Download Compliance Logs
- **Route**: `GET /api/v1/consent/logs`
- **Authentication**: Required (User role)
- **Response**: List of historical `ConsentAuditLog` records for the logged-in user.

---

## 5. Security & Privacy Implementations

### A. IP Anonymization (GDPR Data Minimization)
To store proof of consent without storing raw user IP addresses, the backend applies a salted, cryptographic SHA-256 hash:

```python
def _hash_ip(ip: str) -> str:
    # SECRET_KEY is set in production configs and kept secret
    salted = f"{ip}:{settings.SECRET_KEY}"
    return hashlib.sha256(salted.encode()).hexdigest()
```

### B. Session Token Rotation (Replay Protection)
Our session service prevents session hijacking by rotating `refresh_token` credentials:
- When `/auth/refresh` is requested, the server verifies the token against server-side Redis/PostgreSQL.
- Upon verification, the old token is permanently revoked. A new access token and a fresh rotating refresh token are set.
- **Replay Attack Defense**: If a client attempts to reuse a revoked refresh token, the server suspects session hijacking, invalidates **all active sessions** for that user ID, and forces all client sessions to re-authenticate immediately.

### C. Right to be Forgotten (Account Deletion)
When `DELETE /api/v1/users/account` is executed:
- The associated `ConsentPreference` record is cascaded and deleted.
- The `ConsentAuditLog` entries are kept to satisfy tax and regulatory retention requirements but are **fully anonymized** by settings `user_id = NULL` and removing all linkable PII elements.

---

## 6. Developer Integration Guidelines

### A. Adding a New Cookie or Storage Item
If you need to introduce a new browser storage mechanism:
1. Identify the category:
   - **Essential**: Strictly necessary for page functionality or user security.
   - **Functional**: Custom layouts or visual settings.
   - **Analytics**: Telemetry and metrics tracking.
   - **Marketing**: Conversions and advertising tracking.
2. Update the cookie inventory documentation in [cookie-inventory.md](file:///c:/Users/zakau/NewsIQ/docs/cookie-inventory.md) and [/legal?policy=cookies](file:///c:/Users/zakau/NewsIQ/apps/web/src/app/(legal)/legal/page.tsx).
3. If non-essential, ensure its injection is guarded by checking state variables:
   ```ts
   const { analyticsEnabled } = useConsent();
   if (analyticsEnabled) {
     // Inject tracker script or write to local storage
   }
   ```

### B. Consuming Consent State in React
The React context exposes variables representing the visitor's current choices:

```tsx
import { useConsent } from "@/components/legal/consent-provider";

export default function MyComponent() {
  const { 
    functionalEnabled, 
    analyticsEnabled, 
    marketingEnabled 
  } = useConsent();

  return (
    <div>
      {functionalEnabled ? (
        <CustomLayout />
      ) : (
        <StandardLayout />
      )}
    </div>
  );
}
```

### C. Triggering Preferences Modal Programmatically
You can open the cookie configuration modal from any component on the frontend by dispatching a custom window event:

```tsx
const openCookieSettings = () => {
  window.dispatchEvent(new CustomEvent("open-cookie-settings"));
};
```
This is useful for footers, privacy policies, and banner links.
