/**
 * The rail's rows, built from fields the published GeoJSON actually carries:
 * address, backrest, facing and facing_method, what the bench looks at, and
 * whether there is a photo. The first row holds every photographed bench in
 * view, however few; a themed row with fewer than MIN_ROW benches is hidden.
 *
 * Not built, for lack of data: best-rated (ratings live behind the Worker,
 * per bench) and most-photographed (gallery sizes are only in the per-bench
 * files).
 */
import { streetName } from "./describe"
import { facingKind, looksAt } from "./facing"
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

// Dutch street names that are, by definition, on water: canals (gracht,
// burgwal), quays (kade) and harbours (haven). The rule is shown in the note.
const WATER_STREET = /(gracht|burgwal|kade|haven)$/i
// Parks named in the address. "Science Park" is a business district.
const PARK_STREET = /park$/i
const NOT_A_PARK = /^science park$/i

const list = (names: string[]) =>
  names.length <= 2
    ? names.join(" and ")
    : `${names.slice(0, 2).join(", ")} and ${names.length - 2} more`

/**
 * Rows for the photographed benches in view, nearest the map centre first.
 * `photos` must already be sorted by distance from the centre. The first row
 * is every one of them, so whenever the map shows a photo the rail does too;
 * it returns no rows only when there is no photographed bench in view.
 */
export function buildRows(photos: BenchFeature[]): Row[] {
  if (!photos.length) return []
  const rows: Row[] = []
  const street = (b: BenchFeature) => streetName(b.properties.address)

  rows.push({
    key: "near",
    title:
      photos.length < MIN_ROW
        ? "In view on the map"
        : "Near the middle of the map",
    note: photos.length < MIN_ROW ? "" : "Closest first",
    benches: photos,
  })

  // What the bench looks at, once the data has it (faces_category).
  for (const cat of ["water", "park"] as const) {
    rows.push({
      key: `looks:${cat}`,
      title: looksAt(cat) as string,
      note: "What the bench looks at",
      benches: photos.filter((b) => b.properties.faces_category === cat),
    })
  }

  const water = photos.filter((b) => WATER_STREET.test(street(b) ?? ""))
  rows.push({
    key: "water",
    title: "On a gracht or kade",
    note: "Canal and quay addresses",
    benches: water,
  })

  const parks = photos.filter((b) => {
    const s = street(b) ?? ""
    return PARK_STREET.test(s) && !NOT_A_PARK.test(s)
  })
  const parkNames = [...new Set(parks.map((b) => street(b) as string))]
  rows.push({
    key: "parks",
    title: "In the parks",
    note: list(parkNames),
    benches: parks,
  })

  // The two streets with the most photographed benches in view.
  const byStreet = new Map<string, BenchFeature[]>()
  for (const b of photos) {
    const s = street(b)
    if (!s || PARK_STREET.test(s)) continue
    byStreet.set(s, [...(byStreet.get(s) ?? []), b])
  }
  const top = [...byStreet.entries()]
    .filter(([, v]) => v.length >= 4)
    .sort((a, b) => b[1].length - a[1].length)
    .slice(0, 2)
  for (const [name, benches] of top) {
    rows.push({
      key: `street:${name}`,
      title: `Along ${name}`,
      note: "Same street address",
      benches,
    })
  }

  rows.push({
    key: "mapped",
    title: "Facing mapped",
    note: "Direction tagged in OpenStreetMap",
    benches: photos.filter((b) => facingKind(b.properties) === "mapped"),
  })
  rows.push({
    key: "estimated",
    title: "Facing estimated",
    note: "From street views, may be wrong",
    benches: photos.filter((b) => facingKind(b.properties) === "estimated"),
  })
  rows.push({
    key: "backless",
    title: "No backrest",
    note: "Tagged backrest=no",
    benches: photos.filter((b) => b.properties.backrest === false),
  })

  // Themed rows need MIN_ROW benches, and a row that repeats the first one
  // exactly says nothing new.
  return rows.filter(
    (r) =>
      r.key === "near" ||
      (r.benches.length >= MIN_ROW && r.benches.length < photos.length)
  )
}
