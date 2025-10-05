/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ConfigResponse } from '../models/ConfigResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
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
            method: 'GET',
            url: '/health',
        });
    }
    /**
     * Get Application Configuration
     * Get default configuration values for the frontend application
     * @returns ConfigResponse Successful Response
     * @throws ApiError
     */
    public getConfigApiConfigGet(): CancelablePromise<ConfigResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/config',
        });
    }
    /**
     * Get API Information
     * Get comprehensive API information including capabilities and limits
     * @returns any Successful Response
     * @throws ApiError
     */
    public getApiInfoApiInfoGet(): CancelablePromise<Record<string, any>> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/info',
        });
    }
}
