import { describe, expect, it } from "vitest"
import { facingSentence } from "./describe"
import { buildRows, MIN_ROW } from "./rows"
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
    hero_key: "k",
    hero_urls: { "400": "img/k-400.avif" },
    address: `Prinsengracht ${id}`,
    ...p,
  },
})

describe("buildRows", () => {
  it("shows every photographed bench in view, however few", () => {
    const rows = buildRows([bench(1), bench(2)])
    expect(rows).toHaveLength(1)
    expect(rows[0].title).toBe("In view on the map")
    expect(rows[0].benches.map((b) => b.properties.id)).toEqual([1, 2])
  })

  it("returns no rows only when there is no photographed bench", () => {
    expect(buildRows([])).toEqual([])
  })

  it("hides short themed rows and ones that repeat the first", () => {
    const photos = [
      ...Array.from({ length: MIN_ROW + 1 }, (_, i) =>
        bench(i + 1, { faces_category: "water" })
      ),
      bench(9, { address: "Dam 1", faces_category: "water" }),
      bench(10, { address: "Dam 2" }),
    ]
    const keys = buildRows(photos).map((r) => r.key)
    expect(keys[0]).toBe("near")
    expect(keys).toContain("looks:water")
    expect(keys).toContain("water") // the gracht addresses: 4 of 6
    expect(keys).not.toContain("looks:park")
  })
})

describe("facingSentence", () => {
  const base = {
    facing: 180,
    facing_method: "osm_tag" as const,
    facing_confidence: 1,
  }
  it("leads with what the bench looks at", () => {
    expect(facingSentence({ ...base, faces_category: "water" })).toBe(
      "Looks out over the water, facing south."
    )
    expect(
      facingSentence({ ...base, facing: null, faces_category: "park" })
    ).toBe("Looks out over the park.")
  })
  it("falls back to the compass", () => {
    expect(facingSentence(base)).toBe(
      "Faces south, as mapped in OpenStreetMap."
    )
  })
})
