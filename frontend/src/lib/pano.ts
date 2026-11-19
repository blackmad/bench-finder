/** A street panorama a missing-bench report points at, and the bearing to the bench. */
export interface PanoPick {
  source: "amsterdam" | "google"
  id: string
  /** Compass bearing from the panorama to the bench, 0 <= h < 360. */
  heading: number
  url?: string
}

export interface CityPano {
  id: string
  lat: number
  lng: number
  date: string
  /** Equirectangular, 2000 x 1000; its centre column looks north. */
  image: string
  distance: number
}

const API = "https://api.data.amsterdam.nl/panorama/panoramas/"

export const norm = (deg: number) => ((deg % 360) + 360) % 360

/** Metres and compass bearing from a to b (flat earth, fine within a few hundred m). */
export function offset(
  a: { lat: number; lng: number },
  b: { lat: number; lng: number }
) {
  const k = Math.cos((a.lat * Math.PI) / 180)
  const dx = (b.lng - a.lng) * 111_320 * k
  const dy = (b.lat - a.lat) * 110_574
  return {
    distance: Math.hypot(dx, dy),
    bearing: norm((Math.atan2(dx, dy) * 180) / Math.PI),
  }
}

/** Equirectangular column (0..1 across the image) <-> compass heading. Centre = north. */
export const headingAt = (fraction: number) => norm((fraction - 0.5) * 360)
export const fractionOf = (heading: number) => norm(heading + 180) / 360

/**
 * The City of Amsterdam's newest panoramas within `radius` metres of a point,
 * nearest first, one per spot (panoramas closer than 2 m to a nearer one are
 * dropped), at most 12. Empty outside Amsterdam.
 */
export async function cityPanos(
  at: { lat: number; lng: number },
  radius = 60,
  signal?: AbortSignal
): Promise<CityPano[]> {
  const q = `${API}?near=${at.lng},${at.lat}&radius=${radius}&newest_in_range=true&page_size=100`
  const r = await fetch(q, { signal })
  if (!r.ok) throw new Error(`panoramas: HTTP ${r.status}`)
  const data = (await r.json()) as {
    _embedded?: {
      panoramas?: {
        pano_id: string
        timestamp: string
        geometry: { coordinates: [number, number, number?] }
        _links: { equirectangular_small: { href: string } }
      }[]
    }
  }
  const all = (data._embedded?.panoramas ?? [])
    .map((p) => {
      const [lng, lat] = p.geometry.coordinates
      return {
        id: p.pano_id,
        lat,
        lng,
        date: p.timestamp.slice(0, 10),
        image: p._links.equirectangular_small.href,
        distance: offset(at, { lat, lng }).distance,
      }
    })
    .sort((a, b) => a.distance - b.distance)
  const out: CityPano[] = []
  for (const p of all) {
    if (out.every((o) => offset(o, p).distance >= 2)) out.push(p)
  }
  return out.slice(0, 12)
}

/**
 * A Google Maps Street View link: `.../@52.36,4.85,3a,75y,256.02h,86.01t/data=...!1s<pano>!2e0...`.
 * Returns the panorama id, the heading the viewer looked along, and its position.
 */
export function parseStreetViewLink(
  link: string
): (PanoPick & { lat: number; lng: number }) | null {
  let u: URL
  try {
    u = new URL(link.trim())
  } catch {
    return null
  }
  if (
    !/(^|\.)google\.[a-z.]+$/.test(u.hostname) &&
    u.hostname !== "maps.app.goo.gl"
  )
    return null
  const s = decodeURIComponent(u.pathname + u.search)
  const at = s.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?),([^/]*)/)
  const pano = s.match(/!1s([A-Za-z0-9_-]{10,})!2e/)
  if (!at || !pano) return null
  const h = at[3].match(/(?:^|,)(-?\d+(?:\.\d+)?)h(?:,|$)/)
  return {
    source: "google",
    id: pano[1],
    heading: h ? Math.round(norm(Number(h[1])) * 10) / 10 : 0,
    url: link.trim(),
    lat: Number(at[1]),
    lng: Number(at[2]),
  }
}
