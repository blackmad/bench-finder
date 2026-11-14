import type { BenchProps, FacesCategory } from "./types"

const WINDS = [
  "N",
  "NNE",
  "NE",
  "ENE",
  "E",
  "ESE",
  "SE",
  "SSE",
  "S",
  "SSW",
  "SW",
  "WSW",
  "W",
  "WNW",
  "NW",
  "NNW",
] as const

export type Wind = (typeof WINDS)[number]

export const windName = (deg: number): Wind =>
  WINDS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16]

export const WIND_LONG: Record<Wind, string> = {
  N: "north",
  NNE: "north-north-east",
  NE: "north-east",
  ENE: "east-north-east",
  E: "east",
  ESE: "east-south-east",
  SE: "south-east",
  SSE: "south-south-east",
  S: "south",
  SSW: "south-south-west",
  SW: "south-west",
  WSW: "west-south-west",
  W: "west",
  WNW: "west-north-west",
  NW: "north-west",
  NNW: "north-north-west",
}

const FACES: Record<FacesCategory, string> = {
  water: "the water",
  park: "the park",
  street: "the street",
  square: "the square",
  wall: "a wall",
  playground: "a playground",
  other: "something",
}

export const facesText = (f: FacesCategory | null): string =>
  (f && FACES[f]) || "something"

/** Known facings are drawn in ink; estimated ones in airmail blue. */
export const isKnown = (p: Pick<BenchProps, "facing_method">): boolean =>
  p.facing_method === "osm_tag" || p.facing_method === "human"

export const sectorOf = (deg: number): number =>
  Math.round((((deg % 360) + 360) % 360) / 45) % 8

/**
 * How much the facing can be trusted: "mapped" (OSM tag or a visitor),
 * "estimated" (model output), or null when there is no facing at all.
 * Nothing draws a needle for null; estimated needles are dashed and marked ≈.
 */
export type FacingKind = "mapped" | "estimated"
export const facingKind = (
  p: Pick<BenchProps, "facing" | "facing_method">
): FacingKind | null =>
  p.facing === null ? null : isKnown(p) ? "mapped" : "estimated"

/** "NE 52°" for mapped facings, "≈ NE 52°" for estimated ones. */
export const facingShort = (
  p: Pick<BenchProps, "facing" | "facing_method">
): string | null => {
  const k = facingKind(p)
  if (k === null || p.facing === null) return null
  const deg = Math.round(p.facing)
  return `${k === "estimated" ? "≈ " : ""}${windName(deg)} ${deg}°`
}
