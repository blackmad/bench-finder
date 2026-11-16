# Bench Finder resurrection plan (orchestrator-ready)

## Context

Bench Finder (bench.blackmad.com) was abandoned mid-migration. An audit on 2026-11-14 found:

- **Production is down, not slow.** Every API call returns Vercel `500 FUNCTION_INVOCATION_FAILED` after 7–8 s, including `/api/config`, which touches no database. `/cards` waits on that call and swallows the error (`frontend/src/contexts/AppContext.tsx:205-233`, `CardsPage.tsx:195`), so it stays blank. Cause unconfirmed: either startup `os.makedirs` on a read-only filesystem (`api/fastapi_server.py:70-72`) or a paused Supabase database.
- **Hosting is spread over three providers:** Vercel (site + Python API), Supabase Postgres (Frankfurt), Firebase project `bench-finder-a45db` (Storage bucket, Auth, and a broken second Hosting deploy on every push). A Cloud SQL instance may also exist from a December 2025 migration attempt (not verified).
- **Data is small:** 3,229 OSM candidates (Amsterdam + a little NYC), 1,887 marked detected, in a 25 MB SQLite file. Local images are 60 GB, mostly 16384×8192 panoramas.
- **Existing detections are not trustworthy.** All detections predate the current imagery; none of the 21,653 streetlevel images has been through detection. 1,076 of the 1,887 "detected" benches use a representative image that belongs to a different location (7,251 mislinked legacy Mapillary rows). 22% of candidates have only Apple imagery, which never yields a usable file.
- **No facing-direction or view-selection concept exists.** One nearest panorama per bench, one aimed view, stock `yolo11n-seg` COCO plus one Roboflow model, no classifier, no labels. Only 40 OSM `direction` tags exist as ground truth.
- **The frontend is a prototype:** Vite starter CSS still active, fonts never loaded, 48 emoji as UI, debug controls shown to everyone, separate desktop/mobile apps by user-agent sniffing, login reachable only on the mobile map, no place search.
- **Security:** `base64_creds.txt` in git is almost certainly the Firebase service-account private key.

**Outcome wanted:** a finished, fast, free-to-run site with trustworthy bench data, a facing direction per bench, a hero image chosen from behind the bench where possible, a real design, and a repeatable pipeline for adding cities.

## Decisions already made by the owner

1. **Hosting: all Cloudflare.** Pages (static site), R2 (images + prebuilt data files), one TypeScript Worker + D1 for writes. The Python code becomes the local pipeline only; FastAPI leaves production.
2. **Accounts stay at launch:** sign-in, ratings, visited/favorite, public comments, reports.
3. **Imagery:** host small crops; use Google's official Maps Embed for the interactive panorama; self-hosted downsampled panoramas are an optional later task.

## Target architecture

```
LOCAL (Python, uv)                       CLOUDFLARE (free plan)
bench_finder pipeline                    Pages  -> frontend/ (static SPA)
  generate -> fetch views -> detect      R2     -> img/<hash>-<w>.avif
  -> classify -> fuse facing             R2     -> data/benches.<hash>.geojson
  -> pick hero                                     data/bench/<id>.json, manifest.json
data/benches.db (source of truth)        Worker -> /api/* (Hono): ratings, status,
  `bench-finder publish` ------------->            comments, reports, moderation
                                         D1     -> user-generated rows only
                                         Firebase Auth (free) -> ID token verified
                                                   in the Worker via Google JWKS
```

Reads never hit a server: the map loads one GeoJSON file and filters client-side. Only user writes go through the Worker.

Repo layout after the work: `bench_finder/` (pipeline), `frontend/` (rebuilt), `worker/` (new), `api/` deleted after cutover, `docs/RESURRECTION_PLAN.md` + `docs/RESURRECTION_STATUS.md`.

## How to run this plan (orchestrator rules)

