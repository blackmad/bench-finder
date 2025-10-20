# Bench Clustering System

The bench clustering system de-duplicates nearby benches by grouping them into clusters based on geographic proximity. This reduces visual clutter in the interface while preserving access to individual bench data.

## Overview

The clustering system consists of several key components:

1. **Clustering Algorithm** (`clustering.py`) - Groups benches within a configurable distance
2. **Clustered Bench Service** (`clustered_bench_service.py`) - Serves clustered data through API endpoints
3. **API Integration** - Modified endpoints that serve clustered or individual bench data
4. **Database Schema** - New `clustered_benches` table to store cluster information

## How It Works

### Clustering Process

1. **Data Preparation**: All benches with confidence scores above a threshold are retrieved
2. **Greedy Clustering**: Starting with the highest confidence bench, nearby benches (within N meters) are grouped together
3. **Cluster Creation**: Each cluster stores:
   - Center coordinates (centroid of all benches)
   - List of bench IDs in the cluster
   - Representative bench (highest confidence)
   - Cluster metadata (radius, average confidence, sources)

### Distance Configuration

- **Default distance**: 5 meters
- **Configurable range**: 1-50 meters
- **Algorithm**: Haversine formula for accurate geographic distance

## Database Schema

### `clustered_benches` Table

```sql
CREATE TABLE clustered_benches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    center_lat REAL NOT NULL,
    center_lng REAL NOT NULL,
    bench_ids TEXT NOT NULL,  -- JSON array of bench IDs
    best_bench_id INTEGER NOT NULL,
    max_distance_meters REAL NOT NULL,
    bench_count INTEGER NOT NULL,
    avg_confidence REAL NOT NULL,
    sources TEXT NOT NULL,  -- JSON array of sources
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (best_bench_id) REFERENCES benches (id)
);
```

## API Changes

### Enhanced Endpoints

Both `/api/benches` and `/api/benches/bbox` now support clustering:

#### New Parameter
- `clustered: bool = True` - Enable/disable clustered responses

#### Response Types

**Individual Benches** (when `clustered=false` or clustering unavailable):
```json
{
  "benches": [...],
  "pagination": {...}
}
```

**Clustered Benches** (when `clustered=true` and available):
```json
{
  "clustered_benches": [
    {
      "cluster": {
        "cluster_id": 1,
        "center_lat": 52.361234,
        "center_lng": 4.866543,
        "bench_count": 3,
        "max_distance_meters": 4.2,
        "avg_confidence": 0.875,
        "sources": ["osm", "mapillary"]
      },
      "representative_bench": {...},
      "all_benches": [...],
      "distance_to_cluster_center": 1250.5
    }
  ],
  "pagination": {...},
  "clustering_info": {
    "clustering_enabled": true,
    "clustering_distance_meters": 5.0,
    "total_clusters": 156,
    "total_benches": 423
  }
}
```

### Backward Compatibility

- Existing API calls work unchanged (individual benches by default when clustering unavailable)
- All individual bench IDs remain valid for segmentation and other endpoints
- Frontend can opt into clustering by setting `clustered=true`

## Usage

### Running Clustering

```bash
# Run clustering with default settings (5m distance, 0.5 min confidence)
python run_clustering.py

# Just show statistics
python run_clustering.py stats

# Test the clustering service
python run_clustering.py test
```

### Programmatic Usage

```python
from clustering import BenchClusterer
from clustered_bench_service import ClusteredBenchService

# Run clustering
clusterer = BenchClusterer(cluster_distance_meters=5.0)
cluster_count = clusterer.cluster_all_benches(min_confidence=0.5)

# Serve clustered data
service = ClusteredBenchService()
result = service.get_clustered_benches_filtered(
    page=0,
    page_size=20,
    min_confidence=0.8,
    clustered=True
)
```

### Configuration

The clustering distance can be adjusted when creating the clusterer:

