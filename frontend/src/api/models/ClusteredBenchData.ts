/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClusterInfo } from './ClusterInfo';
import type { WebBenchData } from './WebBenchData';
/**
 * Schema for clustered bench data showing both cluster and individual bench info.
 */
export type ClusteredBenchData = {
    cluster: ClusterInfo;
    representative_bench: WebBenchData;
    all_benches: Array<WebBenchData>;
    distance_to_cluster_center: number;
};
