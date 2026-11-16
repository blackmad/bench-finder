import { describe, expect, it } from "vitest"
import { benchCount, placeIndex } from "./hooks"
import type { BenchFeature } from "./types"

const place = (id: number, bench_ids?: number[]) =>
  ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [4.9, 52.37] },
    properties: { id, bench_ids, count: bench_ids?.length },
  }) as unknown as BenchFeature

describe("placeIndex", () => {
  it("finds a place from any of its benches", () => {
    const rokin = place(5596, [5596, 5597, 5598])
    const alone = place(7)
    const index = placeIndex([rokin, alone])
    expect(index.get(5597)).toBe(rokin)
    expect(index.get(5596)).toBe(rokin)
    expect(index.get(7)).toBe(alone) // old data without bench_ids
    expect(benchCount(rokin.properties)).toBe(3)
    expect(benchCount(alone.properties)).toBe(1)
  })
})
