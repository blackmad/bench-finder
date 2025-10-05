/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BboxBenchResponse } from '../models/BboxBenchResponse';
import type { BenchListResponse } from '../models/BenchListResponse';
import type { ClusteredBenchListResponse } from '../models/ClusteredBenchListResponse';
import type { RandomBenchResponse } from '../models/RandomBenchResponse';
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
        source,
        clustered = true,
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
         * Filter by data source
         */
        source?: (string | null),
        /**
         * Return clustered results when available (default: True)
         */
        clustered?: boolean,
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
                'source': source,
                'clustered': clustered,
            },
            errors: {
                400: `Invalid query parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * List Benches by Source
     * Get benches filtered by specific data source (OSM or Mapillary)
     * @returns BenchListResponse Successful Response
     * @throws ApiError
     */
    public getBenchesBySourceApiBenchesSourceSourceGet({
        source,
        page,
        pageSize = 20,
        minConfidence = 0.8,
        startLat = 52.3613577,
        startLng = 4.8666322,
        sortBy = 'distance',
    }: {
        /**
         * Data source filter
         */
        source: string,
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
    }): CancelablePromise<BenchListResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/benches/source/{source}',
            path: {
                'source': source,
            },
            query: {
                'page': page,
                'page_size': pageSize,
                'min_confidence': minConfidence,
                'start_lat': startLat,
                'start_lng': startLng,
                'sort_by': sortBy,
            },
            errors: {
                400: `Invalid source or parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get Random Bench
     * Get a randomly selected bench that meets the specified criteria
     * @returns RandomBenchResponse Successful Response
     * @throws ApiError
     */
    public getRandomBenchApiBenchesRandomGet({
        minConfidence = 0.8,
        source,
    }: {
        /**
         * Minimum detection confidence
         */
        minConfidence?: number,
        /**
         * Filter by data source
         */
        source?: (string | null),
    }): CancelablePromise<RandomBenchResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/benches/random',
            query: {
                'min_confidence': minConfidence,
                'source': source,
            },
            errors: {
                404: `No benches found matching criteria`,
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
        sortBy = 'distance',
        limit = 200,
        clustered = true,
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
         * Filter by data source
         */
        source?: (string | null),
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
                'sort_by': sortBy,
                'limit': limit,
                'clustered': clustered,
            },
            errors: {
                400: `Invalid bounding box parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
}
