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
