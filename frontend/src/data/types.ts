/**
 * Shapes of the static files written by `bench-finder publish` (plan row 4.2).
 * Reads come from these files; nothing here talks to the Worker.
 */

export type FacingMethod =
  | "osm_tag"
  | "vlm"
  | "geometry"
  | "human"
  /** Turned toward the nearest water edge. */
  | "water_edge"
  /** Water behind the backrest (checked by a vision model): faces away from it. */
  | "water_back"
export type BenchType = "backrest" | "backless" | "picnic" | "other"
export type FacesCategory =
  | "water"
  | "park"
  | "residential_street"
  | "busy_street"
  | "square"
  | "courtyard"
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
  /** OSM `material`, lower-cased; may hold several values ("wood;steel"). */
  material?: string | null
  /** OSM `seats`. */
  seats?: number | null
  /** OSM `lit`. */
  lit?: boolean | null
  hero_key: string | null
  hero_urls: ImageUrls | null
  /** WebP fallbacks for `hero_urls`, same widths. */
  hero_urls_webp?: ImageUrls | null
  /** Pixel size of the hero source, for explicit width/height. */
  hero_width?: number | null
  hero_height?: number | null
  /**
   * Where the bench centre sits in the hero, as fractions [x, y] of its width
   * and height; null or absent when unknown. Cropped heroes keep it in view.
   */
  hero_focus?: [number, number] | null
  /** Short street address, e.g. "Javakade 622". */
  address: string | null
  /**
   * A feature is a place: benches a few metres apart, led by the one with the
   * best photo (`id`). Every member id, leader first; absent in old data.
   */
  bench_ids?: number[]
  /** Benches at this place (1 when alone). */
  count?: number
}

/** Another bench at the same place, as listed in a bench file. */
export type PlaceMember = Pick<
  BenchProps,
  | "id"
  | "lat"
  | "lng"
  | "address"
  | "facing"
  | "facing_confidence"
  | "facing_method"
  | "axis_only"
  | "backrest"
  | "bench_type"
  | "faces_category"
  | "hero_key"
  | "hero_urls"
  | "hero_urls_webp"
  | "hero_width"
  | "hero_height"
  | "hero_focus"
>

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
  /** Prefix for `benches` and `bench_dir` (publish writes "data"); absent in the dev fixture. */
  data_base?: string
  /** Where image renditions live; image URLs already include it. */
  image_base?: string
  counts?: { benches: number; with_hero: number; images: number }
}

export interface GalleryImage {
  /** The image's database id (publishes from Nov 2026 on): picks and suggestions name it. */
  id?: number
  urls: ImageUrls
  urls_webp?: ImageUrls
  width: number
  height: number
  /** Camera heading in degrees; null when not recorded. */
  heading: number | null
  camera_bearing_deg?: number | null
  kind?: string | null
  /** "YYYY-MM" when the panorama date is known. */
  pano_date?: string | null
}

export interface BenchDetail extends BenchProps {
  /** The bench's outline in the hero photo (0..1), drawn on hover. */
  hero_outline?: [number, number][] | null
  /** Raw OpenStreetMap tags, when the bench came from OSM. */
  tags?: Record<string, string>
  /** Free text on what the bench looks at, e.g. "canal and houseboats". */
  faces_text?: string | null
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
  /** Camera position of the embed view; used when there is no Google pano id. */
  embed_lat?: number | null
  embed_lng?: number | null
  /** The place this bench belongs to; `benches` are the others there. */
  place?: { id: number; count: number; benches: PlaceMember[] }
}
