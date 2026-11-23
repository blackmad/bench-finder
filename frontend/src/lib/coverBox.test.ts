import { describe, expect, it } from "vitest"
import { coverBox } from "./coverBox"

describe("coverBox", () => {
  it("a square photo in a 16:10 box overflows top and bottom by its position", () => {
    expect(coverBox(160, 100, 800, 800, 0.5, 0.5)).toEqual([0, -30, 160, 160])
    expect(coverBox(160, 100, 800, 800, 0.5, 0)).toEqual([0, 0, 160, 160])
    expect(coverBox(160, 100, 800, 800, 0.5, 1)).toEqual([0, -60, 160, 160])
  })
  it("a wide photo in a square box overflows left and right", () => {
    expect(coverBox(100, 100, 400, 200, 0.5, 0.5)).toEqual([-50, 0, 200, 100])
  })
})
