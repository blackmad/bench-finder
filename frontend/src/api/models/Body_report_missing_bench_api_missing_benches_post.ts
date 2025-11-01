/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type Body_report_missing_bench_api_missing_benches_post = {
  /**
   * Bench latitude
   */
  lat: number
  /**
   * Bench longitude
   */
  lng: number
  /**
   * Description of the bench
   */
  description?: string | null
  /**
   * How location was determined (gps, map_click)
   */
  location_method?: string
  /**
   * User's GPS latitude
   */
  user_location_lat?: number | null
  /**
   * User's GPS longitude
   */
  user_location_lng?: number | null
  /**
   * GPS accuracy in meters
   */
  accuracy_meters?: number | null
  /**
   * Base64 encoded image data
   */
  image_data?: string | null
}
