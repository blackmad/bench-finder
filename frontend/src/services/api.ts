// Updated API service using auto-generated OpenAPI client for type safety

import axios from "axios"
import type {
  BboxBenchResponse,
  BenchListResponse,
  ClusteredBenchListResponse,
  ConfigResponse,
  SearchListResponse,
  SegmentationData,
  WebBenchData,
  BenchDetectionData,
  ImageListResponse,
  ReportResponse,
  MissingBenchReportResponse,
  ApiInfoResponse,
} from "../api"
import { DataSource, BenchMode, BenchReportType } from "../api"
import { BenchFinderApi, OpenAPI } from "../api"
import type { AppFilters } from "../contexts/AppContext"

// Configure the OpenAPI client
OpenAPI.BASE = "" // Use relative URLs for Vite proxy in development
OpenAPI.WITH_CREDENTIALS = false
OpenAPI.CREDENTIALS = "same-origin"

// Create the main API client instance
const benchFinderApi = new BenchFinderApi()

// Keep the old axios instance for any remaining manual calls and debugging
export const api = axios.create({
  baseURL: "",
  headers: {
    "Content-Type": "application/json",
  },
})

// Add request interceptor for debugging (keep for backward compatibility)
api.interceptors.request.use(
  (config) => {
    console.log(
      "API Request:",
      config.method?.toUpperCase(),
      config.url,
      config.params
    )
    return config
  },
  (error) => Promise.reject(error)
)

// Add response interceptor for error handling (keep for backward compatibility)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error(
      "API Error:",
      error.response?.status,
      error.response?.data || error.message
    )
    return Promise.reject(error)
  }
)

// Health check function
export const checkApiHealth = async (): Promise<Record<string, boolean>> => {
  const results: Record<string, boolean> = {}

  try {
    // Test main API
    await benchFinderApi.config.getConfigApiConfigGet()
    results.main = true
  } catch {
    results.main = false
  }

  try {
    // Test API info endpoint
    await benchFinderApi.config.getApiInfoApiInfoGet()
    results.info = true
  } catch {
    results.info = false
  }

  return results
}

