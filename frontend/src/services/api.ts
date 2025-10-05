// Updated API service using auto-generated OpenAPI client for type safety

import axios from "axios"
import type {
  BboxBenchResponse,
  BenchListResponse,
  ConfigResponse,
  RandomBenchResponse,
  SearchListResponse,
  SegmentationData,
} from "../api"
import { BenchFinderApi, OpenAPI } from "../api"
import type { AppFilters, BboxResponse, Bench } from "../types/index"

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

export const benchApi = {
  // Get paginated benches - now using generated API client
  getBenches: async (params: {
    page?: number
    page_size?: number
    min_confidence?: number
    start_lat?: number
    start_lng?: number
    sort_by?: string
  }): Promise<BenchListResponse> => {
    return benchFinderApi.benches.getBenchesApiBenchesGet({
      page: params.page,
      pageSize: params.page_size,
      minConfidence: params.min_confidence,
      startLat: params.start_lat,
      startLng: params.start_lng,
      sortBy: params.sort_by,
    })
  },

  // Get benches by source - now using generated API client
  getBenchesBySource: async (
    source: string,
    params: {
      page?: number
      page_size?: number
      min_confidence?: number
      start_lat?: number
      start_lng?: number
      sort_by?: string
    }
  ): Promise<BenchListResponse> => {
    return benchFinderApi.benches.getBenchesBySourceApiBenchesSourceSourceGet({
      source,
      page: params.page,
      pageSize: params.page_size,
      minConfidence: params.min_confidence,
      startLat: params.start_lat,
      startLng: params.start_lng,
      sortBy: params.sort_by,
    })
  },

  // Get benches in bounding box for map view - now using generated API client
  getBenchesInBbox: async (params: {
    north: number
    south: number
    east: number
    west: number
    min_confidence?: number
    source?: string
    sort_by?: string
    limit?: number
    clustered?: boolean
  }): Promise<any> => {
    return benchFinderApi.benches.getBenchesInBboxApiBenchesBboxGet({
      north: params.north,
      south: params.south,
      east: params.east,
      west: params.west,
      minConfidence: params.min_confidence,
      source: params.source,
      sortBy: params.sort_by,
      limit: params.limit,
      clustered: params.clustered ?? true, // Default to clustered
    })
  },

  // Get random bench - now using generated API client
  // Note: The API returns RandomBenchResponse but for backward compatibility
  // we keep the same interface
  getRandomBench: async (params?: {
    min_confidence?: number
    source?: string
    sort_by?: string
  }): Promise<RandomBenchResponse> => {
    return benchFinderApi.benches.getRandomBenchApiBenchesRandomGet({
      minConfidence: params?.min_confidence,
      source: params?.source,
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
export const mapillaryService = benchFinderApi.mapillary
export const statisticsService = benchFinderApi.statistics

// Health check utility using the generated client
export const checkApiHealth = async () => {
  return benchFinderApi.config.healthCheckHealthGet()
}

export default benchApi
