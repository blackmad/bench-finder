/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type MapillarySearchRequest = {
    /**
     * Search center latitude
     */
    center_lat: number;
    /**
     * Search center longitude
     */
    center_lng: number;
    /**
     * Search radius in meters
     */
    radius_meters?: number;
    /**
     * Maximum results to return
     */
    limit?: number;
};
