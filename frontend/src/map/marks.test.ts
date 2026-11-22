import { describe, expect, it } from "vitest"
import { marksFrom } from "./marks"

describe("marksFrom", () => {
  it("badges favourites, want-to-sit and both", () => {
    const m = marksFrom({ favorites: [1, 2], want: [2, 3] })
    expect(Object.fromEntries(m)).toEqual({ 1: "fav", 2: "both", 3: "want" })
  })
  it("signed out or an older API without `want`", () => {
    expect(marksFrom(null).size).toBe(0)
    expect(Object.fromEntries(marksFrom({ favorites: [4] }))).toEqual({
      4: "fav",
    })
  })
})
