import { sectorOf } from "../data/facing"
import type { BenchProps, FacesCategory } from "../data/types"

export interface Filters {
  faces: ReadonlySet<FacesCategory>
  backrest: boolean
  /** Selected 45-degree facing sectors, 0 = N. */
  sectors: ReadonlySet<number>
}

export const NO_FILTERS: Filters = {
  faces: new Set(),
  backrest: false,
  sectors: new Set(),
}

export function passes(p: BenchProps, f: Filters): boolean {
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
