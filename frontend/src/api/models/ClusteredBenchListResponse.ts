/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClusteredBenchData } from './ClusteredBenchData';
import type { PaginationInfo } from './PaginationInfo';
/**
 * Schema for paginated clustered bench list response.
 */
export type ClusteredBenchListResponse = {
    clustered_benches: Array<ClusteredBenchData>;
    pagination: PaginationInfo;
    clustering_info?: Record<string, any>;
};
