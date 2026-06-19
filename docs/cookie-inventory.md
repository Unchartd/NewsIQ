# NewsIQ Cookie & Storage Inventory

This document provides a comprehensive inventory of all cookies, local storage, and server-side session caching mechanisms used across the NewsIQ platform. 

NewsIQ operates on **privacy-by-default** principles, ensuring no non-essential tracking is loaded without the user's explicit consent.

---

## 1. Essential Storage Mechanisms (Strictly Necessary)

These cookies and storage items are strictly necessary for core platform security, authentication, and state management. They cannot be turned off, and consent is not required under GDPR Art 6(1)(f) and DPDPA 2023.

| Key / Name | Storage Type | Domain / Scope | Purpose | Retention | Third-Party | Consent Required |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| `access_token` | Cookie (HttpOnly, Secure, SameSite=Lax) | Backend API | Temporary JWT session token used to authorize requests. | 15 minutes | No | **No** |
| `refresh_token` | Cookie (HttpOnly, Secure, SameSite=Lax) | Backend API | Rotating token to securely generate new access tokens without requiring user re-authentication. | 30 days | No | **No** |
| `newsiq-auth` | LocalStorage (Zustand Persist) | Client (Browser) | Keeps basic user state (id, email, name, role) in memory to avoid UI flashing during page transitions. | Persistent | No | **No** |
| `resend_cooldown` | LocalStorage | Client (Browser) | Restricts resending verification emails to prevent spam and rate-limit abuse. | 60 seconds | No | **No** |
| `niq_cookie_consent` | LocalStorage | Client (Browser) | Stores the user's granular cookie preferences (essential, functional, analytics, marketing) and policy version. | 1 year | No | **No** |
| `session_cache` | Redis Server-Side | Server RAM | Maps active `refresh_token` hashes to valid sessions to enable secure server-side revocation (session rotation). | 30 days | No | **No** |

---

## 2. Functional Storage Mechanisms

These cookies and storage items remember layout settings, interface themes, and preferences to provide a personalized user experience. Users can opt out of these.

| Key / Name | Storage Type | Domain / Scope | Purpose | Retention | Third-Party | Consent Required | Default State |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `newsiq-ui` | LocalStorage (Zustand Persist) | Client (Browser) | Persists user UI settings: sidebar open state (`sidebarOpen`), preferred AI summary depth (`preferredSummary`), and active filters (`activeCategory`, `activeCountry`, etc.). | Persistent | No | **Yes** | Opt-In (EU/UK) / Opt-Out (CA/ROW) |
| `theme` | LocalStorage | Client (Browser) | Saves the user's dark/light/system mode selection for `next-themes`. | Persistent | No | **Yes** | Opt-In (EU/UK) / Opt-Out (CA/ROW) |
| `next-theme` | LocalStorage | Client (Browser) | Alternate token for visual styling configuration. | Persistent | No | **Yes** | Opt-In (EU/UK) / Opt-Out (CA/ROW) |

---

## 3. Analytics Cookies

Analytics mechanisms collect telemetry to monitor system load, analyze click-through rates, optimize summary pipelines, and measure engagement. They are disabled by default for EU, UK, and Indian users.

| Key / Name | Storage Type | Domain / Scope | Purpose | Retention | Third-Party | Consent Required | Default State |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `_ga` | Cookie | Client (Browser) | Google Analytics: Tracks traffic sources, visitor counts, and page views. | 2 years | Yes (Google) | **Yes** | **Disabled (Opt-In Required)** |
| `_gid` | Cookie | Client (Browser) | Google Analytics: Distinguishes users on a rolling 24-hour basis. | 24 hours | Yes (Google) | **Yes** | **Disabled (Opt-In Required)** |
| `ph_<project_token>_user` | LocalStorage / Cookie | Client (Browser) | PostHog: Stores user engagement sessions, features used, and API request durations. | 1 year | Yes (PostHog) | **Yes** | **Disabled (Opt-In Required)** |

---

## 4. Marketing Cookies

Marketing pixels track ad conversions, optimize campaigns, and target relevant ads. They are strictly opt-in and disabled by default everywhere.

| Key / Name | Storage Type | Domain / Scope | Purpose | Retention | Third-Party | Consent Required | Default State |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `_fbp` | Cookie | Client (Browser) | Meta Pixel: Measures conversion rates for marketing campaigns on Facebook. | 90 days | Yes (Meta) | **Yes** | **Disabled (Opt-In Required)** |
| `UserMatchHistory` | Cookie | Client (Browser) | LinkedIn Insight Tag: Tracks ad clicks and profile interactions. | 30 days | Yes (LinkedIn) | **Yes** | **Disabled (Opt-In Required)** |
| `_gcl_au` | Cookie | Client (Browser) | Google Ads: Stores ad clicks to attribute conversions. | 90 days | Yes (Google) | **Yes** | **Disabled (Opt-In Required)** |

---

## 5. Cookie Inventory Policy Compliance Matrix

| Regulation | Region | Default Analytics | Default Marketing | Explicit Opt-In | Opt-Out Link |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **GDPR / UK GDPR** | European Union / UK | **Disabled** | **Disabled** | **Yes** (Prior to load) | Yes (Withdrawal settings) |
| **DPDPA 2023** | India | **Disabled** | **Disabled** | **Yes** (Notice provided) | Yes (Withdrawal settings) |
| **CCPA / CPRA** | California, USA | **Enabled** | **Enabled** | No (Opt-Out) | **Yes** (Do Not Sell/Share) |
| **Rest of World** | Other regions | **Enabled** | **Disabled** | No (Opt-Out) | Yes (Cookie settings) |
