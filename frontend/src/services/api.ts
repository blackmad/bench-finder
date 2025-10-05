import axios from "axios"
import type {
  AppFilters,
  BboxResponse,
  Bench,
  BenchListResponse,
  ConfigResponse,
  SearchListResponse,
  SegmentationData,
} from "../types/index"

// Configure axios with base URL - Vite will proxy to Flask server in development
export const api = axios.create({
  baseURL: "",
  headers: {
    "Content-Type": "application/json",
  },
})

// Add request interceptor for debugging
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

// Add response interceptor for error handling
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
  // Get paginated benches
  getBenches: async (params: {
    page?: number
    page_size?: number
    min_confidence?: number
    start_lat?: number
    start_lng?: number
    sort_by?: string
  }): Promise<BenchListResponse> => {
    const response = await api.get("/api/benches", { params })
    return response.data
  },

  // Get benches by source
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
    const response = await api.get(`/api/benches/source/${source}`, { params })
    return response.data
  },

  // Get benches in bounding box for map view
  getBenchesInBbox: async (params: {
    north: number
    south: number
    east: number
    west: number
    min_confidence?: number
    source?: string
    sort_by?: string
    limit?: number
  }): Promise<BboxResponse> => {
    const response = await api.get("/api/benches/bbox", { params })
    return response.data
  },

  // Get random bench
  getRandomBench: async (params?: {
    min_confidence?: number
    source?: string
    sort_by?: string
  }): Promise<{ bench: Bench }> => {
    const response = await api.get("/api/benches/random", { params })
    return response.data
  },

  // Get image segmentation data
  getImageSegmentation: async (imageId: number): Promise<SegmentationData> => {
    const response = await api.get(`/api/image/${imageId}/segmentation`)
    return response.data
  },

  // Get available searches
  getSearches: async (): Promise<SearchListResponse> => {
    const response = await api.get("/api/searches")
    return response.data
  },

  // Get app configuration
  getConfig: async (): Promise<ConfigResponse> => {
    const response = await api.get("/api/config")
    return response.data
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

export default benchApi