- **Roles.** Orchestrator = Opus: owns sequencing, briefs, review, design direction, and every decision gate. Subagent tier per task is marked **[S]** Sonnet, **[H]** Haiku, **[O]** do it yourself.
- **First action:** copy this file to `docs/RESURRECTION_PLAN.md`, create `docs/RESURRECTION_STATUS.md` (task id, state, commit, notes) and update it after every task so work survives context resets.
- **Branching:** commit the owner's uncommitted refactor first as its own commit on a new branch `resurrect` (ask before committing). One commit per task. Parallel lanes use worktree isolation; lanes touch disjoint directories (`bench_finder/`, `worker/`, `frontend/`).
- **Briefs:** each subagent gets the task row, the named files, the acceptance check, and what is out of scope. Never pass a conclusion to be confirmed; pass the check to run.
- **Verify before marking done:** run the acceptance check yourself (tests, build, a query, a screenshot). A subagent's "done" is not evidence.
- **Gates (stop and ask the owner):** anything marked **GATE**; any cloud resource deletion; deleting local image directories; any paid API run; DNS changes; pushing or force-pushing.
- **Python:** activate the venv / use `uv run` for every command (CLAUDE.md rule).

## Phase 0 — Stabilize, secure, find the bill

| ID | Task | Who | Acceptance |
|---|---|---|---|
| 0.1 | Commit the in-progress `api/routes/` refactor as-is on `resurrect` | [O] GATE | `git status` clean; app still imports |
| 0.2 | Rotate the Firebase service-account key; delete `base64_creds.txt`, `firebase_creds.json` from the tree; add to `.gitignore` | [O] GATE (owner rotates in console) | old key revoked; files gone from HEAD |
| 0.3 | Billing forensics: `vercel logs` for the crash cause; `gcloud sql instances list --project bench-finder-a45db`; Firebase plan; Supabase plan; Vercel plan. Write findings to STATUS | [S] + owner logins | one line per provider: what exists, what it costs |
| 0.4 | Export production data before touching anything: `pg_dump` Supabase; diff row counts against `data/benches.db`; keep any user rows (reports, ratings, comments) that exist only in production | [S] GATE | dump file saved outside repo; diff recorded |
| 0.5 | Fix pytest startup (`--cov` without `pytest-cov`), make `uv run pytest` green | [H] | 1 existing test passes |

Do not repair the Vercel deploy. Phase 4 replaces it.

## Phase 1 — Data foundation (lane A, Python)

| ID | Task | Who | Acceptance |
|---|---|---|---|
| 1.1 | Adopt numbered SQL migrations (`migrations/NNN_*.sql` + a tiny runner replacing `tools/migrate_database.py`); back up `data/benches.db` first | [S] | runner is idempotent; `make db-migrate` works |
| 1.2 | Quarantine bad data: move the 7,251 mislinked Mapillary image rows and legacy tables (`benches`, `detected_benches`, `clustered_benches`, `ultralytics_detections`) to an archive DB; delete duplicate image/detection rows; clear `processed_benches` | [S] | no image row is >50 m from its candidate; row counts logged |
| 1.3 | Constraints + idempotency: unique `bench_candidates.provider_id`; unique image key `(bench_candidate_id, pano_id, kind)`; upserts in `services/database.py` (`add_bench_candidate` :311-357); indexes on FK columns | [S] | re-running a search or fetch adds 0 rows |
| 1.4 | Schema additions (below) in `bench_finder/models/unified_models.py` + migration | [S] | migration applies to a copy of the DB |
| 1.5 | Bug fixes: `detection.py:533` (writes "detected" with no bench), `:453` hardcoded success, `cli.py:435` bare `from detection import`, `fetch-images` ignoring `search_id` (`cli.py:~808-840`), YOLO reload per image (`clients/ultralytics_client.py:146`), 10 m dedup + dead enum-case branch (`cli.py:1044-1080`) → dedupe by `provider_id`, merge only <1.5 m | [S] | unit test per fix |
| 1.6 | Delete dead code: `api/database_service.py`, stale `tools/*` one-offs, `bin/unified_bench_search`, Firestore/Mapillary/Cloud SQL docs, `templates/`, `openapi.json`, `.upload_progress.json`, `requirements.txt.backup`; rewrite `DATABASE_MODEL.md` from `docs/PIPELINE.md` | [H] | `ruff` clean; imports resolve |

