# Database Model

The schema is defined by the SQLModel classes in `bench_finder/models/unified_models.py`
and evolved by the numbered SQL files in `migrations/`. It is SQLite (`data/benches.db`,
or `$DATABASE_PATH`). Enum values live in `bench_finder/models/enums.py`.

Schema changes are applied with `uv run python -m bench_finder.migrate`
(`make db-migrate`). A new database is created from the SQLModel metadata and every
migration is recorded as applied. An existing database gets only the migrations not yet
listed in `schema_migrations`.

Migrations applied so far: `001_baseline`, `002_constraints_and_indexes`, `003_schema_additions`.

## Relationships

```
searches
  └── bench_candidates (status: pending → image_download_done → detection_done)
        ├── images (kind: aimed | pano | legacy)
        │     ├── detections (one per model run)
        │     │     └── detection_items (one per bounding box / polygon)
        │     └── image_annotations (label from a model or a human)
        ├── processed_benches (1:1; best_image_id, best_detection_id)
        ├── reverse_geocodes (1:1, street address)
        ├── bench_attributes (1:1; hero_image_id → images)
        ├── bench_ratings / bench_user_status / bench_comments (user feedback)
        └── bench_reports (user reports of bad detections, optional candidate link)

missing_bench_reports        (standalone; no candidate FK)
rtree_bench_candidates       (R-tree mirror of bench_candidates lat/lng, kept by triggers)
```

## Tables

Foreign keys are noted inline. "Indexed" lists the indexes beyond primary keys.

### searches

A location search (geocoded query plus radius). Root of the pipeline.

Columns: `id`, `query`, `start_lat`, `start_lng`, `search_radius`, `status` (pending, completed, failed), `created_at`, `completed_at`.

### bench_candidates

A potential bench found during the search phase. The central table: most other tables hang off it.

Columns: `id`, `search_id` → searches, `provider_id` (unique, nullable; the upstream id, e.g. OSM), `lat`, `lng`, `tags` (JSON), `source` (`OSM`), `external_id`, `confidence`, `status` (pending, image_download_done, detection_done; default `pending`), `created_at`.

Indexed: `search_id`, `(lat, lng)`, `source`, `external_id`, `status`, `provider_id` (unique).

### images

One street view image per candidate and heading, or a raw panorama. Stores file location and capture provenance.

Columns: `id`, `bench_candidate_id` → bench_candidates, `heading`, `kind` (aimed, pano, legacy), `image_source` (see `ImageSource` in enums.py), `filepath`, `filename`, `firebase_url`, `file_size`, `capture_success`, `capture_error`, `panorama_lat`, `panorama_lng`, `panorama_heading`, `panorama_metadata` (TEXT), `pano_id`, `pano_date`, `camera_bearing_deg`, `camera_distance_m`, `fov_deg`, `pitch_deg`, `created_at`.

Indexed: `bench_candidate_id`, `capture_success`, unique `(bench_candidate_id, pano_id, kind)`. Legacy rows have a NULL `pano_id`, and NULLs never collide in a unique index.

### detections

One detection run of one model on one image.

Columns: `id`, `image_id` → images, `model_id`, `model_url`, `source` (ROBOFLOW, ULTRALYTICS, MULTI_MODEL, NONE), `external_detection_id`, `has_bench`, `bench_count`, `max_confidence`, `detections` (JSON, raw), `detection_success`, `detection_error`, `confidence_threshold`, `iou_threshold`, `image_size`, `inference_time`, `preprocess_time`, `postprocess_time`, `created_at`.

Indexed: `image_id`, `has_bench`, `max_confidence`, `source`, `external_detection_id`.

### detection_items

One bounding box or polygon inside a detection.

Columns: `id`, `detection_id` → detections, `class_name`, `confidence`, `bbox` (JSON), `polygon` (JSON), `is_target`, `center_offset_deg`, `created_at`.

Indexed: `detection_id`.

### processed_benches

The outcome for one candidate after detection. Exactly one row per candidate. `best_image_id` and `best_detection_id` are set only when `detection_status = 'detected'`.

