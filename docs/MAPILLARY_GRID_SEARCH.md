# Mapillary Grid Search Enhancement

## Overview

The `test_mapillary.py` script has been enhanced to handle large radius searches (> 100m) by methodically sampling across the search area using overlapping 100m radius sub-searches. This approach ensures comprehensive coverage while respecting any API limitations on individual search radius.

## How It Works

### 1. Automatic Detection
- When `radius > 100m`, the system automatically switches to grid sampling mode
- For `radius <= 100m`, it performs a single direct search as before

### 2. Grid Point Calculation
- Calculates a grid of overlapping circular search areas
- Uses 70% spacing of the sub-radius (70m spacing for 100m searches) to ensure good overlap
- Takes into account latitude effects on longitude distances using `cos(lat)` correction
- Filters grid points to only include those within the total target radius

### 3. Methodical Sampling
- Performs individual 100m radius searches at each grid point
- Shows progress through all sub-searches
- Handles individual sub-search failures gracefully
- Continues with remaining searches if some fail

### 4. Result Aggregation
- Merges results from all successful sub-searches
- Removes duplicate benches (by bench ID)
- Recalculates distances from the original center point
- Sorts final results by distance from original center
- Provides comprehensive statistics across all searches

## Key Features

### Geographic Accuracy
- Uses Haversine formula for accurate distance calculations
- Accounts for latitude effects on longitude spacing
- Ensures proper coverage of the target area

### Overlap Strategy
- 70% spacing ensures good overlap between adjacent searches
- Prevents gaps in coverage while minimizing redundant searches
- Adapts grid density to the total radius size

### Error Handling
- Individual sub-search failures don't stop the overall process
- Logs warnings for failed sub-searches
- Continues with remaining grid points

### Comprehensive Output
- Shows detailed progress for each sub-search
- Provides coverage analysis for large radius searches
- Displays statistics about search efficiency
- Shows closest/furthest/average distances from center

## Usage Examples

### Small Radius (Single Search)
```bash
python3 test_mapillary.py --token YOUR_TOKEN --lat 52.3676 --lng 4.9041 --radius 50
```
Output: Direct single search, same as before.

### Medium Radius (Grid Search)
```bash
python3 test_mapillary.py --token YOUR_TOKEN --lat 52.3676 --lng 4.9041 --radius 200
```
Output: ~25 grid points, comprehensive coverage.

### Large Radius (Extensive Grid)
```bash
python3 test_mapillary.py --token YOUR_TOKEN --lat 52.3676 --lng 4.9041 --radius 1000
```
Output: ~637 grid points, full area coverage.

## Grid Point Examples

| Radius | Grid Points | Coverage Strategy |
|--------|------------|-------------------|
| 50m    | 1          | Single direct search |
| 200m   | ~25        | 5x5 overlapping grid |
| 500m   | ~159       | Dense overlapping coverage |
| 1000m  | ~637       | Extensive grid sampling |

## Benefits

1. **Complete Coverage**: No gaps in large search areas
2. **API Compliance**: Each individual search uses <= 100m radius
3. **Deduplication**: Eliminates duplicate results from overlapping areas
4. **Progress Tracking**: Clear visibility into search progress
5. **Fault Tolerance**: Continues even if some sub-searches fail
6. **Accurate Distances**: All distances calculated from original center point

## Technical Details

### Grid Calculation Algorithm
1. Calculate spacing as 70% of sub-radius (70m for 100m searches)
2. Convert spacing to degrees with latitude correction
3. Generate rectangular grid within circular bounds
4. Filter points to only include those within target radius
5. Always include original center point

### Result Merging Process
1. Collect all successful search results
2. Track seen bench IDs to prevent duplicates
3. Recalculate distances from original center
4. Sort by distance from center
5. Generate merged statistics and pagination info

### Memory and Performance
- Processes results incrementally to manage memory
- Uses set-based deduplication for efficiency
- Logs progress to provide user feedback
- Scales appropriately with search area size

This enhancement makes the Mapillary testing tool much more capable for large-area searches while maintaining full compatibility with existing small-radius usage patterns.