**Schema additions (1.4)**
- `images`: `pano_id`, `pano_date`, `camera_bearing_deg` (camera→bench), `camera_distance_m`, `fov_deg`, `pitch_deg`, `kind` (`aimed`/`pano`/`legacy`).
- `detection_items`: `is_target` (bool), `center_offset_deg`.
- New `image_annotations`: `image_id`, `annotator` (model id or `human:<uid>`), `label_type`, `value` (JSON), `confidence`, `created_at`. Model and human labels live side by side.
- New `bench_attributes` (one row per candidate): `facing_deg`, `facing_confidence`, `facing_method` (`osm_tag`/`vlm`/`geometry`/`human`), `axis_only` (backless benches), `bench_type`, `backrest`, `faces_category`, `faces_text`, `hero_image_id`, `hero_reason`, `embed_pano_id`, `embed_heading_deg`.

## Phase 2 — Imagery and detection v2 (lane A)

| ID | Task | Who | Acceptance |
|---|---|---|---|
| 2.1 | Multi-panorama enumeration in `core/streetview.py`: for each bench list panoramas within 30 m, keep up to 6 spread across bearing sectors, prefer newest, drop pre-2016 when a newer one exists, drop distance <4 m, drop third-party/indoor (reuse `tools/remove_indoor_images.py` logic). Reuse `_calculate_bearing` (:1135-1167) and the `equi2pers` extraction (:552-565, :1227-1242) | [S] | median ≥3 views per bench on a 100-bench sample; bearing and distance stored |
| 2.2 | Aimed-view extraction: FOV scaled by distance (`clamp(2·atan(3 m / d), 40°, 90°)`), honour pano pitch/roll, 1024 px output. Stop keeping 16k panoramas (fetch the zoom needed, discard after extraction) | [S] | views visually centred on the bench in a 30-image contact sheet |
| 2.3 | Apple Look Around: write a real aimed view from the stitched equirect (fix `filepath=None`, :610-653) | [S] | Apple-only candidates get a usable file |
| 2.4 | Remove the per-candidate `asyncio.run` and the 60 s blocking sleep (:149-164, :186); bounded concurrency + `backoff` retries on Overpass and pano fetches | [S] | 100 benches fetch without a blocking sleep |
| 2.5 | Labeling tool: a single local HTML page over the SQLite DB (served by a small script) to label per image: bench present, target box correct, view relation (8-way), bench type. Writes `image_annotations` | [S] | owner can label ~10 images/min |
| 2.6 | **Gold set:** owner labels ~300 benches (about an hour); add the 40 OSM `direction` benches | owner GATE | ≥300 labelled benches, stratified by distance and source |
| 2.7 | Detector bake-off on the gold set: current `yolo11n-seg` vs a larger YOLO seg model vs an open-vocabulary Ultralytics model prompted "bench" vs Roboflow `streetview-benches-m4bc5/1`. Also try Jev 1.14's `box` question ("locate the bench nearest the centre of the image"), which returns one box with a confidence, as a target locator. Report precision/recall for *target-bench present* | [S] | table in STATUS; pick one primary + one fallback |
| 2.8 | Target association: mark the detection nearest the image centre (the view is aimed at the bench) as `is_target`, reject frames whose only detections are off-centre; replace pixel-coverage selection (`detection.py:166-183`) | [S] | target-association accuracy ≥90% on gold |
| 2.9 | Re-run detection from scratch on all aimed views | [H] runs, [O] checks | every candidate has status `DETECTION_DONE`; counts sane vs gold |

## Phase 3 — Facing direction and hero image (lane A)

