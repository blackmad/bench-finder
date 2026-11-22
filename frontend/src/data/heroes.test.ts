import { describe, expect, it } from "vitest"
import { applyPick, pickBody } from "./heroes"

const props = {
  id: 2160,
  hero_key: "12276b213fb43d16",
  hero_urls: { "800": "img/12276b213fb43d16-800.avif" },
  hero_width: 1600,
  hero_height: 1600,
  hero_focus: [0.4, 0.6] as [number, number],
}
const pick = {
  imageId: 54438,
  key: "a78e32b62970c9c5",
  urls: { "800": "img/a78e32b62970c9c5-800.avif" },
  urls_webp: { "800": "img/a78e32b62970c9c5-800.webp" },
  width: 800,
  height: 800,
}

describe("lead photo picks", () => {
  it("a pick replaces the lead photo and drops the old crop focus", () => {
    const out = applyPick(props, pick)
    expect(out).toMatchObject({
      id: 2160,
      hero_key: pick.key,
      hero_urls: pick.urls,
      hero_urls_webp: pick.urls_webp,
      hero_width: 800,
      hero_focus: null,
    })
  })
  it("no pick, or a pick the publish already has, leaves the bench as is", () => {
    expect(applyPick(props, undefined)).toBe(props)
    expect(applyPick(props, { ...pick, key: props.hero_key })).toBe(props)
  })
  it("sends only the published renditions and the image id", () => {
    const g = {
      id: 7,
      urls: pick.urls,
      width: 800,
      height: 800,
      heading: 229,
      kind: "aimed",
    }
    expect(pickBody(g)).toEqual({
      imageId: 7,
      photo: { urls: pick.urls, width: 800, height: 800 },
    })
  })
})
