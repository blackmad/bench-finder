/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WebBenchData } from './WebBenchData';
export type BboxBenchResponse = {
    /**
     * List of benches within bounding box
     */
    benches: Array<WebBenchData>;
    /**
     * Total number of benches returned
     */
    total_count: number;
    /**
     * Bounding box coordinates
     */
    bbox: Record<string, number>;
    /**
     * Query metadata
     */
    query_info?: Record<string, any>;
};

