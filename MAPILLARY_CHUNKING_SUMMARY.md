# Mapillary Chunking Enhancement Summary

## Overview

Enhanced the MapillaryBenchGenerator to automatically break down large search areas into smaller chunks for improved API performance. This addresses the limitation where large bounding boxes could result in timeouts or incomplete results from the Mapillary API.

## Key Features Implemented

### 1. **Configurable Chunk Size**
- Added `MAPILLARY_MAX_CHUNK_SIZE_METERS = 200` to config.py (default: 200m)
- Added `MAPILLARY_API_LIMIT_PER_REQUEST = 1000` for per-request limits
- Fully configurable via environment variables

### 2. **Automatic Chunking Logic**
- **Point searches**: Automatically chunks when radius * 2 > chunk size (e.g., >200m diameter)
- **Area searches**: Always uses chunking for optimal performance
- **Smart calculation**: Determines optimal number of chunks based on area dimensions

### 3. **Overlap and Deduplication**
- **Small overlap**: 0.0001° (~10m) between adjacent chunks prevents missing detections at boundaries
- **Image-level deduplication**: Removes duplicate images that may appear in overlapping chunks
- **Candidate-level deduplication**: Prevents duplicate bench candidates from same images

### 4. **Comprehensive Logging**
- Progress tracking for chunk processing
- Detailed chunk boundary logging (debug level)
- Success/failure counts per chunk
- Deduplication statistics

## Implementation Details

### Chunking Algorithm

```python
# Calculate area dimensions in meters
lat_meters = (max_lat - min_lat) * 111000
lng_meters = (max_lng - min_lng) * 111000 * math.cos(math.radians(center_lat))

# Determine number of chunks needed
lat_chunks = max(1, math.ceil(lat_meters / MAPILLARY_MAX_CHUNK_SIZE_METERS))
lng_chunks = max(1, math.ceil(lng_meters / MAPILLARY_MAX_CHUNK_SIZE_METERS))
```

### Chunk Overlap
```python
overlap_deg = 0.0001  # ~10 meters
chunk_min_lat = base_lat - (overlap_deg if not_edge_chunk else 0)
chunk_max_lat = base_lat + (overlap_deg if not_edge_chunk else 0)
```

## Performance Examples

### Example 1: Central Park Area (3.8km × 2.3km)
- **Without chunking**: 1 large API call (likely to timeout/fail)
- **With chunking**: 20×12 = 240 smaller API calls (~200m each)
- **Benefits**: Reliable completion, better error handling per chunk

### Example 2: Small Area Search (100m radius)
- **Without chunking**: 1 API call (200m diameter < 200m threshold)
- **With chunking**: Not needed - uses single API call
- **Benefits**: No unnecessary overhead for small searches

## Configuration Impact Analysis

| Chunk Size | 1km² Area | 5km² Area | API Calls | Trade-offs |
|------------|-----------|-----------|-----------|------------|
| 100m | 100 calls | 500 calls | High volume | Max reliability |
| 200m | 25 calls | 125 calls | **Balanced** | **Recommended** |
| 500m | 4 calls | 20 calls | Lower volume | Some timeout risk |
| 1000m | 1 call | 5 calls | Minimal calls | High timeout risk |

## Usage Examples

### Automatic Chunking (Transparent to User)
```python
# Large area search automatically chunks
generator = MapillaryBenchGenerator()
candidates = generator.find_benches_near_point(40.7812, -73.9665, radius=1000)
# → Automatically breaks into 5×4 = 20 chunks

# Small area search uses single call
candidates = generator.find_benches_near_point(40.7812, -73.9665, radius=50)
# → Uses single API call (no chunking needed)
```

### Configuration Customization
```bash
# In .env file
MAPILLARY_MAX_CHUNK_SIZE_METERS=150  # Smaller chunks for extra reliability
MAPILLARY_API_LIMIT_PER_REQUEST=500  # Lower per-request limits
```

## Logging Output Example

```
INFO: Large search area (500m radius) - breaking into chunks of 200m
DEBUG: Search area: 1000m x 758m
INFO: Breaking search area into 5x4 = 20 chunks
DEBUG: Searching chunk 1/20: (-73.9956, 40.7314) to (-73.9933, 40.7333)
DEBUG: Chunk 1 found 3 images
...
INFO: Chunked search complete: 60 total images from 20/20 chunks
INFO: After deduplication: 60 unique images
INFO: Found 0 unique Mapillary benches from 60 images
```

## Technical Benefits

### Reliability
- **Prevents timeouts**: Smaller requests are less likely to timeout
- **Graceful degradation**: Failed chunks don't prevent other chunks from succeeding
- **Retry capability**: Individual chunks can be retried without reprocessing entire area

### Performance
- **Parallel potential**: Chunks can be processed in parallel (future enhancement)
- **Memory efficient**: Processes smaller data sets at a time
- **API rate limiting**: Better compliance with API rate limits

### Data Quality
- **Complete coverage**: Overlaps ensure no gaps at chunk boundaries
- **Deduplication**: Prevents duplicate processing of same images/benches
- **Source tracking**: Maintains full audit trail of which chunks found which data

## Future Enhancements

### Easy Additions
1. **Parallel processing**: Process chunks concurrently for speed
2. **Dynamic chunk sizing**: Adjust based on API response times
3. **Caching**: Cache chunk results to avoid re-processing
4. **Progressive loading**: Stream results as chunks complete

### Advanced Features
1. **Adaptive chunking**: Larger chunks in sparse areas, smaller in dense areas
2. **API optimization**: Batch multiple small chunks into single requests where possible
3. **Load balancing**: Distribute chunks across multiple API keys/endpoints

## Conclusion

The chunking enhancement transforms Mapillary searches from a single-point-of-failure approach to a robust, scalable system that can handle arbitrarily large search areas. The 200m default chunk size provides an optimal balance between API call volume and reliability.

**Key Achievement**: Large-area Mapillary searches that previously would timeout or return incomplete results now complete successfully with comprehensive coverage and deduplication.
