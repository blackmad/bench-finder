# Database Performance Optimization Plan

## Problem Analysis

The `/api/benches` endpoint is experiencing slow performance. Based on code analysis, here are the identified bottlenecks:

### Current Query Structure (from `get_high_confidence_benches_filtered`)

1. **Complex multi-table joins:**
   - `ProcessedBench` → `BenchCandidate` (JOIN)
   - `ProcessedBench` → `Detection` (OUTER JOIN)
   - `BenchCandidate` → `Image` (OUTER JOIN with filter)

2. **Heavy aggregations:**
   - `COUNT(DISTINCT Image.id)` for image counts
   - `GROUP_CONCAT(DISTINCT Image.filename)` and `GROUP_CONCAT(DISTINCT Image.id)` for image lists
   - Large `GROUP BY` clause with 13 columns

3. **N+1 Query Problems:**
   - **Segmentation check**: For each result row (lines 907-913), a separate query is executed to check if `DetectionItem` has polygons:
     ```python
     has_segmentation_query = session.query(DetectionItem)
         .filter(DetectionItem.detection_id == best_detection_id)
         .filter(DetectionItem.polygon.isnot(None))
         .first()
     ```
   - **Detection items**: If `include_detection_data=True`, `get_detection_items_for_bench()` is called for each bench (lines 923-925), which executes another complex join query

4. **Inefficient total count:**
   - Uses `base_query.distinct().count()` which requires scanning all matching rows

5. **Missing Database Indexes:**
   - No indexes on foreign keys: `ProcessedBench.bench_candidate_id`, `ProcessedBench.best_detection_id`, `Image.bench_candidate_id`, `Detection.image_id`, `DetectionItem.detection_id`
   - No indexes on frequently filtered columns: `ProcessedBench.detection_status`, `Detection.max_confidence`, `BenchCandidate.source`, `Image.capture_success`
   - No composite indexes for common query patterns (e.g., `(detection_status, best_detection_id)`, `(bench_candidate_id, capture_success)`)
   - No index on spatial columns (`lat`, `lng`) for distance sorting

6. **Inefficient distance sorting:**
   - Uses squared distance calculation `(lat - start_lat)² + (lng - start_lng)²` which cannot use spatial indexes
   - Calculation happens on every row before sorting

## Optimization Plan

### Phase 1: Critical Indexes (Highest Impact)

**Priority: CRITICAL** - These should be added first as they will provide immediate performance gains.

