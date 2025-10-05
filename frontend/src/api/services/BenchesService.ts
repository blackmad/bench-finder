/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BboxBenchResponse } from '../models/BboxBenchResponse';
import type { BenchListResponse } from '../models/BenchListResponse';
import type { RandomBenchResponse } from '../models/RandomBenchResponse';
import type { SortByEnum } from '../models/SortByEnum';
import type { SourceEnum } from '../models/SourceEnum';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class BenchesService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * List Benches
     * Get paginated list of benches with high confidence detections
     * @returns BenchListResponse Successful Response
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
    }: {
        /**
         * Page number (0-based)
         */
        page?: number,
        /**
         * Items per page
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
        sortBy?: SortByEnum,
        /**
         * Filter by data source
         */
        source?: (SourceEnum | null),
    }): CancelablePromise<BenchListResponse> {
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
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Benches by Source
     * Get benches filtered by specific data source
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
        source: SourceEnum,
        /**
         * Page number (0-based)
         */
        page?: number,
        /**
         * Items per page
         */
        pageSize?: number,
        /**
         * Minimum detection confidence
         */
        minConfidence?: number,
        /**
         * Starting latitude
         */
        startLat?: number,
        /**
         * Starting longitude
         */
        startLng?: number,
        /**
         * Sort criteria
         */
        sortBy?: SortByEnum,
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
                422: `Validation Error`,
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
        source?: (SourceEnum | null),
    }): CancelablePromise<RandomBenchResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/benches/random',
            query: {
                'min_confidence': minConfidence,
                'source': source,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Benches in Bounding Box
     * Get benches within a geographic bounding box for map applications
     * @returns BboxBenchResponse Successful Response
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
        source?: (SourceEnum | null),
        /**
         * Sort criteria
         */
        sortBy?: SortByEnum,
        /**
         * Maximum number of results
         */
        limit?: number,
    }): CancelablePromise<BboxBenchResponse> {
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
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
