# React Frontend OpenAPI Integration Guide

## Overview

The React frontend now automatically generates TypeScript types and API client code from the FastAPI server's OpenAPI specification. This provides:

- ✅ **Type Safety** - All API calls are fully typed
- ✅ **Auto-Completion** - IntelliSense support in your IDE
- ✅ **Error Prevention** - Compile-time checking for API parameter mismatches
- ✅ **Documentation** - Inline documentation from OpenAPI specs
- ✅ **Automatic Updates** - Client code stays in sync with backend changes

## Quick Start

### 1. Generate API Client Code

```bash
# Generate from running FastAPI server (recommended for production)
npm run generate-api

# Or generate from local schema file (for development)
npm run generate-schema

# Start development with fresh API types
npm run dev:with-api
```

### 2. Use the New API Service

Replace your old API calls with the new type-safe client:

```typescript
// OLD (manual axios calls)
import { api } from './services/api'

const response = await api.get('/api/benches', {
  params: { page: 0, min_confidence: 0.8 }
})

// NEW (type-safe generated client)
import { benchApi } from './services/benchApi'

const response = await benchApi.getBenches({
  page: 0,
  minConfidence: 0.8
})
```

## Generated API Structure

The code generator creates the following structure:

```
src/api/
├── index.ts                     # Main exports and types
├── BenchFinderApi.ts           # Main API client class
├── core/                       # HTTP client and utilities
│   ├── ApiError.ts
│   ├── ApiRequestOptions.ts
│   ├── AxiosHttpRequest.ts
│   └── OpenAPI.ts
├── models/                     # TypeScript types for all data models
│   ├── BenchListResponse.ts
│   ├── WebBenchData.ts
│   ├── PaginationInfo.ts
│   └── ...
└── services/                   # Service classes for each API group
    ├── BenchesService.ts       # /api/benches endpoints
    ├── ImagesService.ts        # /api/images endpoints
    ├── MapillaryService.ts     # /api/mapillary endpoints
    ├── SearchService.ts        # /api/searches endpoints
    ├── ConfigService.ts        # /api/config endpoints
    └── StatisticsService.ts    # /api/statistics endpoints
```

## Usage Examples

### Basic Bench Queries

```typescript
import { benchApi } from './services/benchApi'

// Get first page of benches
const benches = await benchApi.getBenches({
  page: 0,
  pageSize: 20,
  minConfidence: 0.8,
  sortBy: 'distance'
})

// Get benches from specific source
const osmBenches = await benchApi.getBenchesBySource('osm', {
  page: 0,
  minConfidence: 0.9
})

// Get random bench for discovery
const randomBench = await benchApi.getRandomBench({
  minConfidence: 0.8,
  source: 'mapillary'
})
```

### Map Integration

```typescript
// Get benches within map viewport
const bboxBenches = await benchApi.getBenchesInBbox({
  north: 52.4,
  south: 52.3,
  east: 4.9,
  west: 4.8,
  minConfidence: 0.8,
  limit: 500
})

// The response is fully typed
console.log(`Found ${bboxBenches.total_count} benches`)
bboxBenches.benches.forEach(bench => {
  console.log(`Bench ${bench.id} at ${bench.lat}, ${bench.lng}`)
})
```

### Image and Detection Data

```typescript
// Get segmentation data for visualization
const segmentationData = await benchApi.getImageSegmentation(123)

// Get all images for a bench
const benchImages = await benchApi.getBenchImages(456)

// All with full TypeScript support
if (segmentationData.segmentation_available) {
  console.log(`Image has ${segmentationData.bench_detections.length} detections`)
}
```

### React Query Integration

The API client works seamlessly with React Query:

```typescript
import { useQuery } from '@tanstack/react-query'
import { benchApi } from './services/benchApi'

function BenchList({ filters }: { filters: AppFilters }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['benches', filters],
    queryFn: () => benchApi.getBenches({
      minConfidence: filters.minConfidence,
      startLat: filters.startLat,
      startLng: filters.startLng,
      sortBy: filters.sortBy
    })
  })

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error: {error.message}</div>

  return (
    <div>
      {data?.benches.map(bench => (
        <div key={bench.id}>
          <h3>Bench {bench.id}</h3>
          <p>Confidence: {bench.best_confidence}</p>
          <p>Source: {bench.source}</p>
        </div>
      ))}
    </div>
  )
}
```

### Error Handling

The generated client includes proper error typing:

```typescript
import { ApiError } from './api'

try {
  const bench = await benchApi.getRandomBench()
} catch (error) {
  if (error instanceof ApiError) {
    console.error('API Error:', error.status, error.message)
    // error.body contains the full error response
  } else {
    console.error('Network Error:', error)
  }
}
```

## Available Scripts

