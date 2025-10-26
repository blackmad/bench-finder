/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ApiDetectionItem } from './ApiDetectionItem';
/**
 * Schema for image data with detection items.
 */
export type ImageWithDetectionData = {
    image_id: number;
    filename: string;
    heading: number;
    capture_success: boolean;
    /**
     * List of detection items for this image
     */
    detection_items?: Array<ApiDetectionItem>;
};
