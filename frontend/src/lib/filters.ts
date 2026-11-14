import { sectorOf } from "../data/facing"
import type { BenchProps, BenchType, FacesCategory } from "../data/types"

export interface Filters {
  types: ReadonlySet<BenchType>
  faces: ReadonlySet<FacesCategory>
  backrest: boolean
  /** Selected 45-degree facing sectors, 0 = N. */
  sectors: ReadonlySet<number>
}

export const NO_FILTERS: Filters = {
  types: new Set(),
  faces: new Set(),
  backrest: false,
  sectors: new Set(),
}

export function passes(p: BenchProps, f: Filters): boolean {
  if (f.types.size && !(p.bench_type && f.types.has(p.bench_type))) {
    return false
  }
  if (f.faces.size && !(p.faces_category && f.faces.has(p.faces_category))) {
    return false
  }
  if (f.backrest && p.backrest !== true) return false
  if (f.sectors.size) {
    if (p.facing === null || !f.sectors.has(sectorOf(p.facing))) return false
  }
  return true
}

export function toggled<T>(set: ReadonlySet<T>, v: T): Set<T> {
  const next = new Set(set)
  if (next.has(v)) next.delete(v)
  else next.add(v)
  return next
}

const TYPES: BenchType[] = ["backrest", "backless", "picnic", "other"]
const FACES: FacesCategory[] = [
  "water",
  "street",
  "park",
  "square",
  "wall",
  "playground",
  "other",
]

/** Filters live in the query string so a view can be shared and back works. */
export function filtersFromParams(sp: URLSearchParams): Filters {
  const list = (k: string) => (sp.get(k) ?? "").split(",").filter(Boolean)
  return {
    types: new Set(TYPES.filter((t) => list("type").includes(t))),
    faces: new Set(FACES.filter((t) => list("faces").includes(t))),
    backrest: sp.get("back") === "1",
    sectors: new Set(
      list("dir")
        .map(Number)
        .filter((n) => Number.isInteger(n) && n >= 0 && n < 8)
    ),
  }
}

export function filtersToParams(f: Filters, sp: URLSearchParams) {
  const set = (k: string, v: string) => {
    if (v) sp.set(k, v)
    else sp.delete(k)
  }
  set("type", [...f.types].sort().join(","))
  set("faces", [...f.faces].sort().join(","))
  set("back", f.backrest ? "1" : "")
  set("dir", [...f.sectors].sort((a, b) => a - b).join(","))
}

export interface Viewport {
  lat: number
  lng: number
  z: number
}

export function viewportFromParams(sp: URLSearchParams): Viewport | null {
  const lat = Number.parseFloat(sp.get("lat") ?? "")
  const lng = Number.parseFloat(sp.get("lng") ?? "")
  const z = Number.parseFloat(sp.get("z") ?? "")
  if (![lat, lng, z].every(Number.isFinite)) return null
  if (Math.abs(lat) > 85 || Math.abs(lng) > 180 || z < 0 || z > 22) return null
  return { lat, lng, z }
}

export function viewportToParams(v: Viewport, sp: URLSearchParams) {
  sp.set("lat", v.lat.toFixed(5))
  sp.set("lng", v.lng.toFixed(5))
  sp.set("z", v.z.toFixed(2))
}
