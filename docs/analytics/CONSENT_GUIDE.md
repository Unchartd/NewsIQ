# GA4 Consent Mode v2 Integration Reference

NewsIQ complies with GDPR, UK Data Protection Act, and California's CCPA/CPRA using Google Consent Mode v2 (Advanced Implementation).

---

## 1. How Advanced Consent Mode Works

Rather than completely blocking the injection of Google Analytics tags when a visitor rejects analytics cookies, Google Consent Mode v2 loads the `gtag` script but blocks its cookie-writing capabilities.

- When consent is **granted**, GA4 sets cookies (`_ga`, `_gid`) and tracks sessions normally.
- When consent is **denied**, GA4 operates in cookieless mode. It transmits metadata pings (such as timestamps, user agents, referrers) to Google servers without setting cookies. Google uses these pings to perform AI-based behavioral and conversion modeling, recovering up to 70% of lost session volume metrics.

---

## 2. Technical Implementation

1. **Root Script Default Settings**:
   The defaults are injected in `<head>` in [layout.tsx](file:///c:/Users/zakau/NewsIQ/apps/web/src/app/layout.tsx) before any other script tags are executed.
   ```javascript
   gtag('consent', 'default', {
     'ad_storage': 'denied',
     'ad_user_data': 'denied',
     'ad_personalization': 'denied',
     'analytics_storage': 'denied',
     'functionality_storage': 'denied',
     'personalization_storage': 'denied',
     'security_storage': 'granted',
     'wait_for_update': 500
   });
   ```

2. **Dynamically Updating Consent**:
   When consent preferences are resolved or updated, the consent provider updates Gtag in [consent-provider.tsx](file:///c:/Users/zakau/NewsIQ/apps/web/src/components/legal/consent-provider.tsx):
   ```javascript
   gtag('consent', 'update', {
     'analytics_storage': analyticsGranted ? 'granted' : 'denied',
     'ad_storage': marketingGranted ? 'granted' : 'denied',
     'ad_user_data': marketingGranted ? 'granted' : 'denied',
     'ad_personalization': marketingGranted ? 'granted' : 'denied'
   });
   ```

3. **Storage Mechanism**:
   Active preferences are saved in `localStorage` under key `niq_consent_preferences` as a JSON object. The unified analytics dispatcher uses this to filter third-party tracking calls (such as PostHog).
