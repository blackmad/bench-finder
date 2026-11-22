import { describe, expect, it } from "vitest"
import { moved, pagePath } from "./social"

describe("favourites order", () => {
  it("moves one place up or down", () => {
    expect(moved([1, 2, 3], 2, -1)).toEqual([1, 3, 2])
    expect(moved([1, 2, 3], 0, 1)).toEqual([2, 1, 3])
  })
  it("is a no-op at the ends", () => {
    const ids = [1, 2, 3]
    expect(moved(ids, 0, -1)).toBe(ids)
    expect(moved(ids, 2, 1)).toBe(ids)
  })
})

describe("pagePath", () => {
  it("uses the handle once chosen, else the share slug", () => {
    expect(pagePath({ slug: "k3j9xqab", handle: null })).toBe("/u/k3j9xqab")
    expect(pagePath({ slug: "k3j9xqab", handle: "pia" })).toBe("/u/pia")
  })
})
