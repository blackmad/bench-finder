# Resurrection status

Tracks progress on `docs/RESURRECTION_PLAN.md`. Update after every task.

States: `todo` · `in-progress` · `blocked (owner)` · `done`

| ID | State | Commit | Notes |
|---|---|---|---|
| 0.1 | done | 21d9b9b | Branch `resurrect` created from `main`. The refactor was committed as-is; `api.fastapi_server` imports. |
| 0.2 | partly done, owner action needed | 53d585e | `base64_creds.txt` removed from HEAD and added to `.gitignore`. `firebase_creds.json` was never tracked (already ignored), and the local copy is kept. **Owner:** revoke the old service-account key in the GCP console. It stays in git history. |
| 0.3 | done | (this commit) | See findings below. |
| 0.4 | done | n/a | `pg_dump` saved to `~/bench_finder_backups/supabase_2026-11-14.dump` (1.6 MB, 13 tables). Production has no user rows that SQLite lacks. See the diff below. |
| 0.5 | done | 35ccdee | `--cov` moved out of pytest addopts and `pytest-cov` added to the uv dev group. `uv run pytest`: 1 passed. |

## Findings log

### 0.3 Billing and crash forensics (2026-11-14)

- **Crash cause (confirmed from `vercel logs`):** FastAPI lifespan runs `os.makedirs("static")` (`api/fastapi_server.py:315`), which raises `OSError: [Errno 30] Read-only file system`, so app startup fails on every cold start. Supabase is reachable, so a paused database is not the cause.
- **Second security issue:** server startup prints the full Supabase connection string, password included, and it lands in Vercel logs (`Database initialized: postgres://postgres.<ref>:<password>@...`). **Owner:** rotate the Supabase database password. The old password is also in `.env`/`.env.local` (gitignored, not committed).
- **Vercel:** project `bench-finder` (team "David Blackman's projects"), FastAPI preset. Last deploy was 264 days ago. Plan tier not checked; Hobby is likely if the team is personal.
- **GCP / Firebase `bench-finder-a45db`:** billing **enabled** (billing account `011D92-…`), so it is on the Blaze plan. **No Cloud SQL instances.** Cloud Run API was never enabled. Storage bucket listing failed because of a gcloud/Python `ssl` crash, so check it in the console.
- **Supabase:** Postgres 17.6, eu-central-1 pooler, reachable. Plan tier not checked (no `supabase` CLI login); check in the dashboard.

### 0.4 Production vs local row counts

| table | Supabase | SQLite |
|---|---|---|
| bench_candidates | 3229 | 3229 |
| processed_benches | 3229 | 3229 |
| reverse_geocodes | 3229 | 3229 |
| detections | 12091 | 12091 |
| detection_items | 3904 | 3904 |
| images | 12998 | 37889 |
| searches | 22 | 22 |
| bench_reports | 1 | 1 (same row: a local test from 127.0.0.1) |
| ratings / comments / user_status / missing reports | 0 | 0 |

Conclusion: no production-only user data, so task 4.4 (import user rows into D1) has nothing to import. The SQLite images table is a superset of Supabase's.
