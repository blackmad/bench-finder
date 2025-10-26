/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BoundingBox } from './BoundingBox';
import type { Polygon } from './Polygon';
/**
 * API-specific detection item with optional bbox for responses.
 */
export type ApiDetectionItem = {
    detection_id: number;
    /**
     * Confidence score between 0 and 1
     */
    confidence: number;
    /**
     * Optional bounding box
     */
    bbox?: (BoundingBox | null);
    /**
     * Class name of the detected object
     */
    class_name?: string;
    /**
     * Optional polygon for segmentation
     */
    polygon?: (Polygon | null);
};
