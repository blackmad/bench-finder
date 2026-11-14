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
| 1.1 | done | b970ccb | `migrations/NNN_*.sql` plus `bench_finder/migrate.py` (`make db-migrate`). Applied to the real DB; a second run applies 0. |
| 1.2 | done | 26312cd | `make db-quarantine` (bench_finder/quarantine.py). Real DB: images 37,889 → 20,383 (7,251 mislinked legacy Mapillary rows and 699 panos >50 m quarantined to `data/archive.db`; 9,556 duplicate images and 65 duplicate detections deleted). `processed_benches` cleared; legacy tables archived. Independent check: 0 of 14,648 images with coordinates are >50 m from their candidate. 94 candidates now have 0 images. Pre-run backup: `~/bench_finder_backups/benches_2026-11-14_pre_phase1.db`. |
| 1.3 | done | 3b90cb7 | Unique `provider_id`, FK indexes, upserts in `add_bench_candidate` and `add_image`. Idempotency tests. |
| 1.4 | done | c8c4a09 | Images: aimed-view columns plus `kind` (existing rows = `legacy`). `detection_items.is_target` and `center_offset_deg`. New `image_annotations` and `bench_attributes`. |
| 1.5 | done | 538e8b1 | Six fixes plus one extra (detections could never be saved: a pydantic error on `detection_items`). Tests in `tests/test_task_1_5_fixes.py`. |
| 1.6 | done | 1926ff5 | 43 dead files and stale docs removed; DATABASE_MODEL.md rewritten; CLAUDE.md updated. Ruff count unchanged (26 existing errors). |
| 2.1–2.4 | done | 21d7053..03fd404, a11076f | Aimed views from up to 6 panos per bench (4–30 m, sectors, newest), FOV `clamp(2·atan(3/d),40,90)`, 1024 px, no 16k panos kept, Apple fallback, one event loop + semaphore + backoff. The paid Static API fallback was removed. **`streetlevel` 0.12.4's Google search is decommissioned; bumped to 0.13.0.** 100-bench sample: median 4 views, 11 with 0. Many 20–30 m views don't show the bench, so consider a 20 m cap after gold labels. Full fetch over all candidates started 2026-11-14 (backup: `~/bench_finder_backups/benches_2026-11-14_pre_aimed_fetch.db`). |
| 5.2 | done | 1246c80 | Vite + React 19 + Tailwind v4 tokens + MapLibre 6 + TanStack Query; typed `hc<AppType>` Worker client; self-hosted Archivo with the wdth axis. Entry JS 91 kB gz; the map chunk (298 kB gz) is lazy. Old frontend deleted. Dev fixture: `npm run fixture` (gitignored). Frontend `tsc` needs `worker/node_modules` installed. |
| 2.5 | done | ae978c5 | `uv run python -m bench_finder.labeling --db data/benches.db --images-root images/ --port 8877`. Verified in a headless browser against a DB copy, with real images rendering. Gold labelling (2.6) should wait for the 2.1–2.4 aimed views; today's images are mostly not aimed at the bench. |
| 3.1 | done (code, mocked) | c93449e | `bench_finder/clients/view_classifier.py`: Claude (structured output + batches), Gemini Decisions, TypeSafe Jev. `bench-finder classify-views --backend … --dry-run` prints the payload and a cost estimate. **No live calls yet**; the bake-off (3.2) is a spend gate. Blocker: Roboflow `inference` pins `anthropic<0.50` and a `google-genai` without `decisions`, so the Gemini backend can't run in this env until `inference` is dropped or isolated. |
| 3.3 | done | d26c032 | `bench_finder/facing.py`: offsets back 0, front 180, left −90, right +90, diagonals ±45/±135; weighted circular mean / distribution voting; axis-only for backless and picnic; OSM override with a disagreement flag; geometry prior hook; hero selection; `bench_attributes` writer. The sign is verified by derivation only. Check against the 40 OSM tags in 3.2. |
| 4.2 | done (local; upload not run) | ad752b9 | `uv run bench-finder publish --out dist-data [--upload]`: AVIF (+ WebP fallback, `hero_urls_webp`/`urls_webp`) derivatives, `benches.geojson` (~110 kB gz), per-bench JSON, `manifest.json` (`data_base`, `image_base`, `counts`), capacity guard. Projected R2 use 1.78 GB of the 9 GB budget. Only ~25% of benches have a hero until Phase 3 runs. `--upload` needs R2 env vars (4.1, owner). The frontend types still need the webp/manifest fields (done after 5.3 merges). |
| 4.5 | done (not exercised; nothing pushed) | (this commit) | `.github/workflows/ci.yml` has these jobs:<br>• `python`: uv sync, ruff on the new modules, pytest.<br>• `worker`: tsc and vitest.<br>• `frontend`: biome and build, using repo **variables** `VITE_*`.<br>• `deploy-pages`: `wrangler pages deploy --branch <ref>`, so every push gets a preview URL.<br>• `deploy-worker`: main only, runs D1 migrations and then deploys.<br>The deploy jobs no-op until the owner adds the repo secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` (4.1). Removed: the Firebase Hosting workflow, `firebase.json`, `vercel.json`, `api/index.py`. |
| 4.3 | done | 3cf3025 | `worker/`: Hono + D1 + Firebase JWT via jose. 35 vitest tests and tsc verified locally. Owner TODOs are in `worker/wrangler.jsonc` and `worker/README.md`. |
| 4.4 | done (nothing to import) | n/a | See 0.4: production has no user rows. |
| 5.1 | built, awaiting owner approval (GATE) | (this commit) | The decision page closed unanswered, so the assigned direction was built: "The Postcard Rack" (seed fc8012af). Reference pages are in `frontend/design-reference/`; serve them with `cd frontend/design-reference && python3 -m http.server 8890`, then open `/index.html` and `/bench.html?id=394`. Screenshots are in `.impeccable/review/`. DESIGN.md is written from the build. Finish review: two rounds; the last verdict was **fix**, with these open items: cluster density in the default view, the postmark ring illegible at rack size, the phone filter sheet and sample note not visually verified, no card-flip motion. The Street View crops in `img/` are gitignored. |

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
