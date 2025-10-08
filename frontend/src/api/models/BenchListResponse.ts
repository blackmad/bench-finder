/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PaginationInfo } from './PaginationInfo';
import type { WebBenchData } from './WebBenchData';
export type BenchListResponse = {
    /**
     * List of bench data
     */
    benches: Array<WebBenchData>;
    /**
     * Pagination metadata
     */
    pagination: PaginationInfo;
};

