# PostgreSQL Spatial Indexes for Bounding Box Queries

## Problem

The PostgreSQL database was missing proper spatial indexes for efficient bounding box queries on location columns (lat/lng). Regular B-tree indexes don't efficiently handle 2D spatial queries like `lat BETWEEN ... AND lng BETWEEN ...`.

## Solution

We've created a migration script that adds PostGIS GIST spatial indexes for optimal bounding box query performance.

## Files Created/Modified

1. **`tools/add_postgres_spatial_indexes.py`** - Migration script to add spatial indexes
2. **`api/fastapi_server.py`** - Updated `_get_bbox_filtered_bench_candidate_ids()` to use PostGIS when available

## Usage

### Basic Usage

```bash
# Connect to your PostgreSQL database and add spatial indexes
python tools/add_postgres_spatial_indexes.py --database-url postgresql://user:pass@host/db
```

### Enable PostGIS Extension

If PostGIS is not yet enabled in your database:

```bash
python tools/add_postgres_spatial_indexes.py \
  --database-url postgresql://user:pass@host/db \
  --enable-postgis
```

### Dry Run (Preview)

To see what would be created without making changes:

```bash
python tools/add_postgres_spatial_indexes.py \
  --database-url postgresql://user:pass@host/db \
  --dry-run
```

### Check for Other Missing Indexes

To also check and optionally create other missing indexes:

```bash
python tools/add_postgres_spatial_indexes.py \
  --database-url postgresql://user:pass@host/db \
  --check-other-indexes
```

## What Gets Created

### Spatial Indexes

1. **`bench_candidates` table**:
   - Primary table for bbox queries
   - Index: `idx_bench_candidates_location_postgis` (or fallback variants)

2. **`missing_bench_reports` table**:
   - For missing bench report location queries
   - Index: `idx_missing_bench_reports_location_postgis` (or fallback variants)

### Index Types (in order of preference)

1. **PostGIS GIST Index** (best):
   ```sql
   CREATE INDEX USING GIST (ST_MakePoint(lng, lat)::geography);
   ```
   - Requires PostGIS extension
   - Optimal for spatial queries
   - Uses geography type for accurate distance calculations

2. **Point GIST Index** (fallback):
   ```sql
   CREATE INDEX USING GIST (point(lng, lat));
   ```
   - Works without PostGIS
   - Better than B-tree for spatial queries

3. **Composite B-tree Index** (last resort):
   ```sql
   CREATE INDEX (lat, lng);
   ```
   - Works everywhere
   - Better than nothing but not optimal

## How It Works

The script:
1. Checks if PostGIS is available/enabled
2. Attempts to create PostGIS indexes first
3. Falls back to point-based GIST indexes if PostGIS fails
4. Falls back to composite B-tree indexes as last resort

## Query Optimization

The `_get_bbox_filtered_bench_candidate_ids()` function in `api/fastapi_server.py` now:
- Detects if PostGIS is available
- Uses PostGIS spatial queries for optimal performance when available
- Falls back to regular BETWEEN filters otherwise
- Supports both PostgreSQL (PostGIS) and SQLite (R-tree)

### PostGIS Query

When PostGIS is available, the query uses:
```sql
SELECT id FROM bench_candidates
WHERE ST_MakePoint(lng, lat)::geography && ST_MakeEnvelope(:west, :south, :east, :north, 4326)::geography
```

This uses the GIST index efficiently for spatial intersection queries.

## Performance Expectations

- **Without spatial index**: Full table scans or inefficient index usage for bbox queries
- **With PostGIS GIST**: Logarithmic-time spatial lookups, 10-100x performance improvement
- **With point GIST**: Better than B-tree, but not as good as PostGIS

## Other Missing Indexes

The `--check-other-indexes` flag will identify and optionally create:
- Foreign key indexes (should already exist from migration)
- Filter column indexes (status, confidence, source, etc.)
- Composite indexes for common query patterns
- Date-based indexes for time queries

## Requirements

- PostgreSQL database
- PostGIS extension (optional but recommended)
- Python with sqlalchemy and database connection

## Notes

- Indexes are created with `IF NOT EXISTS`, so it's safe to run multiple times
- The script gracefully degrades if PostGIS is not available
- Existing queries continue to work without changes (backward compatible)
