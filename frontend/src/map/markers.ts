import {
  benchSprite,
  coneSprite,
  discSprite,
  dotSprite,
  type MarkerKind,
  type Sprite,
  slatsSprite,
} from "./sprites"

/**
 * Trial marker styles for benches without a photo marker. Pick one with
 * `?markers` in the URL (a picker appears on the map); the choice is kept in
 * this browser. Once one is chosen, the others go.
 */
export const MARKER_STYLES = [
  ["slats", "Wooden bench (top-down)"],
  ["cone", "View cone"],
  ["headon", "Bench icon + pointer"],
  ["arrow", "Dot and arrow (old)"],
  ["plan", "Plan bars"],
] as const
export type MarkerStyle = (typeof MARKER_STYLES)[number][0]
const KEY = "bf-marker-style"
export const DEFAULT_STYLE: MarkerStyle = "slats"

export function markerStyle(): MarkerStyle {
  const fromUrl = new URLSearchParams(window.location.search).get("markers")
  const ok = (v: string | null): v is MarkerStyle =>
    MARKER_STYLES.some(([k]) => k === v)
  if (ok(fromUrl)) return fromUrl
  try {
    const saved = localStorage.getItem(KEY)
    if (ok(saved)) return saved
  } catch {
    /* storage blocked */
  }
  return DEFAULT_STYLE
}

export function saveMarkerStyle(s: MarkerStyle) {
  try {
    localStorage.setItem(KEY, s)
  } catch {
    /* storage blocked */
  }
}

export const pickerWanted = () =>
  new URLSearchParams(window.location.search).has("markers")

/** The rotating sprite for a bench of this kind in this style. */
export function markerSprite(
  style: MarkerStyle,
  kind: MarkerKind | "none",
  back: boolean
): Sprite {
  switch (style) {
    case "slats":
      return slatsSprite(kind, back)
    case "cone":
      return coneSprite(kind, back)
    case "headon":
      return discSprite(kind, back)
    case "arrow":
      return kind === "none" ? dotSprite("known", false) : dotSprite(kind, true)
    case "plan":
      return benchSprite(kind, back)
  }
}
