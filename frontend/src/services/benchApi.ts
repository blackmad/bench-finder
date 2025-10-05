/**
 * Modern API service using auto-generated OpenAPI client
 * This replaces the old manual API service with type-safe, auto-generated methods
 */
import {
  type BboxBenchResponse,
  BenchFinderApi,
  type BenchListResponse,
  OpenAPI,
  type RandomBenchResponse,
} from "../api"
import type { AppFilters } from "../types/index"

// Configure the OpenAPI client
OpenAPI.BASE = "" // Use relative URLs for Vite proxy in development
OpenAPI.WITH_CREDENTIALS = false
OpenAPI.CREDENTIALS = "same-origin"

// Create the main API client instance
export const benchFinderApi = new BenchFinderApi()

// Enhanced API service with convenience methods
export class BenchApiService {
  /**
   * Get paginated list of benches with filtering and sorting
   */
  async getBenches(
    params: {
      page?: number
      pageSize?: number
      minConfidence?: number
      startLat?: number
      startLng?: number
      sortBy?: "distance" | "confidence" | "images" | "recent"
      source?: "osm" | "mapillary" | null
    } = {}
  ): Promise<BenchListResponse> {
    return benchFinderApi.benches.getBenchesApiBenchesGet({
      page: params.page ?? 0,
      pageSize: params.pageSize ?? 20,
      minConfidence: params.minConfidence ?? 0.8,
      startLat: params.startLat ?? 52.3613577,
      startLng: params.startLng ?? 4.8666322,
      sortBy: params.sortBy ?? "distance",
      source: params.source ?? null,
    })
  }

  /**
   * Get benches filtered by specific data source
   */
  async getBenchesBySource(
    source: "osm" | "mapillary",
    params: {
      page?: number
      pageSize?: number
      minConfidence?: number
      startLat?: number
      startLng?: number
      sortBy?: "distance" | "confidence" | "images" | "recent"
    } = {}
  ): Promise<BenchListResponse> {
    return benchFinderApi.benches.getBenchesBySourceApiBenchesSourceSourceGet({
      source,
      page: params.page ?? 0,
      pageSize: params.pageSize ?? 20,
      minConfidence: params.minConfidence ?? 0.8,
      startLat: params.startLat ?? 52.3613577,
      startLng: params.startLng ?? 4.8666322,
      sortBy: params.sortBy ?? "distance",
    })
  }

  /**
   * Get benches within a geographic bounding box for map applications
   */
  async getBenchesInBbox(params: {
    north: number
    south: number
    east: number
    west: number
    minConfidence?: number
    source?: "osm" | "mapillary" | null
    sortBy?: "distance" | "confidence" | "images" | "recent"
    limit?: number
    clustered?: boolean
  }): Promise<any> {
    return benchFinderApi.benches.getBenchesInBboxApiBenchesBboxGet({
      north: params.north,
      south: params.south,
      east: params.east,
      west: params.west,
      minConfidence: params.minConfidence ?? 0.8,
      source: params.source ?? null,
      sortBy: params.sortBy ?? "distance",
      limit: params.limit ?? 200,
      clustered: params.clustered ?? true, // Default to clustered
    })
  }

  /**
   * Get a randomly selected bench
   */
  async getRandomBench(
    params: { minConfidence?: number; source?: "osm" | "mapillary" | null } = {}
  ): Promise<RandomBenchResponse> {
    return benchFinderApi.benches.getRandomBenchApiBenchesRandomGet({
      minConfidence: params.minConfidence ?? 0.8,
      source: params.source ?? null,
    })
  }

  /**
   * Get image segmentation data for visualization
   */
  async getImageSegmentation(imageId: number) {
    return benchFinderApi.images.getImageSegmentationApiImageImageIdSegmentationGet(
      {
        imageId,
      }
    )
  }

  /**
   * Get all images for a specific bench
   */
  async getBenchImages(benchId: number) {
    return benchFinderApi.images.getBenchImagesApiBenchBenchIdImagesGet({
      benchId,
    })
  }

  /**
   * Get historical search operations
   */
  async getSearches() {
    return benchFinderApi.search.getSearchesApiSearchesGet()
  }

  /**
   * Get application configuration
   */
  async getConfig() {
    return benchFinderApi.config.getConfigApiConfigGet()
  }

  /**
   * Get comprehensive API information
   */
  async getApiInfo() {
    return benchFinderApi.config.getApiInfoApiInfoGet()
  }

  /**
   * Search Mapillary for bench detections (if available)
   */
  async searchMapillary(params: {
    centerLat: number
    centerLng: number
    radiusMeters?: number
    limit?: number
  }) {
    return benchFinderApi.mapillary.searchMapillaryApiMapillarySearchPost({
      requestBody: {
        center_lat: params.centerLat,
        center_lng: params.centerLng,
        radius_meters: params.radiusMeters ?? 1000,
        limit: params.limit ?? 1000,
      },
    })
  }

  /**
   * Get stored Mapillary data
   */
  async getStoredMapillary(params: {
    centerLat: number
    centerLng: number
    radiusMeters?: number
    limit?: number
  }) {
    return benchFinderApi.mapillary.getStoredMapillaryApiMapillaryStoredGet({
      centerLat: params.centerLat,
      centerLng: params.centerLng,
      radiusMeters: params.radiusMeters ?? 1000,
      limit: params.limit ?? 1000,
    })
  }

  /**
   * Get Mapillary statistics
   */
  async getMapillaryStatistics(
    params: {
      centerLat?: number
      centerLng?: number
      radiusMeters?: number
    } = {}
  ) {
    return benchFinderApi.mapillary.getMapillaryStatisticsApiMapillaryStatisticsGet(
      {
        centerLat: params.centerLat,
        centerLng: params.centerLng,
        radiusMeters: params.radiusMeters,
      }
    )
  }

  /**
   * Get statistics filtered by data source
   */
  async getStatisticsBySource(
    source: "osm" | "mapillary",
    params: {
      centerLat?: number
      centerLng?: number
      radiusMeters?: number
    } = {}
  ) {
    return benchFinderApi.statistics.getStatisticsBySourceApiStatisticsSourceSourceGet(
      {
        source,
        centerLat: params.centerLat,
        centerLng: params.centerLng,
        radiusMeters: params.radiusMeters,
      }
    )
  }
}

// Create and export the service instance
export const benchApi = new BenchApiService()

// Helper function to build query params from app filters (for backward compatibility)
export const buildApiParamsFromFilters = (
  filters: AppFilters,
  page: number = 0,
  pageSize: number = 20
) => ({
  page,
  pageSize,
  minConfidence: filters.minConfidence,
  startLat: filters.startLat,
  startLng: filters.startLng,
  sortBy: filters.sortBy as "distance" | "confidence" | "images" | "recent",
})

// Utility function for health check
export const checkApiHealth = async (): Promise<Record<string, string>> => {
  try {
    const response = await fetch("/health")
    return await response.json()
  } catch (error) {
    throw new Error(`Health check failed: ${error}`)
  }
}

// Helper function to calculate distance between two points (kept for utility)
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

// Export individual services for granular access if needed
export const benchesService = benchFinderApi.benches
export const imagesService = benchFinderApi.images
export const searchService = benchFinderApi.search
export const configService = benchFinderApi.config
export const mapillaryService = benchFinderApi.mapillary
export const statisticsService = benchFinderApi.statistics

// Default export for convenience
export default benchApi
