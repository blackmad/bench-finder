# Spatial Indexing for Bounding Box Queries

## Overview

This document describes the spatial indexing optimizations implemented to improve bounding box (bbox) query performance in the bench finder application.

## Problem

The `/api/benches/bbox` endpoint was slow because it was performing full table scans when filtering benches by geographic bounding boxes. SQLite's default B-tree indexes don't efficiently handle spatial range queries like `lat BETWEEN ... AND lng BETWEEN ...`.

## Solution

We've implemented a two-tier optimization approach:

1. **Enhanced Regular Indexes**: Added separate indexes on `lat` and `lng` columns for better BETWEEN query performance
2. **R-tree Spatial Index**: Created an R-tree virtual table for optimal spatial queries (best performance)

## SQLite R-tree Support

SQLite has built-in support for R-tree spatial indexing via virtual tables. R-trees are specifically designed for spatial queries and provide excellent performance for bounding box searches.

**Note**: R-tree support is built into SQLite by default - no extensions needed!

## Implementation

### 1. Enhanced Regular Indexes

Updated `tools/add_performance_indexes.py` to include:
- `idx_bench_candidates_lat` - Single-column index on latitude
- `idx_bench_candidates_lng` - Single-column index on longitude

These allow SQLite to efficiently use both indexes when filtering with `lat BETWEEN ... AND lng BETWEEN ...`.

### 2. R-tree Spatial Index

Created `tools/add_rtree_spatial_index.py` which:
- Creates an R-tree virtual table `rtree_bench_candidates`
- Stores bounding boxes for each bench (minLng, maxLng, minLat, maxLat)
- Populates the index with existing data
- Creates triggers to automatically maintain the index when benches are inserted/updated/deleted

### 3. Query Optimization

Modified `api/fastapi_server.py`:
- Added `_get_bbox_filtered_bench_candidate_ids()` helper function
- Detects if R-tree index is available
- Uses R-tree for fast spatial filtering when available
- Falls back to regular BETWEEN filters if R-tree is not available

## Usage

### Setting Up Indexes

1. **Run the regular index migration** (adds lat/lng indexes):
   ```bash
   python tools/add_performance_indexes.py
   ```

2. **Set up R-tree spatial index** (recommended for best performance):
   ```bash
   python tools/add_rtree_spatial_index.py
   ```

### How It Works

The bbox query endpoint automatically detects if R-tree is available:
- **If R-tree exists**: Uses R-tree to quickly find bench IDs within the bounding box, then joins to other tables
- **If R-tree doesn't exist**: Falls back to regular `BETWEEN` filters using the lat/lng indexes

This provides backward compatibility - the endpoint works either way, but with R-tree it's much faster.

## Performance Expectations

- **Without R-tree**: Bbox queries scan both lat and lng indexes, then intersect results. Performance depends on data distribution.
- **With R-tree**: Bbox queries use spatial indexing for logarithmic-time lookups. Expected 10-100x performance improvement for large datasets.

## Maintenance

The R-tree index is automatically maintained via triggers:
- `rtree_bench_candidates_insert` - Adds new benches to R-tree
- `rtree_bench_candidates_update` - Updates R-tree when lat/lng changes
- `rtree_bench_candidates_delete` - Removes deleted benches from R-tree

No manual maintenance required!

## R-tree Table Structure

```sql
CREATE VIRTUAL TABLE rtree_bench_candidates USING rtree(
    id,              -- Integer primary key (links to bench_candidates.id)
    minLng, maxLng,  -- Longitude bounds (X coordinate)
    minLat, maxLat   -- Latitude bounds (Y coordinate)
);
```

For point data (single lat/lng), min and max values are the same.

## Notes

- R-tree indexes are virtual tables stored separately from the main database
- They don't affect existing queries unless explicitly used
- The implementation gracefully degrades if R-tree is not available
- R-tree is ideal for datasets with > 1000 benches, but beneficial for smaller datasets too
