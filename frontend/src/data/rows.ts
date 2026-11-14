/**
 * The rail's rows and the bench of the day, built from fields the published
 * GeoJSON actually carries: address, backrest, facing and facing_method, and
 * whether there is a photo. A row with fewer than MIN_ROW benches is hidden.
 *
 * Not built, for lack of data: "faces the water / park" (faces_category is
 * empty), best-rated (ratings live behind the Worker, per bench), and
 * most-photographed (gallery sizes are only in the per-bench files).
 */
import { hasPhoto } from "./api"
import { isStreetAddress, streetName } from "./describe"
import { facingKind } from "./facing"
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
 * `photos` must already be sorted by distance from the centre.
 */
export function buildRows(photos: BenchFeature[]): Row[] {
  const rows: Row[] = []
  const street = (b: BenchFeature) => streetName(b.properties.address)

  rows.push({
    key: "near",
    title: "Near the middle of the map",
    note: "Closest first",
    benches: photos,
  })

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

  return rows.filter((r) => r.benches.length >= MIN_ROW)
}

const DAY = 86_400_000

/**
 * One photographed bench per day, the same for everyone. Benches with a mapped
 * facing and a street address come first, so the hero can show its compass.
 */
export function benchOfTheDay(
  benches: BenchFeature[],
  now = Date.now()
): BenchFeature | null {
  const named = benches
    .filter((b) => hasPhoto(b) && isStreetAddress(b.properties.address))
    .sort((a, b) => a.properties.id - b.properties.id)
  const faced = named.filter((b) => facingKind(b.properties) !== null)
  const pool = faced.length ? faced : named
  if (!pool.length) return null
  return pool[Math.floor(now / DAY) % pool.length]
}
