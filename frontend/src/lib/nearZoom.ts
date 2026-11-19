/** How far "Near me" must reach to show a handful of places, as a map zoom. */

const EARTH_M = 40_075_016.686
export const NEAR_COUNT = 8
export const FAR_M = 5_000 // nearest bench farther than this: outside coverage
/** About a five-minute walk (5 km/h). */
export const WALK_M = 400

export function metresBetween(
  a: [number, number],
  b: [number, number]
): number {
  const [lng1, lat1] = a
  const [lng2, lat2] = b
  const x = (lng2 - lng1) * Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180)
  return Math.hypot(x, lat2 - lat1) * 111_320
}

/** Distance to the `n`th nearest point (all of them when there are fewer). */
export function reachMetres(
  here: [number, number],
  points: [number, number][],
  n = NEAR_COUNT
): number {
  const d = points.map((p) => metresBetween(here, p)).sort((a, b) => a - b)
  return d.length ? d[Math.min(n, d.length) - 1] : Number.POSITIVE_INFINITY
}

/**
 * How far "Near me" shows: out to about eight places, but no further than a
 * five-minute walk, unless that would leave no bench in view at all.
 */
export function nearRadius(
  here: [number, number],
  points: [number, number][]
): number {
  return Math.max(
    Math.min(reachMetres(here, points), WALK_M),
    reachMetres(here, points, 1)
  )
}

/** Zoom at which a circle of `radiusM` fits in `px` pixels (the map's short side). */
export function zoomForRadius(
  radiusM: number,
  lat: number,
  px: number
): number {
  const mPerPxAtZ0 = (EARTH_M * Math.cos((lat * Math.PI) / 180)) / 512
  const want = (radiusM * 2.4) / Math.max(px, 200) // a margin around the circle
  return Math.min(17, Math.max(12, Math.log2(mPerPxAtZ0 / want)))
}
