# Unified Client System

This document describes the unified client system that provides a common interface for searching bench data from multiple sources (OSM Overpass and Mapillary).

## Overview

The unified system consists of:

1. **BaseLocationClient** - Abstract base class for location-based search clients
2. **UnifiedBench** - Common model for bench data from any source
3. **UnifiedSearchResult** - Common model for search results
4. **CombinedSearchResult** - Model for combining results from multiple sources
5. **Unified CLI Tool** - Command-line interface for testing both clients

## Architecture

### Base Classes

#### BaseLocationClient
Located in `bench_finder/clients/base_location_client.py`

Abstract base class that defines the common interface for location-based search clients:

```python
class BaseLocationClient(ABC):
    def search_near_point(self, lat: float, lng: float, radius: int = 1000) -> LocationSearchResult
    def get_item_details(self, provider_id: str) -> Optional[dict]
    def validate_coordinates(self, lat: float, lng: float) -> bool
    def calculate_distance_meters(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float
```

### Unified Models

#### UnifiedBench
Located in `bench_finder/models/unified_models.py`

Common model that can represent bench data from any source:

```python
class UnifiedBench(BaseModel):
    provider_id: str
    source: str  # 'osm' or 'mapillary'
    external_id: str
    lat: float
    lng: float
    tags: UnifiedBenchTags
    confidence: Optional[float]
    created_at: Optional[datetime]
    # Source-specific fields
    osm_type: Optional[str]
    osm_id: Optional[int]
    image_id: Optional[str]
    detection_id: Optional[str]
```

#### UnifiedSearchResult
Common model for search results from any source:

```python
class UnifiedSearchResult(BaseModel):
    benches: List[UnifiedBench]
    search_center_lat: float
    search_center_lng: float
    search_radius_meters: int
    total_count: int
    source: str
    search_timestamp: datetime
    processing_time_ms: Optional[float]
```

#### CombinedSearchResult
Model for combining results from multiple sources:

```python
class CombinedSearchResult(BaseModel):
    osm_result: Optional[UnifiedSearchResult]
    mapillary_result: Optional[UnifiedSearchResult]
    combined_result: UnifiedSearchResult
    # Statistics
    total_benches: int
    osm_benches: int
    mapillary_benches: int
    unique_locations: int
```

## Client Implementations

### OverpassClient
Located in `bench_finder/clients/overpass_client.py`

Now inherits from `BaseLocationClient` and provides:

- `search_near_point()` - Implements base class interface
- `search_near_point_unified()` - Returns `UnifiedSearchResult`
- `find_benches_near_point()` - Original method (backward compatibility)
- `get_item_details()` - Implements base class interface

### MapillaryBenchDetector
Located in `bench_finder/clients/mapillary_client.py`

Now inherits from `BaseLocationClient` and provides:

- `search_near_point()` - Implements base class interface
- `search_near_point_unified()` - Returns `UnifiedSearchResult`
- `search_benches_by_location()` - Original method (backward compatibility)
- `get_item_details()` - Implements base class interface

## CLI Tool

### Unified Bench Search CLI
Located in `tools/unified_bench_search_cli.py`

Command-line tool for testing both clients with a unified interface.

#### Usage

```bash
# Search with default coordinates (40.74, -74.0 - New York area)
./bin/unified_bench_search

# Search with custom coordinates
./bin/unified_bench_search --coordinates "40.7589,-73.9851"

# Search with custom radius
./bin/unified_bench_search --radius 500

# Search only OSM (no Mapillary token needed)
./bin/unified_bench_search --osm-only

# Search only Mapillary
./bin/unified_bench_search --mapillary-only --mapillary-token YOUR_TOKEN

# Enable verbose logging
./bin/unified_bench_search --verbose
```

#### Features

- **Unified Interface**: Single command to search both OSM and Mapillary
- **Flexible Configuration**: Custom coordinates, radius, and source selection
- **Rich Output**: Detailed results with statistics and formatting
- **Error Handling**: Graceful handling of API failures
- **Performance Metrics**: Processing time tracking
- **Backward Compatibility**: Original client methods still work

## Example Output

```
================================================================================
🎯 UNIFIED BENCH SEARCH RESULTS
================================================================================
📍 Search Center: 40.740000, -74.000000
📏 Search Radius: 1,000 meters
🕒 Search Time: 2025-10-08 17:59:27

📊 SUMMARY:
   Total Benches Found: 197
   OSM Benches: 197
   Mapillary Benches: 0
   Unique Locations: 124
   Sources Available: osm

🗺️  OSM OVERPASS RESULTS (197 benches):
------------------------------------------------------------
    1. 2477769419_node | 40.735403, -73.990313
       Backrest: yes

    2. 3522432744_node | 40.734603, -73.999527
       Backrest: yes
   ...

🔄 COMBINED RESULTS:
------------------------------------------------------------
   Total unique bench locations: 124
   Data sources: osm

   Sample combined results (first 5):
   1. [OSM] 2477769419_node | 40.735403, -73.990313
   2. [OSM] 3522432744_node | 40.734603, -73.999527
   ...
```

## Benefits

1. **Code Reuse**: Common interface reduces duplication
2. **Type Safety**: Pydantic models provide validation and type hints
3. **Extensibility**: Easy to add new data sources
4. **Consistency**: Unified data models across sources
5. **Testing**: Single CLI tool for testing all sources
6. **Performance**: Built-in timing and statistics
7. **Maintainability**: Clear separation of concerns

## Future Enhancements

1. **Additional Sources**: Easy to add new data sources (Google Places, Foursquare, etc.)
2. **Caching**: Add caching layer for improved performance
3. **Rate Limiting**: Built-in rate limiting for API calls
4. **Batch Processing**: Support for batch searches
5. **Data Export**: Export results to various formats (JSON, CSV, GeoJSON)
6. **Visualization**: Integration with mapping libraries
7. **Web Interface**: Web-based interface for the unified system

## Migration Guide

### For Existing Code

The unified system is backward compatible. Existing code using the original client methods will continue to work:

```python
# Old way (still works)
client = OverpassClient()
result = client.find_benches_near_point(lat, lng, radius)

# New unified way
client = OverpassClient()
result = client.search_near_point_unified(lat, lng, radius)
```

### For New Code

Use the unified interface for better consistency and type safety:

```python
from clients.overpass_client import OverpassClient
from clients.mapillary_client import MapillaryBenchDetector
from models.unified_models import CombinedSearchResult

# Search both sources
osm_client = OverpassClient()
mapillary_client = MapillaryBenchDetector(access_token)

osm_result = osm_client.search_near_point_unified(lat, lng, radius)
mapillary_result = mapillary_client.search_near_point_unified(lat, lng, radius)

# Combine results
combined = CombinedSearchResult.from_individual_results(
    osm_result=osm_result,
    mapillary_result=mapillary_result,
    search_center_lat=lat,
    search_center_lng=lng,
    search_radius_meters=radius
)
```
