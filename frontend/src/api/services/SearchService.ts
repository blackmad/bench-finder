/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SearchListResponse } from '../models/SearchListResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class SearchService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * List Available Searches
     * Get list of completed search operations with bench counts
     * @returns SearchListResponse Successful Response
     * @throws ApiError
     */
    public getSearchesApiSearchesGet(): CancelablePromise<SearchListResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/searches',
            errors: {
                500: `Internal server error`,
            },
        });
    }
}
