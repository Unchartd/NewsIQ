/**
 * In-memory access token store.
 *
 * The access token is deliberately kept ONLY in module memory (never in
 * localStorage/sessionStorage) to prevent token theft via XSS. The long-lived
 * refresh token lives in an HTTP-only cookie managed by the backend; on a full
 * page reload the token is transparently re-obtained via /auth/refresh.
 */

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
