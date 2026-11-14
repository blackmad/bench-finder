/**
 * Shapes of the static files written by `bench-finder publish` (plan row 4.2).
 * Reads come from these files; nothing here talks to the Worker.
 */

export type FacingMethod = "osm_tag" | "vlm" | "geometry" | "human"
export type BenchType = "backrest" | "backless" | "picnic" | "other"
export type FacesCategory =
  | "water"
  | "street"
  | "park"
  | "square"
  | "wall"
  | "playground"
  | "other"

/** Responsive renditions keyed by pixel width, e.g. { "400": "img/ab-400.avif" }. */
export type ImageUrls = Record<string, string>

export interface BenchProps {
  id: number
  lat: number
  lng: number
  /** Degrees clockwise from north; null when unknown. */
  facing: number | null
  facing_confidence: number | null
  facing_method: FacingMethod | null
  /** Backless benches only have an axis, not a direction. */
  axis_only: boolean
  bench_type: BenchType | null
  backrest: boolean | null
  faces_category: FacesCategory | null
  hero_key: string | null
  hero_urls: ImageUrls | null
  /** Short street address, e.g. "Javakade 622". */
  address: string | null
}

export interface BenchFeature {
  type: "Feature"
  geometry: { type: "Point"; coordinates: [number, number] }
  properties: BenchProps
}

export interface BenchCollection {
  type: "FeatureCollection"
  features: BenchFeature[]
}

export interface Manifest {
  version: number
  generated_at: string
  count: number
  /** File name of the content-hashed GeoJSON, relative to the data base. */
  benches: string
  /** Directory of per-bench JSON files, relative to the data base. */
  bench_dir: string
}

export interface GalleryImage {
  urls: ImageUrls
  width: number
  height: number
  /** Camera heading in degrees; null when not recorded. */
  heading: number | null
}

export interface BenchDetail extends BenchProps {
  material: string | null
  address_full: {
    street: string | null
    number: string | null
    postcode: string | null
    city: string | null
    country: string | null
  }
  gallery: GalleryImage[]
  embed_pano_id: string | null
  embed_heading_deg: number | null
}
