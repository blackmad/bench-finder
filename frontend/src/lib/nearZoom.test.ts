import { describe, expect, it } from "vitest"
import { nearRadius, reachMetres, zoomForRadius } from "./nearZoom"

const here: [number, number] = [4.893, 52.372]
const east = (m: number): [number, number] => [
  4.893 + m / (111_320 * Math.cos((52.372 * Math.PI) / 180)),
  52.372,
]

describe("near me reach", () => {
  it("uses the eighth nearest point", () => {
    const pts = [10, 20, 30, 40, 50, 60, 70, 80, 900].map(east)
    expect(Math.round(reachMetres(here, pts))).toBe(80)
  })
  it("stops at a five-minute walk unless nothing is that close", () => {
    expect(Math.round(nearRadius(here, [10, 20, 900, 1000].map(east)))).toBe(
      400
    )
    expect(Math.round(nearRadius(here, [30, 40].map(east)))).toBe(40)
    expect(Math.round(nearRadius(here, [700, 900].map(east)))).toBe(700)
  })
  it("zooms out further where benches are sparse", () => {
    const dense = zoomForRadius(80, 52.372, 390)
    const sparse = zoomForRadius(800, 52.372, 390)
    expect(dense).toBeGreaterThan(sparse)
    expect(dense).toBeLessThanOrEqual(17)
    expect(sparse).toBeGreaterThanOrEqual(12)
  })
})
