/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataSource } from "./DataSource"
import type { DetectionSource } from "./DetectionSource"
/**
 * Schema for API information response.
 */
export type ApiInfoResponse = {
  name: string
  version: string
  description: string
  supported_sources: Array<DataSource>
  supported_detection_models: Array<DetectionSource>
  features: Array<string>
  endpoints: Record<string, string>
  limits: Record<string, any>
}
