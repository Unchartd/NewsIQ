# Privacy & Regulatory Compliance Matrix

NewsIQ is built with **Privacy-by-Design** and **Privacy-by-Default** at its core. This document outlines how our Consent Management Platform (CMP) meets the strict compliance guidelines of the **General Data Protection Regulation (GDPR)**, **UK GDPR**, California's **CCPA / CPRA**, and India's **Digital Personal Data Protection Act (DPDPA) 2023**.

---

## 1. Compliance Mapping by Regulation

### A. GDPR & UK GDPR (Europe / United Kingdom)
- **Legal Basis**: Consent under **Art. 6(1)(a)** is required for reading or storing non-essential cookies.
- **Opt-In Mandate**: All non-essential categories (Functional, Analytics, Marketing) are **disabled by default**. No scripts are loaded prior to affirmative user action.
- **Consent Granularization**: Users must be able to accept some categories and reject others. The Cookie Preferences Modal allows independent toggles for Functional, Analytics, and Marketing.
- **Proof of Consent**: Under **Art. 7(1)**, the platform records every consent change in `consent_audit_logs`. The log contains the action type, old values, new values, a salted IP hash, and the timestamp.
- **Easy Withdrawal**: Under **Art. 7(3)**, consent withdrawal must be as easy as giving it. Users can click "Withdraw Consent" on Settings $\rightarrow$ Privacy or reset preferences at any time, which immediately halts script injection and reloads the browser to purge loaded trackers from active memory.

### B. CCPA / CPRA (California, USA)
- **Legal Basis**: Right to Opt-Out of the "Sale" or "Sharing" of personal information for cross-context behavioral advertising.
- **Opt-Out Design**: California residents default to having cookies enabled on their first visit, but the Cookie Banner displays a regional-specific header ("US / CA Rights") and a direct option to opt out of non-essential cookies ("Reject Non-Essential") or customize settings.
- **Do Not Sell/Share My Info**: The footer and privacy page contain triggers that open the Cookie Preferences Modal instantly, allowing users to exercise their CCPA opt-out rights.

### C. DPDPA 2023 (India)
- **Legal Basis**: Notice-based explicit consent for specified purposes.
- **Opt-In Mandate**: Functional, analytics, and marketing tracking are **disabled by default** for Indian users.
- **Right to Withdraw**: Clear, accessible settings are provided for Indian residents in Settings $\rightarrow$ Privacy to withdraw consent at any time.
- **Audit Trails**: Detailed logs verify compliance with DPDPA storage and processing limits.

---

## 2. Cookie Classification Rules

| Category | Description | Examples | Third-Party Involved? | Consent Required? | Default (EU / UK / IN) | Default (CA) | Default (ROW) |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Essential** | Core security, CSRF protection, and session authentication. | `access_token`, `refresh_token`, `niq_cookie_consent` | No | **No** | **Enabled** (Locked) | **Enabled** (Locked) | **Enabled** (Locked) |
| **Functional** | UI customizations, sidebar layouts, and AI summary preferences. | `theme`, `newsiq-ui` | No | **Yes** | **Disabled** | **Enabled** | **Enabled** |
| **Analytics** | Engagement tracking, site speed metrics, and feature metrics. | `_ga` (Google), `ph_` (PostHog) | Yes | **Yes** | **Disabled** | **Enabled** | **Enabled** |
| **Marketing** | Retargeting campaigns, ad conversions, and profile matching. | `_fbp` (Meta), `LinkedIn Insight` | Yes | **Yes** | **Disabled** | **Enabled** | **Disabled** |

---

## 3. Data Protection & Security Controls

### A. GDPR-Compliant IP Anonymization
To avoid storing raw IP addresses (which are considered Personal Data / PII under GDPR) while maintaining valid audit logs, the backend applies a cryptographic salt-and-hash:
- `ip_hash = SHA256(client_ip + SECRET_KEY)`
- The salt (`SECRET_KEY`) is stored securely in environment variables and never exposed.
- This creates an irreversible signature. We can verify if a specific IP consented by re-hashing it, but we cannot reconstruct the IP from the hash.

### B. Account Deletion & Right to Be Forgotten (Art. 17 GDPR)
When a user deletes their account (`DELETE /api/v1/users/account`):
1. **PII Scrubbing**: The user's name, email, and password hashes are deleted or replaced with randomized anonymized strings.
2. **Linked Records**: All active preferences are cascadingly deleted.
3. **Audit Log Anonymization**: The system keeps the `ConsentAuditLog` records for legal defense and tax audit purposes but **anonymizes them** by setting `user_id = NULL` and removing any linkable metadata. The log remains valid for verifying historical actions without containing any direct identifiers.

### C. Cookie Flag Security
All session cookies are set with:
- `HttpOnly=True`: Prevents client-side scripts from reading the tokens, mitigating XSS attacks.
- `Secure=True` (in production): Forces browsers to send tokens only over encrypted HTTPS connections.
- `SameSite=Lax`: Standard cookie-sharing rule, protecting against CSRF attacks while maintaining a smooth UX when navigating to the site from external links.
- `Rotation`: Session refresh rotates refresh tokens and invalidates the old token immediately to detect token reuse or hijacking.
