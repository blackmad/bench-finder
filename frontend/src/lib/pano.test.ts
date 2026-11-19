import { describe, expect, it } from "vitest"
import { fractionOf, headingAt, offset, parseStreetViewLink } from "./pano"

describe("parseStreetViewLink", () => {
  it("reads position, heading and panorama id from a Street View link", () => {
    const link =
      "https://www.google.com/maps/place/Mezebar+Bodrum/@52.3644963,4.8578325,3a,75y,256.02h,86.01t/data=!3m7!1e1!3m5!1sAbCdEfGhIjKlMnOp_q-12!2e0!6shttps:%2F%2Fstreetviewpixels!7i16384!8i8192"
    expect(parseStreetViewLink(link)).toMatchObject({
      source: "google",
      id: "AbCdEfGhIjKlMnOp_q-12",
      heading: 256,
      lat: 52.3644963,
      lng: 4.8578325,
    })
  })

  it("rejects links that are not Street View", () => {
    expect(
      parseStreetViewLink("https://www.google.com/maps/@52.36,4.85,15z")
    ).toBeNull()
    expect(
      parseStreetViewLink(
        "https://example.com/@52.36,4.85,3a,75y,10h/data=!1sAbCdEfGhIjKl!2e0"
      )
    ).toBeNull()
    expect(parseStreetViewLink("not a url")).toBeNull()
  })
})

describe("equirectangular headings", () => {
  it("centre column is north, a quarter in is west", () => {
    expect(headingAt(0.5)).toBe(0)
    expect(headingAt(0.25)).toBe(270)
    expect(headingAt(0.75)).toBe(90)
    for (const h of [0, 45, 180, 359])
      expect(headingAt(fractionOf(h))).toBeCloseTo(h)
  })

  it("bearing from one point to another", () => {
    const a = { lat: 52.36, lng: 4.85 }
    expect(offset(a, { lat: 52.361, lng: 4.85 }).bearing).toBeCloseTo(0)
    expect(offset(a, { lat: 52.36, lng: 4.851 }).bearing).toBeCloseTo(90)
  })
})
