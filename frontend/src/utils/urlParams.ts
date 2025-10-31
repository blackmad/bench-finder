import { BenchMode } from "../api"
import type { AppFilters } from "../contexts/AppContext"

// Serialize filters to URL search parameters
export const filtersToSearchParams = (filters: AppFilters): URLSearchParams => {
  const params = new URLSearchParams()

  if (filters.minConfidence !== 0) {
    params.set("minConfidence", filters.minConfidence.toString())
  }

  if (filters.sourceFilter !== "all") {
    // Convert enum values to lowercase for URL (OSM -> osm, MAPILLARY -> mapillary)
    const sourceValue = filters.sourceFilter === "OSM" ? "osm" : filters.sourceFilter === "MAPILLARY" ? "mapillary" : filters.sourceFilter
    params.set("source", sourceValue.toLowerCase())
  }

  if (filters.sortBy !== "distance") {
    params.set("sortBy", filters.sortBy)
  }

  // Mode filter - default is BENCHES, so only include if different
  if (filters.mode !== BenchMode.BENCHES) {
    params.set("mode", filters.mode)
  }

  // Include detection data - only include if true (default is false)
  if (filters.includeDetectionData) {
    params.set("includeDetectionData", "true")
  }

  // Always include coordinates as they're essential
  params.set("lat", filters.startLat.toString())
  params.set("lng", filters.startLng.toString())

  return params
}

// Deserialize URL search parameters to filters
export const searchParamsToFilters = (
  searchParams: URLSearchParams,
  _defaultFilters: AppFilters
): Partial<AppFilters> => {
  const filters: Partial<AppFilters> = {}

  const minConfidence = searchParams.get("minConfidence")
  if (minConfidence !== null) {
    const parsed = parseFloat(minConfidence)
    if (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 1) {
      filters.minConfidence = parsed
    }
  }

  const source = searchParams.get("source")
  if (source !== null) {
    // Handle both lowercase (URL) and uppercase (enum) values
    const sourceLower = source.toLowerCase()
    if (sourceLower === "all" || sourceLower === "osm" || sourceLower === "streetview") {
      // Convert lowercase URL values to enum values
      if (sourceLower === "osm") {
        filters.sourceFilter = "OSM" as AppFilters["sourceFilter"]
      } else if (sourceLower === "streetview" || sourceLower === "mapillary") {
        filters.sourceFilter = "MAPILLARY" as AppFilters["sourceFilter"]
      } else {
        filters.sourceFilter = "all"
      }
    } else if (source === "OSM" || source === "MAPILLARY") {
      // Handle uppercase enum values directly
      filters.sourceFilter = source as AppFilters["sourceFilter"]
    }
  }

  const sortBy = searchParams.get("sortBy")
  if (
    sortBy !== null &&
    ["distance", "confidence", "images", "recent"].includes(sortBy)
  ) {
    filters.sortBy = sortBy as AppFilters["sortBy"]
  }

  const lat = searchParams.get("lat")
  if (lat !== null) {
    const parsed = parseFloat(lat)
    if (!Number.isNaN(parsed) && parsed >= -90 && parsed <= 90) {
      filters.startLat = parsed
    }
  }

  const lng = searchParams.get("lng")
  if (lng !== null) {
    const parsed = parseFloat(lng)
    if (!Number.isNaN(parsed) && parsed >= -180 && parsed <= 180) {
      filters.startLng = parsed
    }
  }

  const mode = searchParams.get("mode")
  if (mode !== null && ["benches", "no_bench", "both"].includes(mode)) {
    filters.mode = mode as AppFilters["mode"]
  }

  const includeDetectionData = searchParams.get("includeDetectionData")
  if (includeDetectionData !== null) {
    filters.includeDetectionData = includeDetectionData === "true"
  }

  return filters
}

// Get current URL with updated search parameters
export const buildUrlWithFilters = (
  filters: AppFilters,
  pathname: string = window.location.pathname,
  preserveParams: string[] = []
): string => {
  // Start with existing params to preserve non-filter params (like zoom)
  const existingParams = new URLSearchParams(window.location.search)
  const params = filtersToSearchParams(filters)

  // Preserve specified params from existing URL
  for (const key of preserveParams) {
    const existingValue = existingParams.get(key)
    if (existingValue !== null) {
      params.set(key, existingValue)
    }
  }

  const search = params.toString()
  return search ? `${pathname}?${search}` : pathname
}

// Update URL without triggering navigation (using React Router's setSearchParams)
export const updateUrlWithFilters = (
  filters: AppFilters,
  setSearchParams: (params: URLSearchParams | ((prev: URLSearchParams) => URLSearchParams), opts?: { replace?: boolean }) => void,
  preserveParams: string[] = ["zoom"] // Preserve zoom by default
) => {
  setSearchParams((prev) => {
    const params = filtersToSearchParams(filters)

    // Preserve specified params from existing URL
    for (const key of preserveParams) {
      const existingValue = prev.get(key)
      if (existingValue !== null) {
        params.set(key, existingValue)
      }
    }

    return params
  }, { replace: true })
}

// Legacy function for backwards compatibility (using window.history)
export const updateUrlWithFiltersLegacy = (
  filters: AppFilters,
  pathname?: string,
  preserveParams: string[] = ["zoom"] // Preserve zoom by default
) => {
  const url = buildUrlWithFilters(filters, pathname, preserveParams)
  window.history.replaceState({}, "", url)
}
