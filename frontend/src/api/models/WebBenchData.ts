/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ApiDetectionItem } from "./ApiDetectionItem"
import type { DataSource } from "./DataSource"
import type { DetectionSource } from "./DetectionSource"
import type { StructuredAddress } from "./StructuredAddress"
/**
 * Schema for web UI bench data.
 */
export type WebBenchData = {
  id: number
  provider_id?: string | null
  lat: number
  lng: number
  tags?: Record<string, any>
  source: DataSource
  external_id?: string | null
  bench_found?: boolean
  best_confidence: number
  roboflow_confidence?: number
  ultralytics_confidence?: number
  mapillary_confidence?: number
  detection_type: DetectionSource
  has_segmentation: boolean
  image_count: number
  image_filenames: Array<string>
  image_ids: Array<number>
  image_urls?: Array<string> | null
  distance_meters: number
  distance_km: number
  reverse_geocode?: StructuredAddress | null
  cluster_id?: number | null
  cluster_center_lat?: number | null
  cluster_center_lng?: number | null
  cluster_bench_count?: number | null
  cluster_max_distance_meters?: number | null
  is_cluster_representative?: boolean | null
  detection_items?: Array<ApiDetectionItem> | null
}
