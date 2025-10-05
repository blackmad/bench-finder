/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MapillarySearchRequest } from '../models/MapillarySearchRequest';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class MapillaryService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * Search Mapillary for Benches
     * Search for bench detections using Mapillary API and store results in database
     * @returns any Successful Response
     * @throws ApiError
     */
    public searchMapillaryApiMapillarySearchPost({
        requestBody,
    }: {
        requestBody: MapillarySearchRequest,
    }): CancelablePromise<Record<string, any>> {
        return this.httpRequest.request({
            method: 'POST',
            url: '/api/mapillary/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Invalid request parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
                503: `Mapillary service not available`,
            },
        });
    }
    /**
     * Get Stored Mapillary Data
     * Get previously stored Mapillary bench detections from local database
     * @returns any Successful Response
     * @throws ApiError
     */
    public getStoredMapillaryApiMapillaryStoredGet({
        centerLat,
        centerLng,
        radiusMeters = 1000,
        limit = 1000,
    }: {
        /**
         * Center latitude
         */
        centerLat: number,
        /**
         * Center longitude
         */
        centerLng: number,
        /**
         * Search radius in meters
         */
        radiusMeters?: number,
        /**
         * Maximum number of results
         */
        limit?: number,
    }): CancelablePromise<Record<string, any>> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/mapillary/stored',
            query: {
                'center_lat': centerLat,
                'center_lng': centerLng,
                'radius_meters': radiusMeters,
                'limit': limit,
            },
            errors: {
                400: `Invalid query parameters`,
                422: `Validation Error`,
                500: `Internal server error`,
                503: `Mapillary service not available`,
            },
        });
    }
    /**
     * Get Mapillary Statistics
     * Get statistics about Mapillary bench detections
     * @returns any Successful Response
     * @throws ApiError
     */
    public getMapillaryStatisticsApiMapillaryStatisticsGet({
        centerLat,
        centerLng,
        radiusMeters,
    }: {
        /**
         * Center latitude for area-specific stats
         */
        centerLat?: (number | null),
        /**
         * Center longitude for area-specific stats
         */
        centerLng?: (number | null),
        /**
         * Radius for area-specific stats
         */
        radiusMeters?: (number | null),
    }): CancelablePromise<Record<string, any>> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/mapillary/statistics',
            query: {
                'center_lat': centerLat,
                'center_lng': centerLng,
                'radius_meters': radiusMeters,
            },
            errors: {
                422: `Validation Error`,
                500: `Internal server error`,
                503: `Mapillary service not available`,
            },
        });
    }
    /**
     * Refresh Mapillary Image Detections
     * Refresh detections for a specific Mapillary image
     * @returns any Successful Response
     * @throws ApiError
     */
    public refreshMapillaryImageApiMapillaryRefreshMapillaryImageIdPut({
        mapillaryImageId,
    }: {
        /**
         * Mapillary image ID
         */
        mapillaryImageId: string,
    }): CancelablePromise<Record<string, any>> {
        return this.httpRequest.request({
            method: 'PUT',
            url: '/api/mapillary/refresh/{mapillary_image_id}',
            path: {
                'mapillary_image_id': mapillaryImageId,
            },
            errors: {
                404: `Image not found or no detections available`,
                422: `Validation Error`,
                500: `Internal server error`,
                503: `Mapillary service not available`,
            },
        });
    }
    /**
     * Get Mapillary Configuration
     * Get Mapillary integration configuration and status
     * @returns any Successful Response
     * @throws ApiError
     */
    public getMapillaryConfigApiMapillaryConfigGet(): CancelablePromise<Record<string, any>> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/mapillary/config',
        });
    }
}
