# NewsIQ Legal Implementation Checklist
**Author**: Senior Legal Engineer, Staff Privacy Engineer & AI Governance Specialist  
**Date**: June 19, 2026  
**Document Version**: 1.0  

---

## 1. Status Overview

We have successfully audited the 14 source policies, normalized their terms, unified the Next.js frontend pages, injected AI disclaimers, and refactored backend GDPR/DPDPA data deletion endpoints. 

### A. Completed Features & Changes
* [x] **Legal Audit**: Performed and saved to [legal-audit.md](file:///c:/Users/zakau/NewsIQ/docs/legal-audit.md).
* [x] **Policy Normalization**: Completed master consolidation and saved to [normalized-content.ts](file:///c:/Users/zakau/NewsIQ/apps/web/src/app/(legal)/normalized-content.ts). Standardized domains, effective dates, and contact channels.
* [x] **Unified Legal Page**: Built `/legal` route with sidebar navigation, table of contents anchors, keyword search filter, and mobile drawer.
* [x] **Compatibility Redirects**: Configured existing `/privacy` and `/tos` pages to redirect to `/legal` with pre-selected query parameters.
* [x] **PII Scrubbing on Account Deletion**: Refactored backend `DELETE /users/account` route in `users.py` to completely anonymize user email/name and clear password hashes and OAuth details.
* [x] **Cookie Consent Control**: Added global `CookieBanner` and `CookieModal` components to manage user cookie consents.
* [x] **Compliance Forms**: Integrated self-service forms for DMCA notices, Privacy Requests (Access/Portability/Correction/Nomination), AUP Abuse reporting, and legal contact inquiries directly in the unified Legal Center page.
* [x] **AI Transparency Notices**: Injected notices on story pages detailing AI's probabilistic nature underneath both main summaries and difference engine panels.
* [x] **Attribution & Publisher Logos**: Integrated logo rendering in the source coverage and original article links sections.
* [x] **Security Review**: Completed audit and saved to [security-review.md](file:///c:/Users/zakau/NewsIQ/docs/security-review.md).

---

## 2. Integration Details & Action Items

### A. Needs Backend Support (Future Scope)
* **Email integration**: Hook up submitted form requests (DMCA, Privacy, Abuse, Legal Contact) to send email notifications directly to `legal@newsiq.ai` or `privacy@newsiq.ai` via the transaction mail provider (Postmark) rather than just popping successful client toasts.
* **Consent Database logs**: Store user cookie settings in the UserPreference database table rather than relying solely on client-side `localStorage`, to support cross-device cookie sync.

### B. Needs UI Support
* **Publisher Logos Collection**: Ensure that incoming news crawlers extract and populate the `logo_url` field for news sources in the database, allowing logos to render instead of the default colored dots.

### C. Needs Legal Review
* **Fair Use Validation**: Have legal counsel verify the fair use/fair dealing disclaimers regarding NewsIQ's Difference Engine output in the localized Indian context.
* **Consent Manager Verification**: Monitor regulatory guidance from the Data Protection Board of India (DPBI) to configure API integrations for registered DPDPA Consent Managers when statutory APIs are released.

---

## 3. Potential Risks & Mitigation

| Identified Risk | Mitigation Strategy | Status |
| :--- | :--- | :---: |
| **Card Network Chargebacks**: Users disputing recurring subscription fees due to pricing changes or subscription structures. | Standardized pricing communications to require 30-day advance emails and unified terms in both TOS and Subscription Policy. | **Mitigated** |
| **Scraper Scraping**: Competitors scraping NewsIQ's aggregated summaries for competing products. | Strengthened anti-scraping language in consolidated Terms of Service and AUP, backed by active Redis rate-limiting (100 req/min). | **Mitigated** |
| **AI Inaccuracy Claims**: Users taking legal or financial action based on hallucinated AI summaries or difference engine reports. | Placed noticeable AI transparency disclaimers beneath summaries and comparison blocks, establishing that outputs are purely informational. | **Mitigated** |
