import { type MarkerKind, type Sprite, slatsSprite } from "./sprites"

/** The rotating sprite for a bench without a photo: a wooden bench seen from above. */
export function markerSprite(kind: MarkerKind | "none", back: boolean): Sprite {
  return slatsSprite(kind, back)
}
