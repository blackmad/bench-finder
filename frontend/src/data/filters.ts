/**
 * Home-page filters: what they match, how many benches each option would
 * leave, which controls the data can support, and how they sit in the URL.
 *
 * A control is offered only when at least MIN_FIELD benches carry its field,
 * so a filter lights up by itself once the published data has it.
 */
import { facingKind, sectorOf } from "./facing"
import type {
  BenchFeature,
  BenchProps,
  BenchType,
  FacesCategory,
} from "./types"

export const MIN_FIELD = 3

export type Tri = "yes" | "no"
export type FacingFilter = "known" | "mapped" | "estimated"
export type MaterialGroup =
  | "wood"
  | "metal"
  | "stone"
  | "concrete"
  | "plastic"
  | "other"
export type SeatBucket = "1-2" | "3" | "4" | "5+"

export interface Filters {
  /** Only benches with a photograph. */
  photo: boolean
  facing: FacingFilter | null
  /** Selected 45-degree facing sectors, 0 = N, clockwise. */
  dirs: ReadonlySet<number>
  backrest: Tri | null
  materials: ReadonlySet<MaterialGroup>
  lit: Tri | null
  seats: ReadonlySet<SeatBucket>
  faces: ReadonlySet<FacesCategory>
  types: ReadonlySet<BenchType>
}

export const NO_FILTERS: Filters = {
  photo: false,
  facing: null,
  dirs: new Set(),
  backrest: null,
  materials: new Set(),
  lit: null,
  seats: new Set(),
  faces: new Set(),
  types: new Set(),
}

export const SECTORS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"] as const
export const SECTOR_LONG = [
  "north",
  "north-east",
  "east",
  "south-east",
  "south",
  "south-west",
  "west",
  "north-west",
] as const

export const MATERIALS: MaterialGroup[] = [
  "wood",
  "metal",
  "stone",
  "concrete",
  "plastic",
  "other",
]
export const SEAT_BUCKETS: SeatBucket[] = ["1-2", "3", "4", "5+"]
export const FACES: FacesCategory[] = [
  "water",
  "park",
  "square",
  "street",
  "playground",
  "wall",
  "other",
]
export const TYPES: BenchType[] = ["backrest", "backless", "picnic", "other"]
const FACING: FacingFilter[] = ["known", "mapped", "estimated"]

const METAL =
  /^(metal|steel|stainless_steel|iron|cast_iron|aluminium|aluminum|bronze)$/
const STONE = /^(stone|granite|marble|sandstone|brick)$/

/** OSM material values ("wood;steel") folded into the groups the panel offers. */
export function materialGroups(m: string | null | undefined): MaterialGroup[] {
  if (!m) return []
  const out = new Set<MaterialGroup>()
  for (const raw of m.toLowerCase().split(";")) {
    const v = raw.trim()
    if (!v) continue
    if (v === "wood" || v === "timber") out.add("wood")
    else if (METAL.test(v)) out.add("metal")
    else if (STONE.test(v)) out.add("stone")
    else if (v === "concrete") out.add("concrete")
    else if (v === "plastic" || v === "recycled_plastic") out.add("plastic")
    else out.add("other")
  }
  return [...out]
}

export function seatBucket(n: number | null | undefined): SeatBucket | null {
  if (n == null || !Number.isFinite(n) || n < 1) return null
  return n <= 2 ? "1-2" : n === 3 ? "3" : n === 4 ? "4" : "5+"
}

const triOf = (v: boolean | null | undefined): Tri | null =>
  v === true ? "yes" : v === false ? "no" : null

/** The filter groups, in panel order. Each can be left out of a match. */
export type Group =
  | "photo"
  | "facing"
  | "dirs"
  | "backrest"
  | "materials"
  | "lit"
  | "seats"
  | "faces"
  | "types"

function passesGroup(p: BenchProps, f: Filters, g: Group): boolean {
  switch (g) {
    case "photo":
      return !f.photo || Boolean(p.hero_urls)
    case "facing": {
      if (!f.facing) return true
      const k = facingKind(p)
      return f.facing === "known" ? k !== null : k === f.facing
    }
    case "dirs":
      return (
        !f.dirs.size || (p.facing !== null && f.dirs.has(sectorOf(p.facing)))
      )
    case "backrest":
      return !f.backrest || triOf(p.backrest) === f.backrest
    case "materials":
      return (
        !f.materials.size ||
        materialGroups(p.material).some((m) => f.materials.has(m))
      )
    case "lit":
      return !f.lit || triOf(p.lit) === f.lit
    case "seats": {
      if (!f.seats.size) return true
      const b = seatBucket(p.seats)
      return b !== null && f.seats.has(b)
    }
    case "faces":
      return (
        !f.faces.size ||
        (p.faces_category !== null && f.faces.has(p.faces_category))
      )
    case "types":
      return (
        !f.types.size || (p.bench_type !== null && f.types.has(p.bench_type))
      )
  }
}

