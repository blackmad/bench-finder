/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LocationMethod } from './LocationMethod';
/**
 * Schema for missing bench report response.
 */
export type MissingBenchReportResponse = {
    success: boolean;
    report_id: number;
    message: string;
    location: Record<string, number>;
    location_method: LocationMethod;
    has_image: boolean;
    created_at: string;
};
