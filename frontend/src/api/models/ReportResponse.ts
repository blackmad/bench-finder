/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BenchReportType } from './BenchReportType';
/**
 * Schema for bench report response.
 */
export type ReportResponse = {
    success: boolean;
    report_id: number;
    message: string;
    bench_id: number;
    report_type: BenchReportType;
    created_at: string;
};
