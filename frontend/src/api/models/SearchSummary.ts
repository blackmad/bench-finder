/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SearchSummary = {
    /**
     * Search identifier
     */
    id: number;
    /**
     * Search query term
     */
    query: string;
    /**
     * Search center latitude
     */
    start_lat: number;
    /**
     * Search center longitude
     */
    start_lng: number;
    /**
     * Search radius in meters
     */
    search_radius: number;
    /**
     * Number of benches found
     */
    bench_count: number;
    /**
     * When the search was created
     */
    created_at: string;
};
