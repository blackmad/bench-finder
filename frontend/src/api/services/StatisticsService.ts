/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class StatisticsService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * Get Statistics by Source
     * Get comprehensive statistics filtered by data source
     * @returns any Successful Response
     * @throws ApiError
     */
    public getStatisticsBySourceApiStatisticsSourceSourceGet({
        source,
        centerLat,
        centerLng,
        radiusMeters,
    }: {
        /**
         * Data source
         */
        source: string,
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
            url: '/api/statistics/source/{source}',
            path: {
                'source': source,
            },
            query: {
                'center_lat': centerLat,
                'center_lng': centerLng,
                'radius_meters': radiusMeters,
            },
            errors: {
                400: `Invalid source parameter`,
                422: `Validation Error`,
                500: `Internal server error`,
            },
        });
    }
}
