/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WebBenchData } from './WebBenchData';
/**
 * Response model for bounding box bench queries.
 */
export type BboxBenchResponse = {
    /**
     * List of benches within the bounding box
     */
    benches: Array<WebBenchData>;
    /**
     * Total number of benches returned
     */
    total_count: number;
    /**
     * The requested bounding box coordinates
     */
    bbox: Record<string, number>;
};
