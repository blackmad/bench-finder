import { describe, expect, it } from "vitest"
import { lede } from "./describe"
import type { BenchDetail } from "./types"

const bench = (extra: Partial<BenchDetail>): BenchDetail =>
  ({
    id: 1,
    tags: { material: "wood", backrest: "yes", seats: "3" },
    backrest: true,
    gallery: [],
    hero_urls: null,
    ...extra,
  }) as unknown as BenchDetail

describe("lede", () => {
  it("says where the facts come from when there is no photo", () => {
    expect(lede(bench({}))).toBe(
      "A wooden bench with a backrest, seats three. As mapped on OpenStreetMap."
    )
  })

  it("credits the city for its own records", () => {
    expect(lede(bench({ tags: { source: "BGT Amsterdam" } }))).toMatch(
      /As recorded by the City of Amsterdam\.$/
    )
  })
})
