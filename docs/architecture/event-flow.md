# System Event Flows

This document details the sequence of transactions and event messages exchanged during key operations: authentication, token rotation, and consent synchronization.

---

## 1. Authentication & Token Issuance Flow

When a user submits credentials to `/auth/login`:
1. `AuthService` validates the password against PostgreSQL using `bcrypt`.
2. Upon success, a time-ordered session UUID is generated.
3. An access token and a rotating refresh token are created.
4. The session is cached in Redis (with token hashes) for quick authentication checks.
5. The refresh and access tokens are returned as secure, HTTP-only cookies.

```mermaid
sequenceDiagram
    participant User as Client Browser
    participant API as FastAPI Router
    participant Service as AuthService
    participant Redis as Redis Cache
    participant DB as PostgreSQL DB

    User->>API: POST /auth/login (email, password)
    API->>Service: authenticate_user()
    Service->>DB: Query User by email
    DB-->>Service: User Record (password_hash)
    Service->>Service: Verify bcrypt hash
    
    rect rgb(240, 248, 255)
        Note over Service, Redis: Token Generation & Session Cache
        Service->>Service: Create access_token & refresh_token
        Service->>Redis: Set session:<hash> (expires in 30 days)
    end

    Service-->>API: User details + Tokens
    API->>User: Set Cookies: access_token, refresh_token (HttpOnly, Lax)
    API-->>User: JSON: UserMetadata + access_token
```

---

## 2. Refresh Token Rotation Flow

To mitigate the risk of token theft, refresh tokens are rotated during each refresh:
1. Client requests a token refresh at `/auth/refresh` (cookie containing `refresh_token` sent automatically).
2. Backend decodes the token, hashes it, and queries the database session cache.
3. If valid, the old session is deleted, a new token pair is generated, cached in Redis, and returned as cookies.
4. **Replay Detection**: If a reused refresh token is presented (not found in Redis but has a valid structure), the backend invalidates all active sessions for that user ID.

```mermaid
sequenceDiagram
    participant User as Client Browser
    participant API as FastAPI Router
    participant Service as SessionService
    participant Redis as Redis Cache

    User->>API: POST /auth/refresh (Cookie: refresh_token A)
    API->>Service: rotate_refresh_token(token A)
    Service->>Service: Hash token A
    Service->>Redis: GET session:<hashA>
    
    alt Session Valid (exists in Redis)
        Redis-->>Service: Session details
        Service->>Redis: DEL session:<hashA> (Revoke token A)
        Service->>Service: Generate access token + refresh token B
        Service->>Redis: SET session:<hashB> (Cache token B)
        Service-->>API: Token B
        API->>User: Set Cookies: refresh_token B, access_token B
    else Session Reused / Invalid (not in Redis)
        Service->>Service: Extract user_id from token A payload
        Service->>Redis: Scan & Delete all session keys for user_id
        Service-->>API: Raise InvalidRefreshTokenException
        API-->>User: 401 Unauthorized (Force logout from all devices)
    end
```

---

## 3. Consent Merging Flow

When an anonymous user signs in:
1. The frontend client triggers a request to fetch consent preferences, passing `anonymous_id`.
2. The backend merges the anonymous preference record directly to the new `user_id`.

```mermaid
sequenceDiagram
    participant Client as Next.js Client
    participant API as FastAPI Consent Route
    participant DB as PostgreSQL DB

    Client->>API: GET /consent/preferences?anonymous_id=anonId (Auth headers active)
    API->>DB: Query ConsentPreference where user_id == user.id
    
    alt User Preferences Exist
        DB-->>API: User Preferences
        API-->>Client: Preferences JSON
    else User Preferences Do Not Exist
        API->>DB: Query ConsentPreference where anonymous_id == anonId AND user_id IS NULL
        alt Anonymous Preferences Found
            DB-->>API: Anonymous Preference Record
            API->>DB: UPDATE ConsentPreference SET user_id = user.id
            API->>DB: INSERT ConsentAuditLog (action = merge_anonymous_to_user)
            API-->>Client: Updated Preference Record
        else No Preferences Found
            API-->>Client: Return null (Show Banner)
        end
    end
```