const GROUPS: Group[] = [
  "photo",
  "facing",
  "dirs",
  "backrest",
  "materials",
  "lit",
  "seats",
  "faces",
  "types",
]

/** Whether a bench passes every filter (except `skip`, for option counts). */
export function passes(p: BenchProps, f: Filters, skip?: Group): boolean {
  for (const g of GROUPS) {
    if (g !== skip && !passesGroup(p, f, g)) return false
  }
  return true
}

/** How many filter groups are narrowing the set (for the button badge). */
export function activeCount(f: Filters): number {
  return [
    f.photo,
    f.facing !== null,
    f.dirs.size > 0,
    f.backrest !== null,
    f.materials.size > 0,
    f.lit !== null,
    f.seats.size > 0,
    f.faces.size > 0,
    f.types.size > 0,
  ].filter(Boolean).length
}

export const isFiltered = (f: Filters) => activeCount(f) > 0

/** How many benches carry each field at all. */
export interface Coverage {
  total: number
  photo: number
  facing: number
  mapped: number
  estimated: number
  backrest: number
  material: number
  lit: number
  seats: number
  faces: number
  types: number
}

export function coverage(benches: BenchFeature[]): Coverage {
  const c: Coverage = {
    total: benches.length,
    photo: 0,
    facing: 0,
    mapped: 0,
    estimated: 0,
    backrest: 0,
    material: 0,
    lit: 0,
    seats: 0,
    faces: 0,
    types: 0,
  }
  for (const { properties: p } of benches) {
    if (p.hero_urls) c.photo++
    const k = facingKind(p)
    if (k) c.facing++
    if (k === "mapped") c.mapped++
    if (k === "estimated") c.estimated++
    if (p.backrest != null) c.backrest++
    if (materialGroups(p.material).length) c.material++
    if (p.lit != null) c.lit++
    if (seatBucket(p.seats)) c.seats++
    if (p.faces_category) c.faces++
    if (p.bench_type) c.types++
  }
  return c
}

/** Which controls the data supports (MIN_FIELD benches with the field). */
export function offered(c: Coverage) {
  const ok = (n: number) => n >= MIN_FIELD
  return {
    // A photo filter only means something when some benches lack one.
    photo: ok(c.photo) && c.photo < c.total,
    facing: ok(c.facing),
    // Mapped vs estimated is a choice only when both kinds exist.
    facingSplit: ok(c.mapped) && ok(c.estimated),
    backrest: ok(c.backrest),
    materials: ok(c.material),
    lit: ok(c.lit),
    seats: ok(c.seats),
    faces: ok(c.faces),
    types: ok(c.types),
  }
}
export type Offered = ReturnType<typeof offered>

/**
 * For each option, how many benches would match if it were chosen, given the
 * other groups as they stand. Multi-choice groups count the option alone.
 */
export interface OptionCounts {
  photo: number
  facing: Record<FacingFilter, number>
  dirs: number[]
  backrest: Record<Tri, number>
  materials: Record<MaterialGroup, number>
  lit: Record<Tri, number>
  seats: Record<SeatBucket, number>
  faces: Record<FacesCategory, number>
  types: Record<BenchType, number>
}

const zeros = <K extends string>(keys: readonly K[]) =>
  Object.fromEntries(keys.map((k) => [k, 0])) as Record<K, number>

export function optionCounts(
  benches: BenchFeature[],
  f: Filters
): OptionCounts {
  const out: OptionCounts = {
    photo: 0,
    facing: zeros(FACING),
    dirs: [0, 0, 0, 0, 0, 0, 0, 0],
    backrest: zeros(["yes", "no"] as const),
    materials: zeros(MATERIALS),
    lit: zeros(["yes", "no"] as const),
    seats: zeros(SEAT_BUCKETS),
    faces: zeros(FACES),
    types: zeros(TYPES),
  }
  for (const { properties: p } of benches) {
    if (p.hero_urls && passes(p, f, "photo")) out.photo++
    const k = facingKind(p)
    if (k && passes(p, f, "facing")) {
      out.facing.known++
      out.facing[k]++
    }
    if (p.facing !== null && passes(p, f, "dirs")) {
      out.dirs[sectorOf(p.facing)]++
    }
    const back = triOf(p.backrest)
    if (back && passes(p, f, "backrest")) out.backrest[back]++
    const mats = materialGroups(p.material)
    if (mats.length && passes(p, f, "materials")) {
      for (const m of mats) out.materials[m]++
    }
    const lit = triOf(p.lit)
    if (lit && passes(p, f, "lit")) out.lit[lit]++
    const seats = seatBucket(p.seats)
    if (seats && passes(p, f, "seats")) out.seats[seats]++
    if (p.faces_category && passes(p, f, "faces")) out.faces[p.faces_category]++
    if (p.bench_type && passes(p, f, "types")) out.types[p.bench_type]++
  }
  return out
}

