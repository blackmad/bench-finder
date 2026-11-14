# Bench Finder Pipeline

## Overview

The pipeline has 3 phases, each corresponding to a CLI command:

```
generate-candidates  ──>  fetch-images  ──>  run-detections
   (PENDING)          (IMAGE_DOWNLOAD_DONE)   (DETECTION_DONE)
```

Each phase updates the `status` field on `bench_candidates`.

## Phase 1: Generate Candidates (`bench-finder generate-candidates "Location"`)

1. Geocode the query string → `(lat, lng)` via Google Geocoding API
2. Create a `Search` record (status=pending)
3. Query OSM Overpass API for benches within radius
4. Deduplicate candidates (10m threshold)
5. Store `BenchCandidate` records (status=pending)
6. Reverse geocode each candidate for street address

**Tables written:** `searches`, `bench_candidates`, `reverse_geocodes`

## Phase 2: Fetch Images (`bench-finder fetch-images`)

1. Query candidates with status=PENDING (or specified status)
2. All candidates of the run are processed in one event loop
   (`ImageDownloadService.process_candidates`), at most 4 at a time, with
   `backoff` retries on pano/tile requests and Overpass. Nothing sleeps blocking.
3. For each bench (`StreetViewClient.capture_bench_views_async`):
   - List every Google panorama within 30 m (zoom-17 coverage tiles, then
     per-pano metadata for date and tilt) via the `streetlevel` library (free)
   - Drop <4 m, third-party, indoor (building-level metadata, and a Places365
     indoor check on the rendered view), and pre-2016 when newer exists
   - Keep up to 6, spread over six 60-degree sectors of camera-to-bench bearing,
     newest first
   - For each, fetch only the panorama zoom level the output needs, cut a
     1024 px view aimed at the bench (FOV = clamp(2 atan(3 m / d), 40, 90) deg,
     pano pitch/roll applied), save it, and discard the panorama
   - If Google gave fewer than 3 views, add up to 3 Apple Look Around views
     (faces stitched to an equirect, then the same extraction)
4. Store `Image` rows with `kind='aimed'`, `pano_id`, `pano_date`,
   `camera_bearing_deg`, `camera_distance_m`, `fov_deg`; upsert key is
   (candidate, pano_id, kind), so re-running adds no rows
5. Update candidate status -> IMAGE_DOWNLOAD_DONE

The paid Google Street View Static image API is not used.

**Tables written:** `images`

## Phase 3: Run Detections (`bench-finder run-detections`)

1. Query candidates with status=IMAGE_DOWNLOAD_DONE
2. For each candidate, run AI detection on all successful images
3. Calculate pixel coverage for each detection
4. Select representative image (highest coverage / confidence)
5. Store `Detection` + `DetectionItem` records
6. Create `ProcessedBench` record with best_image_id and best_detection_id
7. Update candidate status → DETECTION_DONE

**Tables written:** `detections`, `detection_items`, `processed_benches`

## Data Model

```
searches
  └── bench_candidates (status: pending → image_download_done → detection_done)
        ├── images (one per heading per source)
        │     └── detections (one per model run)
        │           └── detection_items (one per bounding box)
        ├── processed_benches (one per candidate, links to best image + detection)
        └── reverse_geocodes (street address)
```

## Key Files

| File | Role |
|------|------|
| `bench_finder/cli.py` | CLI commands (generate-candidates, fetch-images, run-detections) |
| `bench_finder/core/streetview.py` | Image capture from Google/Apple panoramas |
| `bench_finder/services/image_download_service.py` | Orchestrates image download for a candidate |
| `bench_finder/detection.py` | Orchestrates detection for a candidate |
| `bench_finder/services/database.py` | Database read/write operations |
| `bench_finder/clients/multi_model_client.py` | Multi-model detection with fallback |
| `bench_finder/clients/roboflow_client.py` | Roboflow detection client |
| `bench_finder/clients/ultralytics_client.py` | Ultralytics/YOLO detection client |
| `bench_finder/generators/overpass.py` | OSM Overpass bench search |
| `bench_finder/models/unified_models.py` | All SQLModel table definitions |
| `bench_finder/models/enums.py` | Status enums (BenchCandidateStatus, etc.) |

## Known Architectural Issues

### 1. Business logic duplicated between CLI and services
`cli.py` does its own database queries, status tracking, and statistics counting
instead of delegating entirely to `ImageDownloadService` and `BenchDetector`.

### 2. Best-image selection logic duplicated
`detection.py` computes the "best image" (by pixel coverage + confidence) in
two separate places (~lines 404-428 and ~528-542), copy-pasted.

### 3. `streetview.py` is too large (2300 lines)
Mixes API client code, image processing (equirectangular→perspective), caching,
and retry logic. Should be split into separate modules.

### 4. `cli.py` is too large (2800 lines)
All commands in one file with inline business logic. Should extract commands
into separate modules and move orchestration to service classes.

### 5. `BenchCandidate` defined twice
- `generators/bench_generator.py` has a `@dataclass BenchCandidate` (search result)
- `models/unified_models.py` has `class BenchCandidate(SQLModel, table=True)` (DB row)
- CLI has to alias one as `DBBenchCandidate` to avoid name collision
