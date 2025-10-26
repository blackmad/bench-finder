/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BenchReportType } from './BenchReportType';
export type Body_report_bad_bench_api_benches__bench_id__report_post = {
    /**
     * Type of report
     */
    report_type?: BenchReportType;
    /**
     * Optional description of the issue
     */
    description?: (string | null);
    /**
     * Specific image ID being reported
     */
    image_id?: (number | null);
    /**
     * User's GPS latitude
     */
    user_location_lat?: (number | null);
    /**
     * User's GPS longitude
     */
    user_location_lng?: (number | null);
};