**Method**
1. **Per-view classification** with structured output: `bench_visible`, `bench_type` (backrest / backless / picnic / other), `view_relation` (which side of the bench the camera sees, 8-way: front, front-left, left, back-left, back, back-right, right, front-right, unknown), `occluded`, `quality` 0–1, `faces_category` (water, street, park, square, wall, playground, other), `faces_text`. Every field except `faces_text` is a closed-set question (yes/no, choice, or ordered rubric), so a decision-style model can answer all of them in one request per image; `faces_text` is optional and only a generative model can fill it.
2. **Per-view facing estimate:** `facing = camera_bearing_deg + offset(view_relation)`. Camera sees the back → offset 0°; sees the front → 180°; sees the bench's left side → 90° one way, right side the other. Unit-test the sign convention against the 40 OSM tags before trusting it.
3. **Fusion:** weighted circular mean across views (weight = quality × model confidence); confidence = resultant length. When the classifier returns a probability for every `view_relation` option, vote with the whole distribution instead of the top answer. Backless benches get `axis_only` and an axis, not a facing.
4. **Priors:** an OSM `direction` tag wins when present. A geometry prior (perpendicular to the nearest path, water edge or wall from Overpass) breaks ties and flags disagreements >90° for the review queue.
5. **Hero image:** for benches with a backrest, prefer the best-quality view with relation back / back-left / back-right; otherwise best-quality front. Store `hero_reason`.
6. **View from the bench:** store the nearest panorama id and `embed_heading_deg = facing_deg` for the official Maps Embed.

| ID | Task | Who | Acceptance |
|---|---|---|---|
| 3.1 | Classifier client `bench_finder/clients/view_classifier.py` with one interface and three backends. (a) Claude via the `anthropic` SDK (already a dependency): structured output via `output_config.format`, Message Batches for bulk runs, results keyed by `custom_id`; load the `claude-api` skill before writing it. (b) Gemini Decisions API via the `google-genai` SDK: one request per image carrying all questions, storing per-option probabilities; write it from the official docs, not from memory. (c) TypeSafe Jev (`jev-1.14.0`) over REST with the `TypeSafe-Danger-Zone-Images: true` header; resize images to its documented limits before sending, since it does not resize for you | [S] | all three backends return schema-valid labels for the same 20 images |
| 3.2 | **Bake-off on the gold set:** `gemini-decision-1` vs `jev-1.14.0` vs `claude-haiku-5-5` vs `claude-sonnet-5-5`. Metrics: 8-way view-relation accuracy, facing within ±45°, mean angular error, calibration (does stated confidence match observed accuracy), measured cost per 1,000 images. Try two image resolutions on the Gemini backend. On Jev, also try defining the eight `view_relation` choices with one reference photo each (it accepts example images as choice criteria), taken from gold-set benches held out of scoring | [S], [O] decides | table in STATUS; pick the cheapest model with ≥85% within ±45° |
| 3.3 | Fusion + priors + hero selection, pure functions with unit tests | [S] | tests for wrap-around, backless, single-view, OSM override |
| 3.4 | **Full classification run** | [H] runs GATE (spend) | every detected bench has `bench_attributes` |
| 3.5 | Escalation: benches with low fusion confidence go to the stronger model, then to the review queue | [S] | <10% of benches left as low-confidence |
| 3.6 | Later, optional: distill labels into an Ultralytics classification model (orientation + type) so new cities classify locally at no cost | [S] | matches VLM within 5 points on gold |

