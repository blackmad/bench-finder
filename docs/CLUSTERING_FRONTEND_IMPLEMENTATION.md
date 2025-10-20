# Clustering Frontend Implementation

## Overview

The frontend has been successfully updated to support and display clustered bench data. The implementation includes full support for both clustered and individual bench display modes, with automatic fallback and seamless integration.

## Changes Made

### 1. OpenAPI Schema Updates
- **File**: `openapi.json`
- **Changes**:
  - Added `clustered` parameter (boolean, default: true) to the `/api/benches/bbox` endpoint
  - Updated response schema to support union of `BboxBenchResponse` and `ClusteredBenchListResponse`
  - Added complete schema definitions for:
    - `ClusterInfo`: Cluster metadata
    - `ClusteredBenchData`: Individual cluster data with representative bench
    - `ClusteredBenchListResponse`: Paginated clustered response

### 2. API Client Regeneration
- **Action**: Regenerated TypeScript client using `npm run generate-api:local`
- **Result**: New types and API methods now include clustering support
- **New Types Generated**:
  - `ClusterInfo.ts`
  - `ClusteredBenchData.ts`
  - `ClusteredBenchListResponse.ts`

### 3. Frontend API Services Updates
- **Files**:
  - `src/services/api.ts`
  - `src/services/benchApi.ts`
- **Changes**:
  - Added `clustered?: boolean` parameter to `getBenchesInBbox` methods
  - Set `clustered: true` as default for map requests
  - Updated return types to handle union responses

### 4. MapView Component Enhancement
- **File**: `src/components/MapView/MapView.tsx`
- **Major Changes**:

#### New State Management
```typescript
interface MapData {
  type: 'individual' | 'clustered'
  benches?: Bench[]
  clusters?: ClusteredBenchData[]
  totalCount: number
  clusteringInfo?: Record<string, any>
}
```

#### Response Handling
- Detects response type automatically (`clustered_benches` vs `benches`)
- Handles both clustered and individual data seamlessly
- Preserves clustering metadata for display

#### Map Markers
- **Cluster markers**: Green circles with bench count, larger size (36px)
- **Individual markers**: Blue bench icons, standard size (28px)
- Different styling for selected state

#### Sidebar Updates
- Dynamic header: "Nearby Clusters" vs "Nearby Benches"
- Cluster cards show:
  - Bench count and representative bench info
  - Average confidence and data sources
  - Distance to cluster center
- Clustering status indicator when active

### 5. Visual Improvements
- **Cluster Markers**:
  - Green background with white number showing bench count
  - Larger size (32px) to distinguish from individual benches
  - Red highlight when selected
- **Cluster Cards**:
  - Display cluster statistics
  - Show representative bench image
  - Include source information and distance
- **Status Indicators**:
  - Shows clustering is active with distance parameter
  - Displays total bench count across all clusters

## How It Works

### 1. Request Flow
1. User moves map → triggers `searchMapArea`
2. API called with `clustered: true` by default
3. Backend returns either:
   - `ClusteredBenchListResponse` if clustering available
   - `BboxBenchResponse` if clustering unavailable/disabled

### 2. Response Processing
```typescript
if ('clustered_benches' in response) {
  // Handle clustered response
  setMapData({
    type: 'clustered',
    clusters: response.clustered_benches,
    totalCount: response.pagination?.total_count,
    clusteringInfo: response.clustering_info
  })
} else {
  // Handle individual response
  setMapData({
    type: 'individual',
    benches: response.benches,
    totalCount: response.total_count
  })
}
```

### 3. Rendering Logic
- Map renders different marker types based on `mapData.type`
- Sidebar content adapts to show cluster or individual bench cards
- Click handlers manage both `selectedClusterId` and `selectedBenchId`

## User Experience

### Benefits
- **Reduced Visual Clutter**: Maps now show fewer markers in dense areas
- **Better Performance**: Fewer DOM elements to render
- **Logical Grouping**: Related benches are visually combined
- **Preserved Functionality**: All individual bench data still accessible

### Visual Indicators
- **Green cluster markers** with bench count numbers
- **Blue individual bench** markers with chair emoji
- **Clustering status** shown in sidebar when active
- **Detailed cluster info** in popups and cards

### Interaction
- Click cluster markers to select and view cluster details
- Cluster cards show representative bench with full cluster metadata
- Seamless fallback to individual benches if clustering unavailable

## Testing

The implementation includes:
- **Type Safety**: Full TypeScript support with generated types
- **Error Handling**: Graceful fallback to individual benches on errors
- **Backward Compatibility**: Still works with non-clustered backends
- **Responsive Design**: Cluster UI adapts to mobile screens

## Backend Requirements

For clustering to work, the backend must:
1. Have clustering data available (run `python run_clustering.py`)
2. Support the `clustered=true` parameter on `/api/benches/bbox`
3. Return `ClusteredBenchListResponse` format when clustering is enabled

The frontend automatically detects and adapts to clustering availability.

## Future Enhancements

Potential improvements:
- Zoom-level dependent clustering (more granular at higher zoom)
- Cluster expansion on click (show individual benches in cluster)
- Custom clustering distance settings in UI
- Cluster filtering and search
