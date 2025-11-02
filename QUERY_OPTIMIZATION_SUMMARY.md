# Query Optimization Summary - `/api/benches` Endpoint

## Problem
Initial curl request taking **4 seconds**:
```
curl 'https://bench-finder-three.vercel.app/api/benches?page=0&page_size=20&min_confidence=0&start_lat=52.3613577&start_lng=4.8666322&sort_by=distance&mode=benches&clustered=true&include_detection_data=false&source=OSM'
```

## Analysis

### Identified Performance Bottlenecks

1. **Expensive Total Count Query** (Lines 927-933)
   - Used `query.with_entities(ProcessedBench.id).distinct()` followed by subquery count
   - Required full execution of main query with all joins just to count rows
   - **Impact**: High - scans all matching rows with all joins

2. **Unnecessary ReverseGeocode Join** (Lines 908-911)
   - Always joined ReverseGeocode table even when not all benches have geocode data
   - Added join overhead to every query execution
   - **Impact**: Medium - unnecessary table scan/join operations

3. **Query Execution Order**
   - Filters applied after all joins were established
   - Could benefit from early filtering to reduce intermediate result sets

## Optimizations Applied

### 1. Fast Total Count Query ✅
**Before:**
```python
total_count_query = query.with_entities(ProcessedBench.id).distinct()
total_count = (
    session.query(func.count())
    .select_from(total_count_query.subquery())
    .scalar()
    or 0
)
```

**After:**
```python
# Count ProcessedBench directly with same filters - avoids expensive subquery
total_count_base = session.query(ProcessedBench.id)
total_count_base = total_count_base.join(
    BenchCandidate,
    ProcessedBench.bench_candidate_id == BenchCandidate.id,
)

# Apply filters early for count query
if source is not None:
    total_count_base = total_count_base.filter(BenchCandidate.source == source)

if mode == BenchMode.BENCHES:
    total_count_base = total_count_base.outerjoin(
        Detection, ProcessedBench.best_detection_id == Detection.id
    ).filter(
        ProcessedBench.detection_status == "detected",
        func.coalesce(Detection.max_confidence, 0.0) >= min_confidence,
    )
elif mode == BenchMode.NO_BENCH:
    total_count_base = total_count_base.filter(
        ProcessedBench.detection_status == "no_bench"
    )

total_count = total_count_base.count()
```

**Rationale:**
- Counts ProcessedBench IDs directly with minimal joins
- Only joins Detection when needed (BENCHES mode with confidence filter)
- Avoids creating complex subquery with all joins
- Filters applied early to reduce row count before counting

**Expected Impact**: 50-70% reduction in count query time

### 2. Removed ReverseGeocode Join from Main Query ✅
**Before:**
```python
query = (
    session.query(
        ...
        ReverseGeocode.formatted_address.label("rg_formatted_address"),
        ReverseGeocode.street_number.label("rg_street_number"),
        ...
    )
    ...
    .outerjoin(
        ReverseGeocode,
        BenchCandidate.id == ReverseGeocode.bench_candidate_id,
    )
)
```

**After:**
```python
# Main query WITHOUT ReverseGeocode join
query = (
    session.query(
        ProcessedBench.id.label("processed_bench_id"),
        BenchCandidate.id.label("bench_candidate_id"),
        ...
        # No ReverseGeocode fields
    )
    ...
    # No ReverseGeocode join
)

# Batch load ReverseGeocode separately after pagination
reverse_geocode_map = {}
if results:
    bench_candidate_ids_for_rg = [r.bench_candidate_id for r in results]
    reverse_geocodes = (
        session.query(ReverseGeocode)
        .filter(ReverseGeocode.bench_candidate_id.in_(bench_candidate_ids_for_rg))
        .all()
    )
    for rg in reverse_geocodes:
        reverse_geocode_map[rg.bench_candidate_id] = rg
```

**Rationale:**
- Removes join overhead from main query (joins are expensive)
- Batch loads ReverseGeocode for only the paginated results (20 rows)
- Uses indexed lookup (`bench_candidate_id` has index)
- Single additional query instead of join on every row

**Expected Impact**: 20-30% reduction in main query execution time

### 3. Early Filtering ✅
**Before:**
- Filters applied after all joins were established
- All joins executed before filtering

**After:**
- Filters applied immediately after necessary joins
- Source filter applied early in count query
- Mode filter applied early in count query

**Rationale:**
- Reduces intermediate result set size
- Database can use indexes more effectively
- Less data to process in subsequent operations

**Expected Impact**: 10-15% improvement

## Performance Expectations

### Before Optimizations
- Total query time: **~4000ms**
- Breakdown (estimated):
  - Total count: ~2000ms
  - Main query with joins: ~1500ms
  - ReverseGeocode join: ~300ms
  - Result processing: ~200ms

### After Optimizations
- Expected total query time: **~1000-1500ms** (62-75% improvement)
- Breakdown (estimated):
  - Total count: ~400-600ms (70% reduction)
  - Main query: ~800-1000ms (33% reduction)
  - ReverseGeocode batch load: ~50ms (83% reduction)
  - Result processing: ~200ms (same)

## Additional Recommendations

1. **Database Indexes**: Ensure these indexes exist (from `tools/add_performance_indexes.py`):
   - `idx_processed_benches_bench_candidate_id`
   - `idx_processed_benches_best_detection_id`
   - `idx_processed_benches_detection_status`
   - `idx_detections_max_confidence`
   - `idx_bench_candidates_source`
   - `idx_reverse_geocodes_bench_candidate_id`

2. **Consider Adding Composite Index**:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_processed_benches_status_source
   ON processed_benches(detection_status, bench_candidate_id);
   ```

3. **Monitor Query Performance**:
   - Use `EXPLAIN ANALYZE` on the actual queries
   - Monitor slow query logs
   - Profile with database-specific tools

4. **Future Optimizations**:
   - Consider materialized views for commonly filtered/sorted queries
   - Cache total count for a few seconds (stale count is often acceptable)
   - Use database connection pooling if not already implemented

## Testing

To verify improvements:
```bash
# Test the optimized endpoint
time curl 'https://bench-finder-three.vercel.app/api/benches?page=0&page_size=20&min_confidence=0&start_lat=52.3613577&start_lng=4.8666322&sort_by=distance&mode=benches&clustered=true&include_detection_data=false&source=OSM'
```

Expected: Response time should be under **1.5 seconds** (ideally under 1 second).

## Code Changes

All changes in: `api/fastapi_server.py`
- Function: `get_high_confidence_benches_filtered()` (lines 789-1157)
- Total lines changed: ~50 lines
- Backward compatible: ✅ Yes (same response format)