**Cost estimate for 3.4** (list prices from the `claude-api` skill table cached 2026-11-03; ~16,000 views at an assumed ~2,000 input and ~300 output tokens each): Haiku 5.5 about $5 standard, about half that with batching; Sonnet 5.5 about $110 standard, about $55 batched. Gemini Decision 1 about $3 (Google's announced $0.10 per 1M input tokens, no output charge), possibly less on its no-cost tier; its image token counts are not known and depend on the resolution setting. Jev 1.14 about $3 ($0.084 per 1M input tokens with free output, as quoted by a third-party guide; image token counts unknown). Measure on 50 images before the full run.

## Phase 4 — Publish pipeline and Cloudflare (lane B)

| ID | Task | Who | Acceptance |
|---|---|---|---|
| 4.1 | Owner creates the Cloudflare account, runs `wrangler login`, creates R2 bucket, D1 database, Pages project | owner GATE | `wrangler whoami` works |
| 4.2 | `bench-finder publish` command: build AVIF + WebP derivatives at 400/800/1600 px with content-hashed names, upload to R2 with immutable cache headers, write `benches.<hash>.geojson` (id, lat, lng, facing, type, backrest, hero key, short address, confidence), per-bench `bench/<id>.json`, and `manifest.json` | [S] | GeoJSON <500 kB gzipped; total R2 usage reported and under the free allowance |
| 4.3 | `worker/`: Hono app, D1 migrations for `ratings`, `user_status`, `comments`, `bench_reports`, `missing_bench_reports`; Firebase ID-token verification with `jose` against Google's JWKS (no service account); Turnstile + rate limit on anonymous reports; photo upload to R2; admin routes behind a uid allowlist | [S] | Vitest suite green under `wrangler dev` |
| 4.4 | Import any production user rows saved in 0.4 into D1 | [H] | counts match the dump |
| 4.5 | CI: GitHub Actions for `frontend` → Pages and `worker` → `wrangler deploy`; delete `.github/workflows/firebase-hosting-deploy.yml`, `firebase.json`, `vercel.json`, `api/index.py` | [S] | push to `resurrect` produces a preview URL |
| 4.6 | Cutover: point `bench.blackmad.com` at Pages, images at an R2 custom domain | owner GATE | site live on the new stack |
| 4.7 | Teardown after a week of clean running: Vercel project, Supabase project, Firebase Storage bucket and Hosting, any Cloud SQL instance; keep Firebase Auth only and move the project to the free plan; delete `api/` | owner GATE, each item | billing shows zero recurring charges |

## Phase 5 — Frontend rebuild (lane C)

**Stack:** keep Vite, React 19, TypeScript, TanStack Query, React Router. Replace Leaflet with MapLibre GL (built-in clustering, free vector tiles), styled-components with Tailwind v4 + CSS-variable tokens, axios + the unmaintained OpenAPI codegen with `fetch` and Hono's typed client. Lazy-load routes and the Firebase SDK.

**Skills and order of use**
1. Check which are installed; install the missing ones from their READMEs: `impeccable` (already present), `leonxlnx/taste-skill`, `vercel-labs/agent-skills` (web design guidelines, React best practices), `anthropics/skills` frontend-design.
2. `impeccable` to set direction and write `DESIGN.md` (tokens, type, colour, motion, component rules).
3. frontend-design + taste-skill while building.
4. Vercel web design guidelines + React best practices as review gates on every screen.
5. `impeccable` critique/polish pass, then the `impeccable-finish-reviewer` agent.

**Design brief:** an atlas of places to sit and what you see from them. Photography leads; the facing direction is the signature datum (a compass mark on every card and marker). No emoji as UI, no glass, no gradient buttons, no debug data. One responsive app; no user-agent sniffing; the map works without location permission.

| ID | Task | Who | Acceptance |
|---|---|---|---|
| 5.1 | Design direction: `DESIGN.md` + two reference screens (map/list, bench detail) at desktop and phone widths | [O] GATE (owner picks direction) | owner approves screenshots |
| 5.2 | Scaffold: tokens, fonts actually loaded, routing, data layer reading `manifest.json` → GeoJSON, error boundary, 404; delete `index.css` starter, `App.css`, `ApiExample`, `theme-redesign-example.ts`, `lib/supabase.ts` | [S] | build passes; initial JS <200 kB gzipped |
| 5.3 | Map + list: clustered markers with facing arrows, client-side filters (type, backrest, facing, what it faces), place search (Photon), URL-synced viewport; phone layout is map + bottom sheet | [S] | 5,000 points pan at 60 fps; no network request on pan |
| 5.4 | Bench detail: hero from behind, gallery with `srcset` and explicit dimensions, compass, "view from this bench" Maps Embed, tags, report action | [S] | Lighthouse performance ≥90 on phone |
| 5.5 | Accounts: one sign-in entry point on every layout, rating, visited/favorite, public comments, `/me` lists | [S] | signed-in round trip works against the Worker |
| 5.6 | Reports + admin: bad-detection and missing-bench flows (reuse `utils/imageCapture.ts`), moderation queue for reports, comments and low-confidence facings | [S] | a report appears in the queue and can be resolved |
| 5.7 | Accessibility + metadata: real buttons, dialog roles and focus trap, contrast ≥4.5:1, keyboard paths; favicon, Open Graph image, manifest | [H] fixes, [O] audits | axe clean on all routes |
| 5.8 | Stretch: sun on the bench (facing + sun position → "evening sun" filter) | [S] | filter returns west-facing benches at sunset |

## Phase 6 — New benches and upkeep (after launch)

- **Coverage:** query by city area or tiled bounding box instead of a point radius; add `bench=yes` on other features and `leisure=picnic_table` as bench types; a city queue with `update-all <city>` running generate → fetch → detect → classify → publish. [S]
- **Centred heroes:** aimed views point at the OSM pin, so the bench is often off to one side. `bench_finder/recentre.py` turns the camera towards the target detection box. It tilts down so the bench sits at ~64% of the frame height with what it looks at above, sets the FOV so the bench fills ~38% of the width, and re-renders at 2,048 px. Pilot of 50 first (owner reviews `data/centring_pilot/index.html`), then all ~4,450 heroes and republish. [S]
- **Refresh:** monthly re-query; `cleanup-deleted-osm` already exists; re-fetch views when a newer panorama appears. [H]
- **Unmapped benches:** run the detector on panoramas along park paths where no OSM bench is within 10 m; results enter the review queue as unverified, alongside user missing-bench reports. [S]
- **Never write Street-View-derived data back to OpenStreetMap;** OSM does not accept it. Offer an "edit in OSM" link for human contributions only.
- **Capacity guard:** `publish` fails loudly when projected R2 usage or D1 limits approach the free allowance.

## Sequencing

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► publish (4.2) ──► cutover (4.6) ──► 4.7, Phase 6
              │
              ├─► Lane B: 4.1, 4.3, 4.5 (needs only the schema from 1.4)
              └─► Lane C: 5.1, 5.2 (can start on today's data exported as GeoJSON), then 5.3–5.7
```

Lanes B and C start as soon as 1.4 lands. Owner time is needed at: 0.1–0.4, 2.6 (labelling), 3.4 (spend), 4.1, 4.6, 4.7, 5.1.

## Verification (end to end)

1. `uv run pytest` and `ruff` green; `npm run build` and Worker tests green.
2. Pipeline on a fresh small area (`update-all "Vondelpark, Amsterdam"`): re-running adds zero rows; every detected bench has views, a target detection, `bench_attributes` and a hero.
3. Gold-set report regenerated: target association ≥90%, facing within ±45° ≥85%, OSM-tag agreement listed bench by bench.
4. Contact sheet of 50 random hero images reviewed by the owner: the bench is the mapped bench, and backrest benches are seen from behind where a rear view exists.
5. Preview deploy checked in a real browser at desktop and phone widths: map loads with no API call, `/bench/:id` shows the embed aimed along the facing, sign-in → rate → comment → report → moderate all work.
6. Lighthouse on phone: performance ≥90, accessibility ≥95. No request to Vercel, Supabase or Firebase Storage in the network log.
7. A week after cutover: provider billing pages show no recurring charges.

## Not verified — check before relying on it

- The cause of the Vercel crash, and whether a Cloud SQL instance exists (0.3).
- Whether production Supabase holds rows that local SQLite lacks (0.4).
- Cloudflare free allowances: sources agree on D1 (5 GB, 5M rows read and 100K written per day, hard-failing since 2026-09-01); R2's 10 GB and the Workers daily request cap (100K vs 500K) came from secondary sources. Confirm on Cloudflare's own pricing pages in 4.1.
- Gemini Decisions API (`gemini-decision-1`, announced 2026-11-11, https://aistudio.google.com/docs/decisions-api): the announcement states image input, yes/no + choice (2–255 options) + rubric questions, a 0–1 confidence per answer, and a no-cost tier, but not the tier's limits, image token counts, or how well it handles a spatial judgement like which side of a bench is visible. It is three days old and not yet on Google Cloud. The bake-off decides.
- Jev 1.14 (`jev-1.14.0`, released 2026-10-14, docs at https://docs.typesafe.ai/images and https://docs.typesafe.ai/primitives/box): image input and the `box` question are experimental opt-in features that TypeSafe labels "danger zone" and describes as for prototypes. The price and limits above come from a guide site (jevai.net), not TypeSafe's own pages. Confirm image size limits and pricing in the official docs.
- That the Maps Embed street-view mode is still free of charge.
- The panorama heading sign convention (`streetview.py:1227-1242`), tested only in a notebook.
