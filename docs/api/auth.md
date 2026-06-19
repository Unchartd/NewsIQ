# Authentication & OAuth API Reference

All routes are prefixed with `/api/v1/auth`.

---

## 1. Local Credentials Authentication

### A. Register Account
- **Endpoint**: `POST /register`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "name": "Jane Doe",
    "password": "SecurePassword123!",
    "confirm_password": "SecurePassword123!"
  }
  ```
- **Response** (201 Created):
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "user": {
      "id": "01982e1c-6e93-75f4-80db-95a5f6d1e2b7",
      "email": "user@example.com",
      "name": "Jane Doe",
      "role": "user",
      "subscription_plan": "free"
    }
  }
  ```
- **Cookies Set**:
  - `access_token` (HttpOnly, Secure, Lax)
  - `refresh_token` (HttpOnly, Secure, Lax, 30 days expiry)

### B. Login Credentials
- **Endpoint**: `POST /login`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Response** (200 OK): Same schema as Register.
- **Lockout Rule**: 5 failed login attempts lock the account for 15 minutes.

### C. Refresh Access Token
- **Endpoint**: `POST /refresh`
- **Headers**: Automatically transmits the `refresh_token` cookie.
- **Response** (200 OK):
  ```json
  {
    "access_token": "eyJhbGciOi..."
  }
  ```
- **Behavior**: Rotates the `refresh_token` cookie automatically. Reusing an old refresh token invalidates all user sessions.

### D. Logout Session
- **Endpoint**: `POST /logout`
- **Behavior**: Revokes the active session from Redis and deletes the browser `access_token` and `refresh_token` cookies.

### E. Logout All Devices
- **Endpoint**: `POST /logout-all`
- **Authentication**: Required (User role)
- **Behavior**: Revokes all cached sessions in Redis for the active user ID.

### F. Fetch Current User Details
- **Endpoint**: `GET /me`
- **Authentication**: Required (User role)
- **Response** (200 OK):
  ```json
  {
    "id": "01982e1c-6e93-75f4-80db-95a5f6d1e2b7",
    "email": "user@example.com",
    "name": "Jane Doe",
    "image_url": null,
    "role": "user",
    "subscription_plan": "free",
    "status": "active",
    "email_verified": true,
    "created_at": "2026-06-19T11:27:00"
  }
  ```

---

## 2. Google OAuth Integration

### A. Initialize OAuth Flow
- **Endpoint**: `GET /google`
- **Response**:
  ```json
  {
    "redirect_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=..."
  }
  ```

### B. OAuth Callback Handler
- **Endpoint**: `GET /google/callback`
- **Query Parameters**: `code=AUTHORIZATION_CODE`
- **Behavior**: Exchanges authorization code for Google user details. Creates a new user record or logs in an existing one, sets refresh token cookies, and redirects the browser back to:
  `https://newsiq.ai/auth/callback?access_token=<JWT_ACCESS_TOKEN>`

---

## 3. Account Reset & Verification Workflows

### A. Email Verification Action
- **Endpoint**: `POST /verify-email`
- **Query Parameters**: `token=VERIFICATION_TOKEN`
- **Response** (200 OK):
  ```json
  {
    "message": "Email verified successfully."
  }
  ```

### B. Resend Email Verification
- **Endpoint**: `POST /resend-verification`
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```

### C. Forgot Password Link
- **Endpoint**: `POST /forgot-password`
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```

### D. Verify Reset Token
- **Endpoint**: `POST /verify-reset-token`
- **Query Parameters**: `token=RESET_TOKEN`
- **Response** (200 OK):
  ```json
  {
    "message": "Token is valid."
  }
  ```

### E. Reset Password Action
- **Endpoint**: `POST /reset-password`
- **Request Body**:
  ```json
  {
    "token": "reset_token_from_email",
    "new_password": "NewSecurePassword123!"
  }
  ```

---

## 4. Session & Password Management

### A. List Active Sessions
- **Endpoint**: `GET /sessions`
- **Authentication**: Required (User role)
- **Response** (200 OK):
  ```json
  [
    {
      "id": "01982e1c-6e93-75f4-80db-95a5f6d1e2b7",
      "device_name": "Chrome on Windows",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "last_used_at": "2026-06-19T11:27:00",
      "created_at": "2026-06-19T11:27:00",
      "expires_at": "2026-07-19T11:27:00",
      "is_current": true
    }
  ]
  ```

### B. Revoke Specific Session
- **Endpoint**: `DELETE /sessions/{session_id}`
- **Authentication**: Required (User role)

### C. Change Account Password
- **Endpoint**: `POST /change-password`
- **Authentication**: Required (User role)
- **Request Body**:
  ```json
  {
    "current_password": "OldSecurePassword123!",
    "new_password": "NewSecurePassword123!"
  }
  ```
