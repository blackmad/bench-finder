import { describe, expect, it } from "vitest"
import {
  activeCount,
  coverage,
  type Filters,
  filtersFromParams,
  filtersToParams,
  materialGroups,
  NO_FILTERS,
  offered,
  optionCounts,
  passes,
  seatBucket,
  summary,
} from "./filters"
import type { BenchFeature, BenchProps } from "./types"

const bench = (id: number, p: Partial<BenchProps> = {}): BenchFeature => ({
  type: "Feature",
  geometry: { type: "Point", coordinates: [4.9, 52.37] },
  properties: {
    id,
    lat: 52.37,
    lng: 4.9,
    facing: null,
    facing_confidence: null,
    facing_method: null,
    axis_only: false,
    bench_type: null,
    backrest: null,
    faces_category: null,
    hero_key: null,
    hero_urls: null,
    address: null,
    ...p,
  },
})

const photo = { hero_urls: { "400": "img/a-400.avif" } }
const mapped = (deg: number) =>
  ({ facing: deg, facing_method: "osm_tag" }) as const
const est = (deg: number) => ({ facing: deg, facing_method: "vlm" }) as const

const with_ = (f: Partial<Filters>): Filters => ({ ...NO_FILTERS, ...f })

describe("materialGroups / seatBucket", () => {
  it("folds OSM values into groups", () => {
    expect(materialGroups("wood")).toEqual(["wood"])
    expect(materialGroups("Wood;stainless_steel")).toEqual(["wood", "metal"])
    expect(materialGroups("granite")).toEqual(["stone"])
    expect(materialGroups("rope")).toEqual(["other"])
    expect(materialGroups(null)).toEqual([])
  })
  it("buckets seats", () => {
    expect([1, 2, 3, 4, 5, 12].map(seatBucket)).toEqual([
      "1-2",
      "1-2",
      "3",
      "4",
      "5+",
      "5+",
    ])
    expect(seatBucket(null)).toBeNull()
    expect(seatBucket(0)).toBeNull()
  })
})

describe("passes", () => {
  it("lets everything through with no filters", () => {
    expect(passes(bench(1).properties, NO_FILTERS)).toBe(true)
  })
  it("filters by photo, facing kind and direction", () => {
    const a = bench(1, { ...photo, ...mapped(50) }).properties // NE
    const b = bench(2, est(180)).properties // S
    const c = bench(3).properties
    expect(passes(a, with_({ photo: true }))).toBe(true)
    expect(passes(b, with_({ photo: true }))).toBe(false)
    expect(passes(c, with_({ facing: "known" }))).toBe(false)
    expect(passes(b, with_({ facing: "known" }))).toBe(true)
    expect(passes(b, with_({ facing: "mapped" }))).toBe(false)
    expect(passes(b, with_({ facing: "estimated" }))).toBe(true)
    expect(passes(a, with_({ dirs: new Set([1]) }))).toBe(true)
    expect(passes(a, with_({ dirs: new Set([4]) }))).toBe(false)
    expect(passes(c, with_({ dirs: new Set([0]) }))).toBe(false)
    // 350 degrees rounds into the north sector.
    expect(
      passes(bench(4, mapped(350)).properties, with_({ dirs: new Set([0]) }))
    ).toBe(true)
  })
  it("treats unknown values as not matching yes/no filters", () => {
    const yes = bench(1, { backrest: true, lit: true }).properties
    const unknown = bench(2).properties
    expect(passes(yes, with_({ backrest: "yes", lit: "yes" }))).toBe(true)
    expect(passes(yes, with_({ backrest: "no" }))).toBe(false)
    expect(passes(unknown, with_({ backrest: "no" }))).toBe(false)
    expect(passes(unknown, with_({ lit: "yes" }))).toBe(false)
  })
  it("ORs within a group and ANDs across groups", () => {
    const wood4 = bench(1, { material: "wood", seats: 4, backrest: true })
    const metal2 = bench(2, { material: "steel", seats: 2, backrest: true })
    const f = with_({ materials: new Set(["wood", "metal"]) })
    expect(passes(wood4.properties, f)).toBe(true)
    expect(passes(metal2.properties, f)).toBe(true)
    const g = with_({ ...f, seats: new Set(["4"]) })
    expect(passes(wood4.properties, g)).toBe(true)
    expect(passes(metal2.properties, g)).toBe(false)
    expect(activeCount(g)).toBe(2)
  })
  it("skips one group for option counts", () => {
    const p = bench(1, { backrest: false }).properties
    expect(passes(p, with_({ backrest: "yes" }), "backrest")).toBe(true)
  })
})

