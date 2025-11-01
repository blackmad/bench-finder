/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DetectionSource } from "./DetectionSource"
import type { ImageWithDetectionData } from "./ImageWithDetectionData"
/**
 * Schema for comprehensive bench detection data including all images and detections.
 */
export type BenchDetectionData = {
  bench_id: number
  bench_lat: number
  bench_lng: number
  total_images: number
  images_with_detections: number
  best_confidence: number
  detection_sources: Array<DetectionSource>
  /**
   * List of images with their detection items
   */
  images?: Array<ImageWithDetectionData>
}
