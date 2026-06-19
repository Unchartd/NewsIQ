# NewsIQ Security & Consent Architecture Review

**Author**: Principal Privacy Engineer & GDPR Compliance Architect  
**Date**: June 19, 2026  
**Document Version**: 2.0  
**Target Platform**: NewsIQ AI News Intelligence Platform  

---

## 1. Executive Summary

This Security Review details the evaluation of the security controls implemented in NewsIQ's production-ready codebase, with a specific focus on the newly integrated Consent Management Platform (CMP). Based on a deep audit of the FastAPI backend and Next.js frontend, we have verified that the platform utilizes industry-standard defensive security designs. All core security features are fully implemented, verified via backend tests, and aligned with international privacy guidelines.

---

## 2. Verified Security Controls

### A. Network & Session Security
1. **HTTPS Enforcement**: 
   - HSTS (HTTP Strict Transport Security) is enforced via security header middleware, instructing browsers to interact exclusively over HTTPS.
2. **CORS Configuration**: 
   - `CORSMiddleware` is configured in `app/main.py` to allow requests only from verified origins (e.g., `localhost:3000` and the canonical domain `https://newsiq.ai`), blocking cross-origin resource leakage.
3. **Session Management (Redis)**: 
   - Temporary session states and tokens are managed using a secure Redis database cache on the server.
   - Session identifiers expire automatically after user inactivity, reducing session hijacking risk.
4. **CSRF Protection**: 
   - Custom CSRF middleware validates request origin and referer headers for all state-changing operations (POST, PUT, PATCH, DELETE) against allowed origins, protecting against Cross-Site Request Forgery attacks.

### B. Cookie Security Parameters
All session cookies are configured with maximum defensive attributes:
- **`HttpOnly`**: Set to `True` for both `access_token` and `refresh_token` cookies. This blocks client-side JavaScript access to raw session tokens, effectively neutralizing session theft via Cross-Site Scripting (XSS) vulnerabilities.
- **`Secure`**: Set to `True` in production (`secure=not settings.DEBUG`). This forces the browser to transmit authentication cookies exclusively over encrypted SSL/TLS (HTTPS) channels.
- **`SameSite=Lax`**: Balances security and user experience. It ensures cookies are withheld from third-party sites during cross-origin requests (preventing CSRF) but allows them to be sent during top-level navigations (e.g., clicking a link to NewsIQ in an email newsletter), preventing users from being logged out on arrival.

### C. Token Rotation & Replay Protection
- **Rotating Refresh Tokens**: Each call to `/api/v1/auth/refresh` rotates the refresh token. The old refresh token is immediately deleted and replaced with a newly issued token.
- **Token Reuse/Theft Detection**: If a client attempts to reuse an old refresh token, the backend session service detects the double-use anomaly. As a defensive countermeasure, it **revokes all active sessions** for that user ID, forcing all devices to re-authenticate. This mitigates token theft and replay attacks.
- **In-Memory Access Tokens**: On the client, the `access_token` is held strictly in-memory (inside modular JS memory). This prevents persistent access tokens from being extracted from local storage or session storage via XSS.

### D. GDPR Data Minimization: Salted IP Hashing
Under GDPR Article 5(1)(c) (Data Minimization) and Article 32 (Security of Processing), raw IP addresses should not be stored in audit logs if they can be avoided.
- To prove consent legally (GDPR Art 7) while maintaining user anonymity:
  - The CMP hashes the client's IP address: `ip_hash = SHA256(client_ip + SECRET_KEY)`.
  - The cryptographic salt (`SECRET_KEY`) is stored securely on the server.
  - This hash is one-way (irreversible), making it impossible for attackers to recover raw IP addresses from audit log tables, while still allowing the system to verify if a given IP was used to perform an action by re-hashing it for audit validation.

### E. Rate Limiting & Denial of Service (DoS)
- **Redis Rate Limiter**: 
   - Dedicated `RateLimitMiddleware` is configured in `app/core/rate_limiter.py` and mounted in `app/main.py`.
   - Restricts API requests to a fixed-window counter of **100 requests per 60 seconds** per client IP, preventing brute-force attacks, scraping abuse, and denial-of-service attempts.

### F. Input Validation & Defense
- **Pydantic Schemas**: 
   - Every API request body is parsed and validated using Pydantic schemas, blocking SQL injection, buffer overflows, and type coercion exploits.
- **Security Headers**: 
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
