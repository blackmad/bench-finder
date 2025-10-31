# Performance Optimizations Applied

## Summary

Optimizations have been applied to dramatically improve database query performance for the `/api/benches` endpoint.

## Changes Made

### 1. Database Indexes (`tools/add_performance_indexes.py`)

Created a migration script that adds **14 critical indexes**:

**Foreign Key Indexes:**
- `idx_processed_benches_bench_candidate_id`
- `idx_processed_benches_best_detection_id`
- `idx_processed_benches_best_image_id`
- `idx_images_bench_candidate_id`
- `idx_detections_image_id`
- `idx_detection_items_detection_id`

**Filter Column Indexes:**
- `idx_processed_benches_detection_status`
- `idx_detections_max_confidence`
- `idx_bench_candidates_source`
- `idx_images_capture_success`

**Composite Indexes:**
- `idx_processed_benches_status_detection` (detection_status, best_detection_id)
- `idx_images_bench_success` (bench_candidate_id, capture_success)
- `idx_bench_candidates_source_lat_lng` (source, lat, lng)

**Spatial Index:**
- `idx_bench_candidates_lat_lng` (for distance sorting)

**Database Configuration:**
- Enables WAL mode for better concurrent performance
- Sets cache size to 10MB
- Runs ANALYZE on all tables to update query planner statistics

### 2. Query Refactoring (`api/fastapi_server.py`)

**Eliminated GROUP BY from main query:**
- Moved image aggregation to a separate subquery
- Main query now has NO GROUP BY clause (was 13 columns before)
- Subquery handles image counts and filenames separately

**Eliminated N+1 Query for Segmentation:**
- Added segmentation check to subquery with CASE statement
- Removed per-row query in loop (was ~20 queries per page)
- Now loaded in single subquery join

**Eliminated N+1 Query for Detection Items:**
- If `include_detection_data=True`, now batch loads all detection items in ONE query
- Groups by `bench_candidate_id` in Python instead of separate queries
- Removed `get_detection_items_for_bench()` calls in loop

**Optimized Total Count:**
- Changed from `base_query.distinct().count()` to subquery-based count
- More efficient with indexes

**Reduced Joins:**
- Main query now has only 4 joins (was 3 joins + complex GROUP BY)
- Image data comes from subquery join (no aggregate joins)
- Segmentation comes from subquery join (no per-row queries)

## How to Apply

### Step 1: Run the Index Migration

```bash
python tools/add_performance_indexes.py
```

This will:
- Create all indexes
- Enable WAL mode
- Optimize database settings
- Update query planner statistics

### Step 2: Test the API

The query optimizations are already in the code. Test with:

```bash
curl "http://localhost:5174/api/benches?page=1&page_size=20&min_confidence=0.8&start_lat=52.36127728814825&start_lng=4.866352893186991&sort_by=distance&mode=benches&clustered=true&include_detection_data=false"
```

## Expected Performance Improvements

### Before:
- Main query: 13-column GROUP BY with multiple joins
- N+1 queries: ~20 segmentation checks per page
- N+1 queries: ~20 detection item queries (if `include_detection_data=True`)
- Total: 1 main query + ~20-40 additional queries per request
- Query time: ~2-5 seconds

### After:
- Main query: NO GROUP BY, only simple joins to subqueries
- N+1 queries: ZERO (everything loaded in subqueries)
- Detection items: 1 batch query if needed
- Total: 1-2 queries per request
- Query time: < 500ms (target)

## Technical Details

### Subquery Approach

**Image Aggregation Subquery:**
```sql
SELECT
    bench_candidate_id,
    COUNT(DISTINCT id) as image_count,
    GROUP_CONCAT(DISTINCT filename) as image_filenames,
    GROUP_CONCAT(DISTINCT CAST(id AS TEXT)) as image_ids
FROM images
WHERE capture_success = 1
GROUP BY bench_candidate_id
```

**Segmentation Subquery:**
```sql
SELECT
    detection_id,
    MAX(CASE WHEN polygon IS NOT NULL THEN 1 ELSE 0 END) as has_segmentation
FROM detection_items
GROUP BY detection_id
```

**Main Query:**
- Joins ProcessedBench → BenchCandidate → Detection
- LEFT JOINs to image and segmentation subqueries
- NO GROUP BY needed!

### Batch Loading Detection Items

Instead of:
```python
for bench in results:
    detection_items = get_detection_items_for_bench(session, bench.id)  # N queries!
```

Now:
```python
# Single query for all benches
all_items = session.query(DetectionItem, Image.bench_candidate_id)
    .join(...)
    .filter(Image.bench_candidate_id.in_(all_bench_ids))
    .all()

# Group in Python
for item, bc_id in all_items:
    detection_items_map[bc_id].append(item)
```

## Monitoring

To verify indexes are being used:

```sql
EXPLAIN QUERY PLAN
SELECT ... -- your query
```

Look for "SEARCH" or "SCAN" operations using the indexes.

## Rollback

If you need to rollback the indexes:

```sql
-- Drop all indexes (be careful!)
DROP INDEX IF EXISTS idx_processed_benches_bench_candidate_id;
-- ... (repeat for all indexes)
```

The code changes are backward compatible - the old query structure would still work, just slower.

## Next Steps (Optional)

If performance is still not sufficient after these optimizations:

1. **Denormalization**: Add `image_count` and `has_segmentation` columns to `ProcessedBench` table (maintained via triggers)
2. **Caching**: Add Redis caching for common queries
3. **PostgreSQL Migration**: Switch to PostgreSQL with PostGIS for better spatial queries
4. **Cursor-based Pagination**: For very large datasets
