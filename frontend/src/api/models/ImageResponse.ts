/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ImageResponse = {
    /**
     * Image identifier
     */
    id: number;
    /**
     * Associated bench ID
     */
    bench_id: number;
    /**
     * Camera heading in degrees
     */
    heading: number;
    /**
     * File system path
     */
    filepath?: (string | null);
    /**
     * Image filename
     */
    filename?: (string | null);
    /**
     * File size in bytes
     */
    file_size?: (number | null);
    /**
     * Whether capture was successful
     */
    capture_success: boolean;
    /**
     * Error message if capture failed
     */
    capture_error?: (string | null);
    /**
     * When the image was created
     */
    created_at: string;
};