```python
# More aggressive clustering (larger distance)
clusterer = BenchClusterer(cluster_distance_meters=10.0)

# Conservative clustering (smaller distance)
clusterer = BenchClusterer(cluster_distance_meters=3.0)
```

## Benefits

### For End Users
- **Reduced Visual Clutter**: Map displays show fewer markers while preserving all data
- **Better Performance**: Fewer data points to render and process
- **Logical Grouping**: Related benches (e.g., multiple benches in a park) are grouped together

### For Developers
- **API Flexibility**: Choose between clustered or individual data per request
- **Backward Compatibility**: Existing code continues to work
- **Rich Metadata**: Cluster information provides additional context

### For System Performance
- **Efficient Queries**: Clustered data reduces database load for map displays
- **Scalable**: Algorithm handles large datasets efficiently
- **Configurable**: Distance threshold can be tuned for different use cases

## Implementation Details

### Clustering Algorithm

The system uses a greedy clustering approach:

1. Sort all benches by confidence (descending)
2. For each unclustered bench:
   - Start a new cluster with this bench as seed
   - Find all nearby unclustered benches within the distance threshold
   - Add them to the current cluster
   - Continue until all benches are processed

### Performance Considerations

- **Memory Usage**: Algorithm loads all bench data into memory for clustering
- **Time Complexity**: O(n²) in worst case, but typically much faster due to spatial locality
- **Database Impact**: Clustering is run offline; serving is very efficient

### Error Handling

- **Graceful Degradation**: Falls back to individual benches if clustering fails
- **Validation**: Distance thresholds are validated and clamped to safe ranges
- **Logging**: Comprehensive logging for debugging and monitoring

## Future Enhancements

### Incremental Clustering
Currently, clustering rebuilds all clusters when new benches are added. Future versions could support incremental updates.

### Advanced Algorithms
More sophisticated clustering algorithms (DBSCAN, k-means) could be implemented for specific use cases.

### Spatial Indexing
For very large datasets, spatial indexing (R-tree, Quadtree) could improve performance.

### Multi-level Clustering
Hierarchical clustering could provide different zoom-level appropriate groupings.

## Troubleshooting

### Common Issues

**No clustering data available**
```bash
# Run clustering first
python run_clustering.py cluster
```

**Clustering seems too aggressive/conservative**
```python
# Adjust distance threshold
clusterer = BenchClusterer(cluster_distance_meters=3.0)  # Conservative
clusterer = BenchClusterer(cluster_distance_meters=10.0)  # Aggressive
```

**Poor performance**
```python
# Increase minimum confidence to reduce data size
clusterer.cluster_all_benches(min_confidence=0.8)
```

### Debugging

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check clustering statistics:
```bash
python run_clustering.py stats
```

## Migration Guide

### For Existing Applications

1. **No immediate changes required** - clustering is opt-in via `clustered=true` parameter
2. **To enable clustering**:
   ```bash
   # Run clustering first
   python run_clustering.py

   # Update API calls to use clustered=true
   curl "/api/benches?clustered=true"
   ```

3. **Frontend updates**:
   - Handle both response formats (individual vs clustered)
   - Display cluster information appropriately
   - Provide access to all benches in a cluster when needed

### For New Applications

- Use `clustered=true` by default for map displays
- Fall back to individual benches for detailed views
- Leverage cluster metadata for enhanced user experience

## API Examples

### Get Clustered Benches
```bash
curl "http://localhost:8000/api/benches?clustered=true&min_confidence=0.8&page_size=10"
```

### Get Individual Benches
```bash
curl "http://localhost:8000/api/benches?clustered=false&min_confidence=0.8&page_size=10"
```

### Bounding Box with Clustering
```bash
curl "http://localhost:8000/api/benches/bbox?north=52.4&south=52.3&east=4.9&west=4.8&clustered=true"
```

### Check Clustering Status
```bash
curl "http://localhost:8000/api/benches?page_size=1&clustered=true" | jq .clustering_info
```
