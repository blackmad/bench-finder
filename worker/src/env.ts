export interface Env {
  DB: D1Database;
  UPLOADS: R2Bucket;
  /** Firebase project id. Defaults to bench-finder-a45db. */
  FIREBASE_PROJECT_ID?: string;
  /** Comma-separated extra allowed CORS origins (the Pages origin). localhost:5173 is always allowed. */
  ALLOWED_ORIGINS?: string;
  /** Comma-separated Firebase uids allowed to use /api/admin/*. */
  ADMIN_UIDS?: string;
  /** Turnstile secret key (wrangler secret). Unset means anonymous submissions are refused. */
  TURNSTILE_SECRET?: string;
  /** Comma-separated hostnames Turnstile tokens may come from; defaults to ALLOWED_ORIGINS hosts. */
  TURNSTILE_HOSTNAMES?: string;
  /** DEV ONLY: JSON JWKS that replaces Google's keys for ID-token verification. Leave unset in production. */
  AUTH_TEST_JWKS?: string;
  /** Per-IP limits per hour; defaults in app.ts. */
  RATE_LIMIT_REPORTS_PER_HOUR?: string;
  RATE_LIMIT_UPLOADS_PER_HOUR?: string;
  RATE_LIMIT_COMMENTS_PER_HOUR?: string;
}

export const DEFAULT_FIREBASE_PROJECT_ID = "bench-finder-a45db";

export const csv = (v: string | undefined): string[] =>
  (v ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
