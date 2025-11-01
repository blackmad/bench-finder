/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BaseHttpRequest } from "../core/BaseHttpRequest"
import type { CancelablePromise } from "../core/CancelablePromise"
import type { Body_report_bad_bench_api_benches__bench_id__report_post } from "../models/Body_report_bad_bench_api_benches__bench_id__report_post"
import type { Body_report_missing_bench_api_missing_benches_post } from "../models/Body_report_missing_bench_api_missing_benches_post"
import type { MissingBenchReportResponse } from "../models/MissingBenchReportResponse"
import type { ReportResponse } from "../models/ReportResponse"
export class ReportingService {
  constructor(public readonly httpRequest: BaseHttpRequest) {}
  /**
   * Report Bad Bench Detection
   * Report a bad bench detection with optional description and image data
   * @returns ReportResponse Successful Response
   * @throws ApiError
   */
  public reportBadBenchApiBenchesBenchIdReportPost({
    benchId,
    requestBody,
  }: {
    /**
     * Bench ID to report
     */
    benchId: number
    requestBody?: Body_report_bad_bench_api_benches__bench_id__report_post
  }): CancelablePromise<ReportResponse> {
    return this.httpRequest.request({
      method: "POST",
      url: "/api/benches/{bench_id}/report",
      path: {
        bench_id: benchId,
      },
      body: requestBody,
      mediaType: "application/json",
      errors: {
        400: `Invalid bench ID or request data`,
        404: `Bench not found`,
        422: `Validation Error`,
        500: `Internal server error`,
      },
    })
  }
  /**
   * Report Missing Bench
   * Report a missing bench at a specific location with optional photo
   * @returns MissingBenchReportResponse Successful Response
   * @throws ApiError
   */
  public reportMissingBenchApiMissingBenchesPost({
    requestBody,
  }: {
    requestBody: Body_report_missing_bench_api_missing_benches_post
  }): CancelablePromise<MissingBenchReportResponse> {
    return this.httpRequest.request({
      method: "POST",
      url: "/api/missing-benches",
      body: requestBody,
      mediaType: "application/json",
      errors: {
        400: `Invalid location or request data`,
        413: `Image file too large`,
        422: `Validation Error`,
        500: `Internal server error`,
      },
    })
  }
}
