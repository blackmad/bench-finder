/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BboxBenchResponse } from '../models/BboxBenchResponse';
import type { BenchListResponse } from '../models/BenchListResponse';
import { BenchMode } from '../models/BenchMode';
import type { ClusteredBenchListResponse } from '../models/ClusteredBenchListResponse';
import type { DataSource } from '../models/DataSource';
import type { WebBenchData } from '../models/WebBenchData';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class BenchesService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * List Benches
     * Get paginated list of benches with high confidence detections, sorted by various criteria
     * @returns any Successful Response
     * @throws ApiError
     */
    public getBenchesApiBenchesGet({
        page,
        pageSize = 20,
        minConfidence = 0.8,
        startLat = 52.3613577,
        startLng = 4.8666322,
        sortBy = 'distance',
        mode = BenchMode.BENCHES,
        clustered = true,
        includeDetectionData = false,
        source,
    }: {
        /**
         * Page number (0-based)
         */
        page?: number,
        /**
         * Items per page (max 50)
         */
        pageSize?: number,
        /**
         * Minimum detection confidence
         */
        minConfidence?: number,
        /**
         * Starting latitude for distance sorting
         */
        startLat?: number,
        /**
         * Starting longitude for distance sorting
         */
        startLng?: number,
        /**
         * Sort criteria
         */
        sortBy?: string,
        /**
         * Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'
         */
        mode?: BenchMode,
        /**
         * Return clustered results when available (default: True)
         */
        clustered?: boolean,
        /**
         * Include detection items (bbox, polygon) in response (default: False)
         */
        includeDetectionData?: boolean,
        /**
         * Filter by data source: 'osm' or 'mapillary' (default: all sources)
         */
        source?: (DataSource | null),
    }): CancelablePromise<(BenchListResponse | ClusteredBenchListResponse)> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/benches',
            query: {
                'page': page,
                'page_size': pageSize,
                'min_confidence': minConfidence,
                'start_lat': startLat,
                'start_lng': startLng,
                'sort_by': sortBy,
                'mode': mode,
                'clustered': clustered,
                'include_detection_data': includeDetectionData,
                'source': source,
            },
            errors: {
                400: `Invalid query parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get Random Bench
     * Get a randomly selected bench that meets the specified criteria
     * @returns WebBenchData Successful Response
     * @throws ApiError
     */
    public getRandomBenchApiBenchesRandomGet({
        minConfidence = 0.8,
        mode = BenchMode.BENCHES,
        includeDetectionData = false,
    }: {
        /**
         * Minimum detection confidence
         */
        minConfidence?: number,
        /**
         * Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'
         */
        mode?: BenchMode,
        /**
         * Include detection items (bbox, polygon) in response (default: False)
         */
        includeDetectionData?: boolean,
    }): CancelablePromise<WebBenchData> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/benches/random',
            query: {
                'min_confidence': minConfidence,
                'mode': mode,
                'include_detection_data': includeDetectionData,
            },
            errors: {
                404: `No benches found matching criteria`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get Bench by ID
     * Get detailed information for a specific bench by its ID
     * @returns WebBenchData Successful Response
     * @throws ApiError
     */
    public getBenchByIdEndpointApiBenchBenchIdGet({
        benchId,
        includeDetectionData = false,
    }: {
        /**
         * Bench ID to retrieve
         */
        benchId: number,
        /**
         * Include detection items (bbox, polygon) in response (default: False)
         */
        includeDetectionData?: boolean,
    }): CancelablePromise<WebBenchData> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/bench/{bench_id}',
            path: {
                'bench_id': benchId,
            },
            query: {
                'include_detection_data': includeDetectionData,
            },
            errors: {
                404: `Bench not found`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get Benches in Bounding Box
     * Get benches within a geographic bounding box for map applications
     * @returns any Successful Response
     * @throws ApiError
     */
    public getBenchesInBboxApiBenchesBboxGet({
        north,
        south,
        east,
        west,
        minConfidence = 0.8,
        source,
        mode = BenchMode.BENCHES,
        sortBy = 'distance',
        limit = 200,
        clustered = true,
        includeDetectionData = false,
    }: {
        /**
         * Northern latitude boundary
         */
        north: number,
        /**
         * Southern latitude boundary
         */
        south: number,
        /**
         * Eastern longitude boundary
         */
        east: number,
        /**
         * Western longitude boundary
         */
        west: number,
        /**
         * Minimum detection confidence
         */
        minConfidence?: number,
        /**
         * Filter by data source: 'osm' or 'mapillary' (default: all sources)
         */
        source?: (DataSource | null),
        /**
         * Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'
         */
        mode?: BenchMode,
        /**
         * Sort criteria
         */
        sortBy?: string,
        /**
         * Maximum number of results
         */
        limit?: number,
        /**
         * Return clustered results when available (default: True)
         */
        clustered?: boolean,
        /**
         * Include detection items (bbox, polygon) in response (default: False)
         */
        includeDetectionData?: boolean,
    }): CancelablePromise<(BboxBenchResponse | ClusteredBenchListResponse)> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/benches/bbox',
            query: {
                'north': north,
                'south': south,
                'east': east,
                'west': west,
                'min_confidence': minConfidence,
                'source': source,
                'mode': mode,
                'sort_by': sortBy,
                'limit': limit,
                'clustered': clustered,
                'include_detection_data': includeDetectionData,
            },
            errors: {
                400: `Invalid bounding box parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
}
