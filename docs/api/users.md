# Users & Accounts API Reference

All routes are prefixed with `/api/v1/users`.

---

## 1. Profiles & Onboarding

### A. Fetch User Profile
- **Endpoint**: `GET /profile`
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
    "created_at": "2026-06-19T11:27:00"
  }
  ```

### B. Update Profile Data
- **Endpoint**: `PATCH /profile`
- **Authentication**: Required (User role)
- **Request Body**:
  ```json
  {
    "name": "Jane Smith",
    "image_url": "https://newsite.com/image.png"
  }
  ```
- **Response** (200 OK): Updated user profile details.

### C. Complete Onboarding
- **Endpoint**: `POST /onboarding`
- **Authentication**: Required (User role)
- **Request Body**:
  ```json
  {
    "categories": ["politics", "technology"],
    "countries": ["US"],
    "cities": ["New York"],
    "preferred_summary_type": "short"
  }
  ```

### D. Delete Account (Right to Erasure)
- **Endpoint**: `DELETE /account`
- **Authentication**: Required (User role)
- **Behavior**: Implements GDPR Art. 17 (Right to be Forgotten). Scrubs personal identifiers (name, email, hashes) and deletes preferences, bookmarks, history, and active consent records.

---

## 2. Settings & Preferences

### A. Fetch User Preferences
- **Endpoint**: `GET /preferences`
- **Authentication**: Required (User role)

### B. Update User Preferences
- **Endpoint**: `PATCH /preferences`
- **Authentication**: Required (User role)
- **Request Body**:
  ```json
  {
    "preferred_summary_type": "short",
    "theme": "dark",
    "language": "en",
    "categories": ["technology", "business"],
    "countries": ["US", "IN"],
    "cities": ["Bengaluru"],
    "digest_settings": {},
    "ui_settings": {}
  }
  ```

---

## 3. Notifications & Reading History

### A. Fetch Notifications
- **Endpoint**: `GET /notifications`
- **Authentication**: Required (User role)

### B. Mark Notification as Read
- **Endpoint**: `PATCH /notifications/{notification_id}/read`
- **Authentication**: Required (User role)

### C. Mark All Notifications Read
- **Endpoint**: `PATCH /notifications/read-all`
- **Authentication**: Required (User role)

### D. Delete Notification
- **Endpoint**: `DELETE /notifications/{notification_id}`
- **Authentication**: Required (User role)

### E. Fetch Reading History
- **Endpoint**: `GET /history`
- **Authentication**: Required (User role)

### F. Delete History Item
- **Endpoint**: `DELETE /history/{event_id}`
- **Authentication**: Required (User role)

### G. Clear All Reading History
- **Endpoint**: `DELETE /history`
- **Authentication**: Required (User role)

---

## 4. Digest Subscriptions

### A. Fetch Digest Subscriptions
- **Endpoint**: `GET /digests`
- **Authentication**: Required (User role)

### B. Update Digest Subscriptions
- **Endpoint**: `PATCH /digests`
- **Authentication**: Required (User role)
- **Request Body**:
  ```json
  {
    "frequency": "daily",
    "delivery_channel": "email",
    "enabled": true
  }
  ```

### C. Onboarding Setup Digest
- **Endpoint**: `POST /digests/setup`
- **Authentication**: Required (User role)

### D. Cancel All Digests
- **Endpoint**: `DELETE /digests/unsubscribe`
- **Authentication**: Required (User role)

### E. Get Latest Digest
- **Endpoint**: `GET /digests/latest`
- **Authentication**: Required (User role)

### F. Trigger Delivery (Manual Dispatch)
- **Endpoint**: `POST /digests/trigger-delivery`
- **Authentication**: Required (User role)
- **Request Body**:
  ```json
  {
    "frequency": "daily"
  }
  ```

---

## 5. Analytics & Subscriptions

### A. Track Analytics Event
- **Endpoint**: `POST /events`
- **Authentication**: Required (User role)
- **Query Parameters**: `event_type=view_story&story_id=STORY_UUID`

### B. Upgrade Subscription Plan (Pro)
- **Endpoint**: `POST /subscription/upgrade`
- **Authentication**: Required (User role)

### C. Cancel Subscription (Downgrade to Free)
- **Endpoint**: `POST /subscription/cancel`
- **Authentication**: Required (User role)

### D. Export Personal Data (GDPR Data Portability)
- **Endpoint**: `GET /export-data`
- **Authentication**: Required (User role)
- **Response**: Triggers download of user profile, preferences, bookmarks, history, and notification logs in a JSON format.

### E. Clear Personalisation Data
- **Endpoint**: `POST /clear-personalisation`
- **Authentication**: Required (User role)
- **Behavior**: Wipes reading and search history and resets personalization toggles.
