# Bench Finder Worker

Cloudflare Worker (Hono, TypeScript) serving the `/api/*` **writes** for the bench site: ratings, visited/favorite, comments, reports, report-photo uploads, and moderation. Bench data itself is static files in R2 and never goes through this worker. Data lives in D1 (user-generated rows only); bench ids are the integer `bench_candidates.id`.

## Routes

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/api/health` | none | |
| GET | `/api/bench/:id/social` | optional | rating summary, comments (`mine` flag), and `me` (`rating`, `visited`, `favorite`) when signed in. A bad token is 401, not anonymous. |
| PUT | `/api/bench/:id/rating` | user | `{rating: 1..5}`, upsert |
| PUT | `/api/bench/:id/status` | user | `{visited?, favorite?}`, partial update |
| POST | `/api/bench/:id/comments` | user | `{body}` 1..2000 chars, 20/hour/user |
| DELETE | `/api/comments/:id` | user | soft delete, author only |
| POST | `/api/comments/:id/flag` | user | queues a comment for moderation (stays visible) |
| GET | `/api/me` | user | `{uid, isAdmin, ratings, visited[], favorites[]}` |
| POST | `/api/reports/bench` | anon + Turnstile | `{benchId, reason, note?, photoKey?, turnstileToken?}` |
| POST | `/api/reports/missing` | anon + Turnstile | `{lat, lng, accuracyMeters?, note?, photoKey?, turnstileToken?}` |
| POST | `/api/uploads` | anon + Turnstile | raw image body, `Content-Type` image/jpeg, png or webp, max 5 MB; returns `{key}` |
| GET | `/api/admin/reports?status=pending` | admin | `{bench[], missing[]}` |
| POST | `/api/admin/reports/:kind/:id/:action` | admin | kind `bench`\|`missing`, action `resolve`\|`dismiss`, optional `{adminNotes}` |
| GET | `/api/admin/comments?state=flagged` | admin | |
| POST | `/api/admin/comments/:id/:action` | admin | `hide`\|`approve` |
| GET | `/api/admin/photos/:name` | admin | streams a report photo from R2 (fetch with the auth header, use a blob URL) |

Errors are `{"error": "..."}`. Report reasons: `not_a_bench`, `wrong_location`, `wrong_facing`, `bad_image`, `other`.

Frontend typed client: `import type { AppType } from "../../worker/src/index"; const api = hc<AppType>(base)` (`hono/client`).

## Design notes

- **Auth**: Firebase ID tokens verified with `jose` against Google's securetoken JWKS (cached by `createRemoteJWKSet`); checks issuer `https://securetoken.google.com/<project>`, audience, `exp`, `sub`, RS256 only. No service account. The JWKS source is injectable (`createApp({ jwks })`) so tests sign with a local key.
- **Anonymous writes**: per-IP rate limit first (default 10/hour for reports and for uploads, bucketed separately), then Turnstile verification. Signed-in users skip Turnstile but are still rate limited. If `TURNSTILE_SECRET` is unset, anonymous writes are refused (fail closed). The token goes in the body (`turnstileToken`) or the `X-Turnstile-Token` header. Turnstile tokens are single use, so an anonymous photo report needs two widget runs (one for the upload, one for the report).
- **Rate limit**: a D1-backed fixed-window counter (`src/rate-limit.ts`), not the Workers Rate Limiting binding. Reason: deterministic in tests, nothing extra to configure. Cost is one D1 write per limited request; a fixed window can allow up to 2x the limit across a boundary. Keys contain the client IP and are purged after a day; IPs are not stored on reports.
- **Comments** are published immediately; `state` is `visible`, `flagged` (still visible, in the admin queue) or `hidden` (moderator). Author deletion sets `deleted_at`.
- **Uploads** are checked by declared type, magic bytes and size, stored under `reports/<uuid>.<ext>` in a private bucket, and only attachable to a report if the key exists.

## Local development

```sh
cd worker
npm install
npm run dev        # wrangler dev, local D1/R2 simulated by miniflare
```

Apply the schema to the local D1 (once, and after new migrations):

```sh
npx wrangler d1 migrations apply bench-finder --local
```

Create `worker/.dev.vars` (git-ignored) for local secrets. Cloudflare's published always-pass Turnstile test secret works locally:

```
TURNSTILE_SECRET=1x0000000000000000000000000000000AA
ADMIN_UIDS=<your firebase uid>
```

The frontend dev server (`localhost:5173`) is always an allowed CORS origin.

## Tests

```sh
npm test            # vitest, runs inside workerd via @cloudflare/vitest-plugin (miniflare)
npm run typecheck   # tsc --noEmit
```

Note: `@cloudflare/vitest-pool-workers` is deprecated in favour of `@cloudflare/vitest-plugin`, which this package uses. If `npm install` skips build scripts, run `npm rebuild workerd esbuild`.

## Owner steps to deploy (later; needs a Cloudflare account)

1. `npx wrangler login`
2. Create D1: `npx wrangler d1 create bench-finder`, then paste the printed `database_id` into `wrangler.jsonc` (replace the all-zeros TODO).
3. Create the private uploads bucket: `npx wrangler r2 bucket create bench-finder-uploads` (or change `bucket_name` in `wrangler.jsonc`).
4. Apply migrations remotely: `npx wrangler d1 migrations apply bench-finder --remote`
5. Create a Turnstile widget in the Cloudflare dashboard (Turnstile), put its **site key** in the frontend, and store the **secret**: `npx wrangler secret put TURNSTILE_SECRET`
6. Edit `wrangler.jsonc` vars: `ALLOWED_ORIGINS` (the Pages origin, e.g. `https://bench.blackmad.com`), `ADMIN_UIDS` (comma-separated Firebase uids; sign in on the site, call `GET /api/me`, copy `uid`), and `FIREBASE_PROJECT_ID` if it differs.
7. `npx wrangler deploy`
8. Route `bench.blackmad.com/api/*` to the worker (dashboard Workers Routes, or a `routes` entry in `wrangler.jsonc`), or call it on its `workers.dev` URL and set `ALLOWED_ORIGINS` accordingly.
