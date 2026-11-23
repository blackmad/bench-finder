import { describe, expect, it } from "vitest"
import { zoomToFov } from "./googleMaps"

describe("zoomToFov", () => {
  it("halves the field of view per zoom level, within what we render", () => {
    expect(zoomToFov(1)).toBe(90)
    expect(zoomToFov(2)).toBe(45)
    expect(zoomToFov(0)).toBe(120) // 180 clamps to our widest render
    expect(zoomToFov(5)).toBe(10)
  })
})
