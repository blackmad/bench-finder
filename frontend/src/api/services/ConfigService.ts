/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { BaseHttpRequest } from "../core/BaseHttpRequest"
import type { CancelablePromise } from "../core/CancelablePromise"
import type { ApiInfoResponse } from "../models/ApiInfoResponse"
import type { ConfigResponse } from "../models/ConfigResponse"
export class ConfigService {
  constructor(public readonly httpRequest: BaseHttpRequest) {}
  /**
   * Health Check
   * Simple health check endpoint to verify server status
   * @returns string Successful Response
   * @throws ApiError
   */
  public healthCheckHealthGet(): CancelablePromise<Record<string, string>> {
    return this.httpRequest.request({
      method: "GET",
      url: "/health",
    })
  }
  /**
   * Get Application Configuration
   * Get default configuration values for the frontend application
   * @returns ConfigResponse Successful Response
   * @throws ApiError
   */
  public getConfigApiConfigGet(): CancelablePromise<ConfigResponse> {
    return this.httpRequest.request({
      method: "GET",
      url: "/api/config",
    })
  }
  /**
   * Get API Information
   * Get comprehensive API information including capabilities and limits
   * @returns ApiInfoResponse Successful Response
   * @throws ApiError
   */
  public getApiInfoApiInfoGet(): CancelablePromise<ApiInfoResponse> {
    return this.httpRequest.request({
      method: "GET",
      url: "/api/info",
    })
  }
  /**
   * Test 500 Error Endpoint
   * Test endpoint that triggers a 500 error to demonstrate stacktrace logging
   * @returns any Successful Response
   * @throws ApiError
   */
  public testErrorApiTestErrorGet(): CancelablePromise<any> {
    return this.httpRequest.request({
      method: "GET",
      url: "/api/test-error",
    })
  }
  /**
   * Test 400 Error Endpoint
   * Test endpoint that triggers a 400 error to demonstrate stacktrace logging
   * @returns any Successful Response
   * @throws ApiError
   */
  public test400ErrorApiTest400ErrorGet(): CancelablePromise<any> {
    return this.httpRequest.request({
      method: "GET",
      url: "/api/test-400-error",
    })
  }
  /**
   * Test Validation Error Endpoint
   * Test endpoint that triggers a validation error to demonstrate stacktrace logging
   * @returns any Successful Response
   * @throws ApiError
   */
  public testValidationErrorApiTestValidationErrorGet(): CancelablePromise<any> {
    return this.httpRequest.request({
      method: "GET",
      url: "/api/test-validation-error",
    })
  }
}
