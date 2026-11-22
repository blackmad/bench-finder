import type { BenchDetail } from "./types"

/** Google panorama ids are 22 url-safe base64 characters. */
const GOOGLE_PANO = /^[A-Za-z0-9_-]{22}$/

export interface StreetViewTarget {
  /** A Google panorama id, when the view is Google's. */
  pano: string | null
  /** Otherwise the camera position: Google opens its nearest panorama. */
  at: [number, number] | null
  heading: number
}

/**
 * What the bench page's Street View opens, or null for nothing. Apple, city
 * and other panorama ids never reach Google (they break the embed with
 * "Invalid 'pano' parameter"); those views open at their camera position.
 */
export function streetViewTarget(
  d: Pick<
    BenchDetail,
    "embed_pano_id" | "embed_heading_deg" | "embed_lat" | "embed_lng"
  >
): StreetViewTarget | null {
  const at: [number, number] | null =
    d.embed_lat != null && d.embed_lng != null
      ? [d.embed_lat, d.embed_lng]
      : null
  const pano =
    d.embed_pano_id && GOOGLE_PANO.test(d.embed_pano_id)
      ? d.embed_pano_id
      : null
  if (!pano && !at) return null
  return { pano, at, heading: d.embed_heading_deg ?? 0 }
}

/** The embed iframe and the "open in Google Maps" link for a target. */
export function streetViewUrls(
  t: StreetViewTarget,
  key: string | undefined
): { embed: string | null; out: string } {
  const h = Math.round(t.heading)
  const pano = t.pano ? encodeURIComponent(t.pano) : null
  const at = t.at ? `${t.at[0]},${t.at[1]}` : ""
  const view = `heading=${h}&pitch=0&fov=80`
  return {
    embed: key
      ? `https://www.google.com/maps/embed/v1/streetview?key=${key}&${
          pano ? `pano=${pano}` : `location=${at}`
        }&${view}`
      : null,
    out: `https://www.google.com/maps/@?api=1&map_action=pano&${
      pano ? `pano=${pano}` : `viewpoint=${at}`
    }&${view}`,
  }
}
