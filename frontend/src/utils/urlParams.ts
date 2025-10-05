import type { AppFilters } from "../contexts/AppContext"

// Serialize filters to URL search parameters
export const filtersToSearchParams = (filters: AppFilters): URLSearchParams => {
  const params = new URLSearchParams()

  if (filters.minConfidence !== 0.2) {
    params.set("minConfidence", filters.minConfidence.toString())
  }

  if (filters.sourceFilter !== "all") {
    params.set("source", filters.sourceFilter)
  }

  if (filters.sortBy !== "distance") {
    params.set("sortBy", filters.sortBy)
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
  if (source !== null && ["all", "osm", "streetview"].includes(source)) {
    filters.sourceFilter = source as AppFilters["sourceFilter"]
  }

  const sortBy = searchParams.get("sortBy")
  if (
    sortBy !== null &&
    ["distance", "confidence", "recent"].includes(sortBy)
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

  return filters
}

// Get current URL with updated search parameters
export const buildUrlWithFilters = (
  filters: AppFilters,
  pathname: string = window.location.pathname
): string => {
  const params = filtersToSearchParams(filters)
  const search = params.toString()
  return search ? `${pathname}?${search}` : pathname
}

// Update URL without triggering navigation
export const updateUrlWithFilters = (
  filters: AppFilters,
  pathname?: string
) => {
  const url = buildUrlWithFilters(filters, pathname)
  window.history.replaceState({}, "", url)
}
