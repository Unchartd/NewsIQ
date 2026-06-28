# NewsIQ Analytics Tracking Guide

This guide describes how to use the unified analytics library to instrument features in components.

## Basic Principles

1. **Never write analytics code directly inside UI components**. 
   - Always route calls through `analytics.track` or `analytics.pageView`.
   - Never reference `window.gtag` or `window.posthog` directly in UI components.
2. **Strict Type-Safety**:
   - The analytics service is fully typed. You cannot pass unregistered event names or incorrect parameters. This guarantees catalog consistency.
3. **No PII**:
   - Never pass emails, names, phone numbers, or tokens in event parameters. The analytics service automatically scrubs keys containing these terms, but developers must avoid dispatching them.

---

## Code Examples

### 1. Tracking custom user actions in client components

Import the `analytics` singleton and trigger events inside event callbacks:

```tsx
"use client";

import { analytics } from "@/lib/analytics/service";

export default function BookmarkButton({ storyId }) {
  const handleBookmark = () => {
    // Perform bookmark logic...
    
    analytics.track("story_bookmark", {
      story_id: storyId,
      action: "add"
    });
  };

  return <button onClick={handleBookmark}>Save</button>;
}
```

### 2. Identifying logged-in users

When a user logs in successfully or a session is restored, identify the user to tie page views and clicks together:

```typescript
import { analytics } from "@/lib/analytics/service";

// Inside auth initialization or login success
analytics.identify(user.id, {
  user_tier: user.role,
  subscription_status: user.subscription_plan
});
```

### 3. Cleaning user identity upon logout

Always reset user session parameters on logout to avoid attribution overlaps:

```typescript
import { analytics } from "@/lib/analytics/service";

// Inside logout action
analytics.reset();
```
