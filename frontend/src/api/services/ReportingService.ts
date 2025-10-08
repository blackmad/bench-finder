/* generated manually for reporting functionality */
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';

export interface ReportBadBenchRequest {
  report_type?: string;
  description?: string;
  image_id?: number;
  user_location_lat?: number;
  user_location_lng?: number;
}

export interface ReportMissingBenchRequest {
  lat: number;
  lng: number;
  description?: string;
  location_method?: string;
  user_location_lat?: number;
  user_location_lng?: number;
  accuracy_meters?: number;
  image_data?: string;
}

export interface ReportResponse {
  success: boolean;
  report_id: number;
  message: string;
  created_at: string;
}

export class ReportingService {
  constructor(public readonly httpRequest: BaseHttpRequest) {}

  /**
   * Report Bad Bench Detection
   * Report a bad bench detection with optional description and image data
   * @returns ReportResponse Successful Response
   * @throws ApiError
   */
  public reportBadBench({
    benchId,
    requestBody,
  }: {
    benchId: number;
    requestBody: ReportBadBenchRequest;
  }): CancelablePromise<ReportResponse> {
    return this.httpRequest.request({
      method: 'POST',
      url: '/api/benches/{bench_id}/report',
      path: {
        'bench_id': benchId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        400: `Invalid bench ID or request data`,
        404: `Bench not found`,
        500: `Internal server error`,
      },
    });
  }

  /**
   * Report Missing Bench
   * Report a missing bench at a specific location with optional photo
   * @returns ReportResponse Successful Response
   * @throws ApiError
   */
  public reportMissingBench({
    requestBody,
  }: {
    requestBody: ReportMissingBenchRequest;
  }): CancelablePromise<ReportResponse> {
    return this.httpRequest.request({
      method: 'POST',
      url: '/api/missing-benches',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        400: `Invalid location or request data`,
        413: `Image file too large`,
        500: `Internal server error`,
      },
    });
  }
}