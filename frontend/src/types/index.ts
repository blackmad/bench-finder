export interface Bench {
  id: number
  provider_id: string
  lat: number
  lng: number
  tags: Record<string, string>
  source: "osm" | "mapillary"
  external_id: string
  best_confidence: number
  roboflow_confidence: number
  ultralytics_confidence: number
  mapillary_confidence: number
  detection_type: "roboflow" | "ultralytics" | "mapillary"
  has_segmentation: boolean
  image_count: number
  image_filenames: string[]
  image_ids: number[]
  distance_meters: number
  distance_km: number
}

export interface PaginationInfo {
  page: number
  page_size: number
  total_count: number
  total_pages: number
  has_next: boolean
}

export interface BenchListResponse {
  benches: Bench[]
  pagination: PaginationInfo
}

export interface SearchSummary {
  id: number
  query: string
  start_lat: number
  start_lng: number
  search_radius: number
  bench_count: number
  created_at: string
}

export interface SearchListResponse {
  searches: SearchSummary[]
}

export interface ConfigResponse {
  default_start_lat: number
  default_start_lng: number
  default_min_confidence: number
  page_size: number
}

export interface SegmentationData {
  filename: string
  detection_type: string
  bench_detections: any[]
  image_shape: number[] | null
  segmentation_available: boolean
  roboflow_detections: any[]
  bounding_box_available: boolean
  confidence_score: number
  source: string
}

export interface BboxResponse {
  benches: Bench[]
  total_count: number
  bbox: {
    north: number
    south: number
    east: number
    west: number
  }
}

export interface AppFilters {
  minConfidence: number
  sourceFilter: "all" | "osm" | "mapillary"
  sortBy: "distance" | "confidence" | "images" | "recent"
  startLat: number
  startLng: number
}

export type ViewMode = "cards" | "map"

export interface AppState {
  benches: Bench[]
  filters: AppFilters
  viewMode: ViewMode
  currentPage: number
  loading: boolean
  hasMore: boolean
  selectedBenchId: number | null
  debugMode: boolean
  config: ConfigResponse | null
  searches: SearchSummary[]
}

export interface GeolocationCoords {
  latitude: number
  longitude: number
  accuracy: number
}
