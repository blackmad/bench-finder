/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WebBenchData = {
    /**
     * Unique bench identifier
     */
    id: number;
    /**
     * External provider ID
     */
    provider_id?: (string | null);
    /**
     * Latitude coordinate
     */
    lat: number;
    /**
     * Longitude coordinate
     */
    lng: number;
    /**
     * Additional metadata tags
     */
    tags?: Record<string, any>;
    /**
     * Data source (osm or mapillary)
     */
    source: string;
    /**
     * External system identifier
     */
    external_id?: (string | null);
    /**
     * Highest detection confidence
     */
    best_confidence: number;
    /**
     * Roboflow detection confidence
     */
    roboflow_confidence?: number;
    /**
     * Ultralytics detection confidence
     */
    ultralytics_confidence?: number;
    /**
     * Mapillary detection confidence
     */
    mapillary_confidence?: number;
    /**
     * Primary detection method used
     */
    detection_type: string;
    /**
     * Whether segmentation data is available
     */
    has_segmentation: boolean;
    /**
     * Number of associated images
     */
    image_count: number;
    /**
     * List of image filenames
     */
    image_filenames?: Array<string>;
    /**
     * List of image IDs
     */
    image_ids?: Array<number>;
    /**
     * Distance from reference point in meters
     */
    distance_meters: number;
    /**
     * Distance from reference point in kilometers
     */
    distance_km: number;
};
