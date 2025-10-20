/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WebBenchData } from './WebBenchData';
export type RandomBenchResponse = {
    /**
     * Randomly selected bench
     */
    bench: WebBenchData;
    /**
     * Selection metadata
     */
    selection_info?: Record<string, any>;
};
