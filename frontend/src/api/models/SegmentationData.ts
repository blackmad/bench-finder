/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SegmentationData = {
    /**
     * Image filename
     */
    filename: string;
    /**
     * Type of detection data available
     */
    detection_type: string;
    /**
     * Segmentation detection data
     */
    bench_detections?: Array<Record<string, any>>;
    /**
     * Image dimensions [height, width]
     */
    image_shape?: (Array<number> | null);
    /**
     * Whether segmentation data is available
     */
    segmentation_available?: boolean;
    /**
     * Roboflow detection data
     */
    roboflow_detections?: Array<Record<string, any>>;
    /**
     * Whether bounding box data is available
     */
    bounding_box_available?: boolean;
    /**
     * Detection confidence score
     */
    confidence_score?: number;
    /**
     * Detection data source
     */
    source?: string;
};