export const benchApi = {
  // Get paginated benches - now using generated API client
  getBenches: async (params: {
    page?: number
    page_size?: number
    min_confidence?: number
    start_lat?: number
    start_lng?: number
    sort_by?: string
    mode?: BenchMode
    clustered?: boolean
    include_detection_data?: boolean
  }): Promise<BenchListResponse | ClusteredBenchListResponse> => {
    return benchFinderApi.benches.getBenchesApiBenchesGet({
      page: params.page,
      pageSize: params.page_size,
      minConfidence: params.min_confidence,
      startLat: params.start_lat,
      startLng: params.start_lng,
      sortBy: params.sort_by,
      mode: params.mode || BenchMode.BENCHES,
      clustered: params.clustered ?? true, // Default to clustered
      includeDetectionData: params.include_detection_data ?? false,
    })
  },

  // Get bench by ID - new method
  getBenchById: async (
    benchId: number,
    includeDetectionData: boolean = false
  ): Promise<WebBenchData> => {
    return benchFinderApi.benches.getBenchByIdEndpointApiBenchBenchIdGet({
      benchId,
      includeDetectionData,
    })
  },

  // Get benches in bounding box for map view - now using generated API client
  getBenchesInBbox: async (params: {
    north: number
    south: number
    east: number
    west: number
    min_confidence?: number
    source?: DataSource | null
    mode?: BenchMode
    sort_by?: string
    limit?: number
    clustered?: boolean
    include_detection_data?: boolean
  }): Promise<BboxBenchResponse | ClusteredBenchListResponse> => {
    return benchFinderApi.benches.getBenchesInBboxApiBenchesBboxGet({
      north: params.north,
      south: params.south,
      east: params.east,
      west: params.west,
      minConfidence: params.min_confidence,
      source: params.source,
      mode: params.mode || BenchMode.BENCHES,
      sortBy: params.sort_by,
      limit: params.limit,
      clustered: params.clustered ?? true, // Default to clustered
      includeDetectionData: params.include_detection_data ?? false,
    })
  },

  // Get random bench - now using generated API client
  getRandomBench: async (params?: {
    min_confidence?: number
    mode?: BenchMode
    include_detection_data?: boolean
  }): Promise<WebBenchData> => {
    return benchFinderApi.benches.getRandomBenchApiBenchesRandomGet({
      minConfidence: params?.min_confidence,
      mode: params?.mode || BenchMode.BENCHES,
      includeDetectionData: params?.include_detection_data ?? false,
    })
  },

  // Get image segmentation data - now using generated API client
  getImageSegmentation: async (imageId: number): Promise<SegmentationData> => {
    return benchFinderApi.images.getImageSegmentationApiImageImageIdSegmentationGet(
      {
        imageId,
      }
    )
  },

  // Get available searches - now using generated API client
  getSearches: async (): Promise<SearchListResponse> => {
    return benchFinderApi.search.getSearchesApiSearchesGet()
  },

  // Get app configuration - now using generated API client
  getConfig: async (): Promise<ConfigResponse> => {
    return benchFinderApi.config.getConfigApiConfigGet()
  },

  // Get API information - new method
  getApiInfo: async (): Promise<ApiInfoResponse> => {
    return benchFinderApi.config.getApiInfoApiInfoGet()
  },

  // Get bench images - new method
  getBenchImages: async (benchId: number): Promise<ImageListResponse> => {
    return benchFinderApi.images.getBenchImagesApiBenchBenchIdImagesGet({
      benchId,
    })
  },

  // Get bench detection data - new method
  getBenchDetections: async (benchId: number): Promise<BenchDetectionData> => {
    return benchFinderApi.images.getBenchDetectionsApiBenchBenchIdDetectionsGet({
      benchId,
    })
  },

  // Report bad bench detection - new method
      reportBadBench: async (params: {
        benchId: number
        reportType: BenchReportType
        description?: string
        imageId?: number
        userLocationLat?: number
        userLocationLng?: number
      }): Promise<ReportResponse> => {
        return benchFinderApi.reporting.reportBadBenchApiBenchesBenchIdReportPost({
          benchId: params.benchId,
          requestBody: {
            report_type: params.reportType,
            description: params.description,
            image_id: params.imageId,
            user_location_lat: params.userLocationLat,
            user_location_lng: params.userLocationLng,
          },
        })
      },

  // Report missing bench - new method
  reportMissingBench: async (params: {
    lat: number
    lng: number
    description?: string
    locationMethod?: string
    userLocationLat?: number
    userLocationLng?: number
    accuracyMeters?: number
    imageData?: string
  }): Promise<MissingBenchReportResponse> => {
    return benchFinderApi.reporting.reportMissingBenchApiMissingBenchesPost({
      requestBody: {
        lat: params.lat,
        lng: params.lng,
        description: params.description,
        location_method: params.locationMethod || "gps",
        user_location_lat: params.userLocationLat,
        user_location_lng: params.userLocationLng,
        accuracy_meters: params.accuracyMeters,
        image_data: params.imageData,
      },
    })
  },
}

// Helper function to build query params
export const buildApiParams = (
  filters: AppFilters,
  page: number = 0,
  pageSize: number = 20
) => {
  const params: any = {
    page,
    page_size: pageSize,
    min_confidence: filters.minConfidence,
    start_lat: filters.startLat,
    start_lng: filters.startLng,
    sort_by: filters.sortBy,
  }

  return params
}

// Helper function to calculate distance between two points
export const calculateDistance = (
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number => {
  const toRadians = (degrees: number) => degrees * (Math.PI / 180)

  const R = 6371000 // Earth's radius in meters
  const dLat = toRadians(lat2 - lat1)
  const dLng = toRadians(lng2 - lng1)

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(lat1)) *
      Math.cos(toRadians(lat2)) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2)

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c // Distance in meters
}

// Export the new generated API client for advanced usage
export { benchFinderApi }

// Export individual services for granular access
export const benchesService = benchFinderApi.benches
export const imagesService = benchFinderApi.images
export const searchService = benchFinderApi.search
export const configService = benchFinderApi.config
// Note: mapillary and statistics services are not available in the current API

// Health check utility using the generated client
export const checkHealth = async () => {
  return benchFinderApi.config.healthCheckHealthGet()
}

export default benchApi
