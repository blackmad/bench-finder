/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ApiDetectionItem } from "./ApiDetectionItem"
import type { DetectionSource } from "./DetectionSource"
/**
 * Schema for detection visualization data response (both segmentation and bounding boxes).
 */
export type SegmentationData = {
  filename: string
  detection_type: string
  /**
   * List of detection items with bbox and polygon data
   */
  detection_items?: Array<ApiDetectionItem>
  image_shape?: Array<number> | null
  segmentation_available?: boolean
  bounding_box_available?: boolean
  confidence_score?: number
  source?: DetectionSource
}