export function toggled<T>(set: ReadonlySet<T>, v: T): Set<T> {
  const next = new Set(set)
  if (next.has(v)) next.delete(v)
  else next.add(v)
  return next
}

/* URL: short, readable keys so a filtered view can be shared. */

const PARAMS = [
  "photo",
  "facing",
  "dir",
  "back",
  "mat",
  "lit",
  "seats",
  "faces",
  "type",
] as const

export function filtersFromParams(sp: URLSearchParams): Filters {
  const list = (k: string) =>
    (sp.get(k) ?? "")
      .toLowerCase()
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  const pick = <T extends string>(k: string, allowed: readonly T[]) =>
    new Set(allowed.filter((a) => list(k).includes(a.toLowerCase())))
  const one = <T extends string>(k: string, allowed: readonly T[]) =>
    allowed.find((a) => a === sp.get(k)?.toLowerCase()) ?? null
  const dirs = new Set<number>()
  for (const d of list("dir")) {
    const i = SECTORS.findIndex((s) => s.toLowerCase() === d)
    if (i >= 0) dirs.add(i)
  }
  return {
    photo: sp.get("photo") === "1",
    facing: one("facing", FACING),
    dirs,
    backrest: one("back", ["yes", "no"] as const),
    materials: pick("mat", MATERIALS),
    lit: one("lit", ["yes", "no"] as const),
    seats: pick("seats", SEAT_BUCKETS),
    faces: pick("faces", FACES),
    types: pick("type", TYPES),
  }
}

/** Writes `f` into `sp` in place, removing keys for groups left open. */
export function filtersToParams(f: Filters, sp: URLSearchParams) {
  for (const k of PARAMS) sp.delete(k)
  const set = (k: string, v: string | null) => {
    if (v) sp.set(k, v)
  }
  const csv = <T extends string>(all: readonly T[], s: ReadonlySet<T>) =>
    all.filter((v) => s.has(v)).join(",")
  set("photo", f.photo ? "1" : null)
  set("facing", f.facing)
  set(
    "dir",
    [...f.dirs]
      .sort((a, b) => a - b)
      .map((i) => SECTORS[i].toLowerCase())
      .join(",")
  )
  set("back", f.backrest)
  set("mat", csv(MATERIALS, f.materials))
  set("lit", f.lit)
  set("seats", csv(SEAT_BUCKETS, f.seats))
  set("faces", csv(FACES, f.faces))
  set("type", csv(TYPES, f.types))
}

/** "Facing NE or E · backrest · wood" — the active filters in a few words. */
export function summary(f: Filters): string {
  const parts: string[] = []
  if (f.photo) parts.push("with a photo")
  if (f.dirs.size) {
    parts.push(
      `facing ${[...f.dirs]
        .sort((a, b) => a - b)
        .map((i) => SECTORS[i])
        .join(" or ")}`
    )
  }
  if (f.facing === "known" && !f.dirs.size) parts.push("facing known")
  if (f.facing === "mapped") parts.push("facing mapped")
  if (f.facing === "estimated") parts.push("facing estimated")
  if (f.backrest) parts.push(f.backrest === "yes" ? "backrest" : "no backrest")
  if (f.materials.size) parts.push(join(MATERIALS, f.materials))
  if (f.lit) parts.push(f.lit === "yes" ? "lit" : "not lit")
  if (f.seats.size) {
    parts.push(`seats ${join(SEAT_BUCKETS, f.seats).replace("1-2", "1–2")}`)
  }
  if (f.faces.size) parts.push(`looks at ${join(FACES, f.faces)}`)
  if (f.types.size) parts.push(join(TYPES, f.types))
  return parts.join(" · ")
}

function join<T extends string>(all: readonly T[], s: ReadonlySet<T>) {
  return all.filter((v) => s.has(v)).join(" or ")
}
