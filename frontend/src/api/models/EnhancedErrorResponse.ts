/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Enhanced error response with detailed debugging information.
 */
export type EnhancedErrorResponse = {
    /**
     * Human-readable error message
     */
    error: string;
    /**
     * Machine-readable error code for programmatic handling
     */
    error_code?: (string | null);
    /**
     * Additional error details and context
     */
    detail?: (string | null);
    /**
     * Suggested actions to resolve the error
     */
    suggestions?: (Array<string> | null);
    /**
     * When the error occurred
     */
    timestamp?: string;
};