Columns: `id`, `bench_candidate_id` → bench_candidates (unique), `detection_status` (`detected`, `no_bench`), `best_image_id` → images, `best_detection_id` → detections, `created_at`.

### reverse_geocodes

Cached reverse-geocoded street address for a candidate. One row per candidate.

Columns: `id`, `bench_candidate_id` → bench_candidates (unique), `formatted_address`, `street_number`, `street_name`, `city`, `state`, `postal_code`, `country`, `raw_response` (TEXT), `created_at`, `updated_at`.

### bench_attributes

Derived attributes for a candidate: facing direction, bench type, and hero image. One row per candidate.

Columns: `id`, `bench_candidate_id` → bench_candidates (unique), `facing_deg`, `facing_confidence`, `facing_method` (osm_tag, vlm, geometry, human), `axis_only` (backless bench: axis, not facing), `bench_type`, `backrest`, `faces_category`, `faces_text`, `hero_image_id` → images, `hero_reason`, `embed_pano_id`, `embed_heading_deg`, `updated_at`.

Indexed: `hero_image_id`.

### image_annotations

A label attached to an image, from a model or a human. Both sources sit side by side.

Columns: `id`, `image_id` → images, `annotator` (model id or `human:<uid>`), `label_type`, `value` (JSON), `confidence`, `created_at`.

Indexed: `image_id`.

### bench_reports

User reports that a detection is wrong (bad detection, wrong location, poor image). May link to a candidate.

Columns: `id`, `bench_candidate_id` → bench_candidates (nullable), `image_id` (legacy, not a foreign key), `report_type` (bad_detection, incorrect_location, poor_image_quality), `reported_image_filename`, `description`, `status` (pending, reviewed, resolved, dismissed), `admin_notes`, `user_agent`, `ip_address`, `user_location_lat`, `user_location_lng`, `extra_metadata` (JSON), `created_at`, `reviewed_at`.

Indexed: `bench_candidate_id`, `image_id`.

### missing_bench_reports

User reports of a bench that is not on the map. Not tied to a candidate.

Columns: `id`, `lat`, `lng`, `location_method` (gps, map_click), `accuracy_meters`, `description`, `uploaded_image_filename`, `status` (pending, verified, added, dismissed), `admin_notes`, `user_agent`, `ip_address`, `user_location_lat`, `user_location_lng`, `extra_metadata` (JSON), `created_at`, `reviewed_at`.

Indexed: `status`, `location_method`, `created_at`, `(lat, lng)`.

### bench_ratings

A user's rating of a bench.

Columns: `id`, `bench_candidate_id` → bench_candidates, `user_id`, `rating` (integer), `created_at`, `updated_at`.

Indexed: `bench_candidate_id`, `user_id`. The schema has no unique constraint on `(bench_candidate_id, user_id)`.

### bench_user_status

A user's status marker on a bench: been, want_to_go, or favorite.

Columns: `id`, `bench_candidate_id` → bench_candidates, `user_id`, `status` (been, want_to_go, favorite), `created_at`, `updated_at`.

Indexed: `bench_candidate_id`, `user_id`. As with ratings, the schema has no unique constraint on `(bench_candidate_id, user_id)`.

### bench_comments

A user's comment on a bench.

Columns: `id`, `bench_candidate_id` → bench_candidates, `user_id`, `comment`, `created_at`, `updated_at`.

Indexed: `bench_candidate_id`, `user_id`.

### rtree_bench_candidates

An SQLite R-tree virtual table over `bench_candidates` coordinates, used for bounding-box queries. Columns: `id`, `minLng`, `maxLng`, `minLat`, `maxLat`. Triggers on `bench_candidates` insert, update of `lat`/`lng`, and delete keep it in sync. The `_node`, `_parent` and `_rowid` shadow tables are internal. See `SPATIAL_INDEXING.md`.

### schema_migrations

Bookkeeping for `bench_finder.migrate`. Columns: `version` (primary key), `applied_at`.

### sqlite_sequence

Internal SQLite table that tracks `AUTOINCREMENT` counters. Not used by the application.