| Script | Description | Use Case |
|--------|-------------|----------|
| `npm run generate-api` | Generate from running FastAPI server | When backend is running on localhost:8866 |
| `npm run generate-schema` | Export schema + generate client | Full regeneration from FastAPI code |
| `npm run dev:with-api` | Generate + start dev server | Development with fresh API types |
| `npm run build:with-api` | Generate + build for production | Production builds with latest API |

## Development Workflow

### Method 1: Live Server Integration
```bash
# Terminal 1: Start FastAPI server
cd /Users/blackmad/bench_finder
source venv/bin/activate
python3 -m uvicorn fastapi_server:app --reload --host 0.0.0.0 --port 8866

# Terminal 2: Generate and start frontend
cd frontend
npm run dev:with-api
```

### Method 2: Schema File Generation
```bash
# Generate schema without running full server
npm run generate-schema

# Then start development normally
npm run dev
```

## Type Safety Benefits

### Before (Manual Types)
```typescript
// Old manual typing - prone to errors
interface BenchResponse {
  benches: any[]  // Not specific enough
  pagination: any // Missing validation
}

const response = await api.get('/api/benches')
const data = response.data as BenchResponse  // Manual casting
```

### After (Generated Types)
```typescript
// New auto-generated types - fully validated
import type { BenchListResponse, WebBenchData } from './api'

const response: BenchListResponse = await benchApi.getBenches()
// Full IntelliSense support:
// - response.benches[0]. will show all WebBenchData properties
// - response.pagination. will show all PaginationInfo properties
// - Type errors caught at compile time
```

## Migrating Existing Code

### 1. Replace API Service Imports

```typescript
// OLD
import benchApi from './services/api'

// NEW
import { benchApi } from './services/benchApi'
```

### 2. Update Method Names

```typescript
// OLD
const benches = await benchApi.getBenches({ page: 0 })

// NEW (same interface, better types)
const benches = await benchApi.getBenches({ page: 0 })
```

### 3. Use Generated Types

```typescript
// OLD
import type { Bench, BenchListResponse } from '../types'

// NEW
import type { WebBenchData, BenchListResponse } from '../api'
```

## Configuration

### OpenAPI Client Configuration

The client is configured in `src/services/benchApi.ts`:

```typescript
import { OpenAPI } from '../api'

// Configure base URL (empty for relative URLs in development)
OpenAPI.BASE = ''

// Configure credentials
OpenAPI.WITH_CREDENTIALS = false
OpenAPI.CREDENTIALS = 'same-origin'

// Configure headers (if needed)
OpenAPI.HEADERS = {
  'Authorization': 'Bearer your-token'
}
```

### Vite Proxy Configuration

Make sure your `vite.config.ts` proxies API requests to the FastAPI server:

```typescript
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8866',
      '/health': 'http://localhost:8866',
      '/images': 'http://localhost:8866'
    }
  }
})
```

## Troubleshooting

### Common Issues

#### 1. "Module not found: './api'"
**Solution**: Run `npm run generate-api` to create the API client files.

#### 2. "Property does not exist on type"
**Solution**: Regenerate the API client after backend changes:
```bash
npm run generate-schema
```

#### 3. "Network Error" during API calls
**Solution**: Check that the Vite proxy is configured correctly and the FastAPI server is running.

#### 4. Types are outdated
**Solution**: Always regenerate when the FastAPI server changes:
```bash
# During development
npm run generate-schema

# Or if FastAPI server is running
npm run generate-api
```

### Debugging API Calls

Enable request logging:

```typescript
import { OpenAPI } from './api'

// Enable debugging
OpenAPI.WITH_CREDENTIALS = true

// Add request interceptor
OpenAPI.interceptors.request.use((config) => {
  console.log('API Request:', config)
  return config
})
```

## Best Practices

### 1. Always Regenerate After Backend Changes
- Add `npm run generate-schema` to your development workflow
- Consider adding it to CI/CD pipelines

### 2. Use TypeScript Strict Mode
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true
  }
}
```

### 3. Handle Loading States
```typescript
const { data, isLoading, error } = useQuery({
  queryKey: ['benches'],
  queryFn: () => benchApi.getBenches()
})

if (isLoading) return <LoadingSpinner />
if (error) return <ErrorMessage error={error} />
if (!data) return null

// Now data is guaranteed to be defined
return <BenchList benches={data.benches} />
```

### 4. Use Error Boundaries
```typescript
import { ApiError } from './api'

function ErrorBoundary({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary
      fallbackRender={({ error }) => (
        <div>
          {error instanceof ApiError
            ? `API Error: ${error.message}`
            : 'Unexpected Error'
          }
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  )
}
```

## Future Enhancements

- **GraphQL Integration**: Consider adding GraphQL codegen alongside OpenAPI
- **WebSocket Support**: Extend for real-time features
- **Optimistic Updates**: Implement optimistic mutations for better UX
- **Caching Strategies**: Advanced caching with React Query
- **Mock Service Worker**: Use MSW with generated types for testing

This integration provides a robust, type-safe foundation for your React frontend that automatically stays in sync with your FastAPI backend!
