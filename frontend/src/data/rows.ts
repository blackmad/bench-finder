/** The home rail's rows. */
import type { BenchFeature } from "./types"

export const MIN_ROW = 3
export const STRIP_MAX = 12
export const ALL_MAX = 60

export interface Row {
  key: string
  title: string
  note: string
  benches: BenchFeature[]
}

/**
 * The rail: every photographed bench in view, nearest the map centre first
 * (`photos` must already be sorted). Themed rows (looks at water, on a gracht,
 * facing mapped...) were dropped on 2026-11-17: they mostly repeated this one.
 * Returns no rows only when there is no photographed bench in view.
 */
export function buildRows(photos: BenchFeature[]): Row[] {
  if (!photos.length) return []
  const few = photos.length < MIN_ROW
  return [
    {
      key: "near",
      title: few ? "In view on the map" : "Near the middle of the map",
      note: few ? "" : "Closest first",
      benches: photos,
    },
  ]
}
