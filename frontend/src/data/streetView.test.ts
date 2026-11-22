import { describe, expect, it } from "vitest"
import { streetViewTarget, streetViewUrls } from "./streetView"

const G = "bQ0tE2V_7xLWaMmD3LYDTA"
const base = {
  embed_pano_id: null,
  embed_heading_deg: 90,
  embed_lat: null,
  embed_lng: null,
}

describe("streetViewTarget", () => {
  it("keeps a Google panorama id", () => {
    expect(streetViewTarget({ ...base, embed_pano_id: G })).toEqual({
      pano: G,
      at: null,
      heading: 90,
    })
  })
  it("never sends an Apple, city or other id to Google (regression: 'Invalid pano parameter')", () => {
    for (const id of [
      "9524987388017545573",
      "TMX7316010203-001085_pano_0006_000012",
      "recording_2025-07-02_11-44-00_01950",
    ]) {
      expect(streetViewTarget({ ...base, embed_pano_id: id })).toBeNull()
      expect(
        streetViewTarget({
          ...base,
          embed_pano_id: id,
          embed_lat: 52.37,
          embed_lng: 4.89,
        })
      ).toEqual({ pano: null, at: [52.37, 4.89], heading: 90 })
    }
  })
  it("nothing to open without an id or a position", () => {
    expect(streetViewTarget(base)).toBeNull()
  })
})

describe("streetViewUrls", () => {
  it("embeds by pano id", () => {
    const u = streetViewUrls({ pano: G, at: [1, 2], heading: 89.6 }, "KEY")
    expect(u.embed).toBe(
      `https://www.google.com/maps/embed/v1/streetview?key=KEY&pano=${G}&heading=90&pitch=0&fov=80`
    )
    expect(u.out).toContain(`map_action=pano&pano=${G}&heading=90`)
  })
  it("embeds by location when there is no Google id", () => {
    const u = streetViewUrls(
      { pano: null, at: [52.37, 4.89], heading: 200 },
      "KEY"
    )
    expect(u.embed).toBe(
      "https://www.google.com/maps/embed/v1/streetview?key=KEY&location=52.37,4.89&heading=200&pitch=0&fov=80"
    )
    expect(u.out).toContain("viewpoint=52.37,4.89&heading=200")
    expect(u.embed).not.toContain("pano=")
  })
  it("no key: no embed, only the link out", () => {
    expect(
      streetViewUrls({ pano: G, at: null, heading: 0 }, undefined).embed
    ).toBeNull()
  })
})
