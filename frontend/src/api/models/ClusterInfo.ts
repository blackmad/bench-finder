/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataSource } from './DataSource';
/**
 * Schema for cluster metadata.
 */
export type ClusterInfo = {
    cluster_id: number;
    center_lat: number;
    center_lng: number;
    bench_count: number;
    max_distance_meters: number;
    avg_confidence: number;
    sources: Array<DataSource>;
    created_at?: (string | null);
    updated_at?: (string | null);
};
