/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ImageListResponse } from '../models/ImageListResponse';
import type { SegmentationData } from '../models/SegmentationData';
import type { CancelablePromise } from '../core/CancelablePromise';
import type { BaseHttpRequest } from '../core/BaseHttpRequest';
export class ImagesService {
    constructor(public readonly httpRequest: BaseHttpRequest) {}
    /**
     * Serve Bench Images
     * Serve bench images from the images directory
     * @returns any Successful Response
     * @throws ApiError
     */
    public serveImageImagesFilenameGet({
        filename,
    }: {
        /**
         * Image filename
         */
        filename: string,
    }): CancelablePromise<any> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/images/{filename}',
            path: {
                'filename': filename,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Detection Visualization Data
     * Get detection visualization data for a specific image
     * @returns SegmentationData Successful Response
     * @throws ApiError
     */
    public getImageSegmentationApiImageImageIdSegmentationGet({
        imageId,
    }: {
        /**
         * Image ID
         */
        imageId: number,
    }): CancelablePromise<SegmentationData> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/image/{image_id}/segmentation',
            path: {
                'image_id': imageId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Bench Images
     * Get all images for a specific bench with metadata
     * @returns ImageListResponse Successful Response
     * @throws ApiError
     */
    public getBenchImagesApiBenchBenchIdImagesGet({
        benchId,
    }: {
        /**
         * Bench ID
         */
        benchId: number,
    }): CancelablePromise<ImageListResponse> {
        return this.httpRequest.request({
            method: 'GET',
            url: '/api/bench/{bench_id}/images',
            path: {
                'bench_id': benchId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
