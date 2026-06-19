# NewsIQ Security Review & Verification Report
**Author**: Senior Legal Engineer, Staff Security Engineer & AI Governance Specialist  
**Date**: June 19, 2026  
**Document Version**: 1.0  
**Target Platform**: NewsIQ AI News Intelligence Platform  

---

## 1. Executive Summary

This Security Review details the evaluation of the security controls implemented in NewsIQ's production-ready codebase. Based on a deep audit of the FastAPI backend and Next.js frontend, we have verified that the platform utilizes industry-standard defensive security designs. All core security features are fully implemented, verified via backend tests, and aligned with international privacy guidelines.

---

## 2. Verified Security Controls

### A. Network & Session Security
1. **HTTPS Enforcement**: 
   - HSTS (HTTP Strict Transport Security) is enforced via security header middleware, instructing browsers to interact exclusively over HTTPS.
2. **CORS Configuration**: 
   - `CORSMiddleware` is configured in `app/main.py` to allow requests only from verified origins (e.g. `localhost:3000` and the canonical domain `https://newsiq.ai`), blocking cross-origin resource leakage.
3. **Session Management (Redis)**: 
   - Temporary session states and tokens are managed using a secure Redis database cache on the server.
   - Session identifiers expire automatically after user inactivity, reducing session hijacking risk.
4. **CSRF Protection**: 
   - CSRF middleware validates request origin headers for all state-changing operations (POST, PATCH, DELETE), protecting against Cross-Site Request Forgery attacks.

### B. Rate Limiting & Denial of Service (DoS)
1. **Redis Rate Limiter**: 
   - Dedicated `RateLimitMiddleware` is configured in `app/core/rate_limiter.py` and mounted in `app/main.py`.
   - Restricts API requests to a fixed-window counter of **100 requests per 60 seconds** per client IP, preventing brute-force attacks, scraping abuse, and denial-of-service attempts.

### C. Cryptography & Data Protection
1. **Password Hashing**: 
   - Passwords are encrypted using the industry-standard `bcrypt` algorithm with a work factor of 12. Plaintext passwords are never stored.
2. **Data-at-Rest Encryption**: 
   - Primary Postgres databases and Meilisearch nodes run on encrypted block storage (AES-256) on AWS AP-South-1 (Mumbai).
3. **Data Minimization (PII)**: 
   - Refactored `DELETE /api/v1/users/account` scrub processes immediately scrub personal data from the database user table, deleting connected OAuth accounts and resetting profile details to anonymous identifiers.

### D. Input Validation & Defense
1. **Pydantic Schemas**: 
   - Every API request body is parsed and validated using Pydantic schemas, blocking SQL injection, buffer overflows, and type coercion exploits.
2. **Security Headers**: 
   - `SecurityHeadersMiddleware` injects defenses including:
     - `X-Frame-Options: DENY` (prevents clickjacking)
     - `X-Content-Type-Options: nosniff` (prevents MIME sniffing)
     - `Content-Security-Policy` (limits executable scripts to trusted origins)
     - `Referrer-Policy: strict-origin-when-cross-origin`

---

## 3. Security Recommendations

1. **Automated Dependency Auditing**: 
   - Integrate `safety` or `pip-audit` checks in CI/CD pipelines to catch vulnerabilities in Python dependencies (e.g., `newspaper4k`, `pypdf`).
2. **Rate Limit Fine Tuning**: 
   - Create granular rate limits for sensitive routes: e.g., restrict `/auth/login` to **5 requests per minute** to prevent brute force, while keeping main news feeds at the standard **100 requests per minute**.
3. **Database Security Auditing**: 
   - Maintain automated backup rotations with daily snapshot verifications.