1. **Foreign Key Indexes:**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_processed_benches_bench_candidate_id
       ON processed_benches(bench_candidate_id);

   CREATE INDEX IF NOT EXISTS idx_processed_benches_best_detection_id
       ON processed_benches(best_detection_id);

   CREATE INDEX IF NOT EXISTS idx_processed_benches_best_image_id
       ON processed_benches(best_image_id);

   CREATE INDEX IF NOT EXISTS idx_images_bench_candidate_id
       ON images(bench_candidate_id);

   CREATE INDEX IF NOT EXISTS idx_detections_image_id
       ON detections(image_id);

   CREATE INDEX IF NOT EXISTS idx_detection_items_detection_id
       ON detection_items(detection_id);
   ```

2. **Filter Column Indexes:**
   ```sql
   CREATE INDEX IF NOT EXISTS idx_processed_benches_detection_status
       ON processed_benches(detection_status);

   CREATE INDEX IF NOT EXISTS idx_detections_max_confidence
       ON detections(max_confidence);

   CREATE INDEX IF NOT EXISTS idx_bench_candidates_source
       ON bench_candidates(source);

   CREATE INDEX IF NOT EXISTS idx_images_capture_success
       ON images(capture_success);

   CREATE INDEX IF NOT EXISTS idx_detection_items_polygon
       ON detection_items(detection_id) WHERE polygon IS NOT NULL;
   ```

3. **Composite Indexes for Common Query Patterns:**
   ```sql
   -- For main query: detection_status + best_detection_id lookup
   CREATE INDEX IF NOT EXISTS idx_processed_benches_status_detection
       ON processed_benches(detection_status, best_detection_id);

   -- For image filtering: bench_candidate_id + capture_success
   CREATE INDEX IF NOT EXISTS idx_images_bench_success
       ON images(bench_candidate_id, capture_success);

   -- For source filtering with detection status
   CREATE INDEX IF NOT EXISTS idx_bench_candidates_source_lat_lng
       ON bench_candidates(source, lat, lng);
   ```

4. **Spatial Index for Distance Sorting:**
   ```sql
   -- For distance-based queries
   CREATE INDEX IF NOT EXISTS idx_bench_candidates_lat_lng
       ON bench_candidates(lat, lng);
   ```

### Phase 2: Query Optimization

**Priority: HIGH** - Reduce N+1 queries and optimize aggregations.

1. **Eliminate N+1 Query for Segmentation Check:**
   - Instead of querying `DetectionItem` for each result, join it in the main query
   - Use a CASE statement or subquery to determine `has_segmentation`:
     ```sql
     -- Add to main query:
     func.max(
         func.case(
             (DetectionItem.polygon.isnot(None), 1),
             else_=0
         )
     ).label("has_segmentation")
     ```
   - Join `DetectionItem` on `Detection.id = DetectionItem.detection_id` in main query
   - This eliminates N queries (where N = page_size)

2. **Optimize Total Count:**
   - Instead of `base_query.distinct().count()`, use a subquery approach:
     ```sql
     SELECT COUNT(*) FROM (
         SELECT DISTINCT processed_benches.id
         FROM processed_benches
         -- joins and filters
     )
     ```
   - Or better: Use `COUNT(DISTINCT processed_benches.id)` directly if indexes are in place

3. **Batch Load Detection Items:**
   - If `include_detection_data=True`, collect all `best_detection_id` values first
   - Execute a single query: `SELECT * FROM detection_items WHERE detection_id IN (...)`
   - Map results in Python instead of N separate queries

4. **Consider Using Subquery for Image Aggregation:**
   - Pre-compute image counts in a subquery to avoid large GROUP BY:
     ```sql
     SELECT
         pb.*,
         bc.*,
         d.*,
         img_counts.image_count,
         img_counts.image_filenames,
         img_counts.image_ids
     FROM processed_benches pb
     JOIN bench_candidates bc ON pb.bench_candidate_id = bc.id
     LEFT JOIN detections d ON pb.best_detection_id = d.id
     LEFT JOIN (
         SELECT
             bench_candidate_id,
             COUNT(DISTINCT id) as image_count,
             GROUP_CONCAT(DISTINCT filename) as image_filenames,
             GROUP_CONCAT(DISTINCT id) as image_ids
         FROM images
         WHERE capture_success = 1
         GROUP BY bench_candidate_id
     ) img_counts ON bc.id = img_counts.bench_candidate_id
     ```

### Phase 3: Advanced Optimizations

**Priority: MEDIUM** - Further improvements if needed after Phases 1-2.

1. **Add Materialized/Denormalized Fields:**
   - Add `image_count` column to `ProcessedBench` table (maintained via triggers or updates)
   - Add `has_segmentation` boolean to `Detection` table
   - This eliminates need for joins and aggregations in read queries

2. **Query Result Caching:**
   - Cache paginated results for common queries (e.g., first page with default filters)
   - Use Redis or in-memory cache with TTL
   - Invalidate on data updates

3. **Pagination Optimization:**
   - Consider cursor-based pagination instead of offset-based for large datasets
   - Use `WHERE id > last_id` instead of `OFFSET`

4. **Database Configuration:**
   - Enable SQLite WAL mode if not already: `PRAGMA journal_mode=WAL;`
   - Increase cache size: `PRAGMA cache_size = -10000;` (10MB)
   - Optimize query planner: `PRAGMA optimize;`

### Phase 4: Application-Level Optimizations

**Priority: LOW** - Nice to have improvements.

1. **Lazy Loading:**
   - Only load detection items when `include_detection_data=True`
   - Defer image filename loading until needed

2. **Response Compression:**
   - Enable gzip compression in FastAPI for large JSON responses

3. **Connection Pooling:**
   - Ensure SQLAlchemy connection pool is properly configured
   - Consider connection pooling if switching to PostgreSQL in future

## Implementation Order

1. **First**: Create all indexes from Phase 1 (will see immediate improvement)
2. **Second**: Implement Phase 2.1 (eliminate segmentation N+1 query)
3. **Third**: Implement Phase 2.3 (batch load detection items)
4. **Fourth**: Implement Phase 2.2 (optimize total count)
5. **Fifth**: Test performance and implement Phase 3 if needed

## Expected Performance Gains

- **Phase 1 (Indexes)**: 50-80% improvement in query time (from ~2-5s to ~0.5-1s)
- **Phase 2 (Query Optimization)**: Additional 30-50% improvement (from ~0.5-1s to ~0.2-0.5s)
- **Phase 3 (Advanced)**: Additional 20-30% if needed

**Target**: Reduce endpoint response time from current (likely 2-5 seconds) to < 500ms for typical queries.

## Testing Strategy

1. **Baseline Measurement:**
   - Measure current query time with EXPLAIN QUERY PLAN
   - Log slow queries (> 1s) before optimization

2. **After Each Phase:**
   - Re-run same queries and measure improvement
   - Verify indexes are being used: `EXPLAIN QUERY PLAN`
   - Test with various filter combinations

3. **Load Testing:**
   - Test with realistic data volumes
   - Test pagination performance on later pages
   - Test with `include_detection_data=True` vs `False`

## Notes

- SQLite has limitations compared to PostgreSQL (no partial indexes in older versions, no true spatial indexes)
- If performance is still insufficient after all optimizations, consider:
  - Migrating to PostgreSQL with PostGIS for spatial queries
  - Adding read replicas
  - Implementing more aggressive caching strategies