describe("coverage and offered", () => {
  const data = [
    bench(1, { ...photo, ...mapped(10), backrest: true, material: "wood" }),
    bench(2, { ...mapped(100), backrest: false }),
    bench(3, { ...mapped(200), backrest: true, lit: true }),
    bench(4, { backrest: true, material: "metal", seats: 3 }),
  ]
  it("offers only controls with enough data", () => {
    const c = coverage(data)
    expect(c).toMatchObject({ total: 4, photo: 1, facing: 3, mapped: 3 })
    const o = offered(c)
    expect(o.facing).toBe(true)
    expect(o.facingSplit).toBe(false)
    expect(o.backrest).toBe(true)
    expect(o.photo).toBe(false)
    expect(o.materials).toBe(false)
    expect(o.lit).toBe(false)
    expect(o.faces).toBe(false)
    expect(o.types).toBe(false)
  })
  it("counts each option against the other groups", () => {
    const n = optionCounts(data, with_({ backrest: "yes", dirs: new Set([0]) }))
    // backrest counts ignore the backrest filter but respect the direction.
    expect(n.backrest).toEqual({ yes: 1, no: 0 })
    // direction counts ignore the direction filter but respect backrest.
    expect(n.dirs).toEqual([1, 0, 0, 0, 1, 0, 0, 0])
    expect(n.materials.wood).toBe(1)
    expect(n.materials.metal).toBe(0)
  })
})

describe("URL round trip", () => {
  it("writes short keys and reads them back", () => {
    const f = with_({
      photo: true,
      backrest: "no",
      materials: new Set(["metal", "wood"]),
      seats: new Set(["5+"]),
      faces: new Set(["water"]),
    })
    const sp = new URLSearchParams("lat=52.1&z=12&dir=s")
    filtersToParams(f, sp)
    expect(sp.toString()).toBe(
      "lat=52.1&z=12&photo=1&back=no&mat=wood%2Cmetal&seats=5%2B&faces=water"
    )
    expect(filtersFromParams(sp)).toEqual(f)
    expect(summary(f)).toBe(
      "with a photo · no backrest · wood or metal · seats 5+ · looks at water"
    )
  })
  it("drops unknown values and clears keys", () => {
    const f = filtersFromParams(
      new URLSearchParams("back=maybe&mat=wood,gold&type=picnic")
    )
    expect(f.backrest).toBeNull()
    expect([...f.materials]).toEqual(["wood"])
    expect([...f.types]).toEqual(["picnic"])
    const sp = new URLSearchParams("dir=n&lat=1")
    filtersToParams(NO_FILTERS, sp)
    expect(sp.toString()).toBe("lat=1")
  })
  it("ignores the removed facing filters in old links, and drops them", () => {
    // The compass and "how the facing is known" filters left the panel: an old
    // shared link must not apply a filter nobody can see or clear.
    const sp = new URLSearchParams("dir=n,sw&facing=known&mat=wood&lat=1")
    const f = filtersFromParams(sp)
    expect(f.dirs.size).toBe(0)
    expect(f.facing).toBeNull()
    expect([...f.materials]).toEqual(["wood"])
    expect(activeCount(f)).toBe(1)
    filtersToParams(f, sp)
    expect(sp.toString()).toBe("lat=1&mat=wood")
  })
})
