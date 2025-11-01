/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PaginationInfo } from "./PaginationInfo"
import type { WebBenchData } from "./WebBenchData"
/**
 * Schema for paginated clustered bench list response.
 */
export type ClusteredBenchListResponse = {
  benches: Array<WebBenchData>
  pagination: PaginationInfo
}
