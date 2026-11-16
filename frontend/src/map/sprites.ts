/**
 * Canvas-drawn map sprites for the in-GL marker layers: cluster postmark roses
 * and photographed-bench postcard thumbnails. Everything is drawn on demand
 * (MapLibre's `styleimagemissing`), so the map holds one GL symbol per point
 * instead of one DOM node.
 */

const INK = "#141414"
const AIRMAIL = "#1e4fa3"
const VERMILION = "#e23b1e"
const PAPER = "#fffdf8"
const CARD = "#fbf8f1"
const EMPTY = "#c9c9bf"
const DPR = 2
const FONT = '"Archivo Variable", ui-sans-serif, system-ui, sans-serif'

export interface Sprite {
  data: ImageData
  pixelRatio: number
}

function canvas(w: number, h: number) {
  const cv = document.createElement("canvas")
  cv.width = Math.ceil(w * DPR)
  cv.height = Math.ceil(h * DPR)
  const g = cv.getContext("2d", { willReadFrequently: true })
  if (!g) throw new Error("2d canvas unavailable")
  g.scale(DPR, DPR)
  return { cv, g }
}

const finish = (
  cv: HTMLCanvasElement,
  g: CanvasRenderingContext2D
): Sprite => ({
  data: g.getImageData(0, 0, cv.width, cv.height),
  pixelRatio: DPR,
})

/** Radius tiers by cluster size, as in the design reference. */
export const ROSE_RADIUS = [13, 16, 19] as const

/**
 * Cluster rose: a stamp-paper ring with the count and up to eight ticks, one
 * per facing sector. `levels[i]` is 0..10, the sector's share in tenths.
 */
export function roseSprite(
  tier: number,
  label: string,
  levels: readonly number[]
): Sprite {
  const R = ROSE_RADIUS[tier] ?? 13
  const S = R + 18
  const { cv, g } = canvas(2 * S, 2 * S)
  g.translate(S, S)
  g.lineCap = "round"
  g.strokeStyle = INK
  g.lineWidth = 2
  for (let i = 0; i < 8; i++) {
    const lvl = levels[i] ?? 0
    if (!lvl) continue
    const a = (i * 45 * Math.PI) / 180
    const l = 3 + (lvl / 10) * 14
    g.beginPath()
    g.moveTo(Math.sin(a) * R, -Math.cos(a) * R)
    g.lineTo(Math.sin(a) * (R + l), -Math.cos(a) * (R + l))
    g.stroke()
  }
  g.save()
  g.shadowColor = "rgba(20, 20, 20, 0.2)"
  g.shadowBlur = 2
  g.shadowOffsetY = 1
  g.beginPath()
  g.arc(0, 0, R, 0, Math.PI * 2)
  g.fillStyle = PAPER
  g.fill()
  g.restore()
  g.lineWidth = 1.5
  g.beginPath()
  g.arc(0, 0, R, 0, Math.PI * 2)
  g.stroke()
  g.lineWidth = 0.7
  g.beginPath()
  g.arc(0, 0, R - 3.2, 0, Math.PI * 2)
  g.stroke()
  g.fillStyle = INK
  g.textAlign = "center"
  g.textBaseline = "middle"
  g.font = `700 ${R >= 16 ? 11 : 10}px ${FONT}`
  g.fontStretch = "semi-expanded"
  g.fillText(label, 0, 0.5)
  return finish(cv, g)
}

export type MarkerKind = "known" | "est" | "sel"

function drawNeedle(g: CanvasRenderingContext2D, c: number, est: boolean) {
  g.lineWidth = est ? 1.4 : 2.2
  if (est) g.setLineDash([2.5, 2.2])
  g.beginPath()
  g.moveTo(c, c - 6)
  g.lineTo(c, c - 17)
  g.stroke()
  g.setLineDash([])
  g.beginPath()
  g.moveTo(c, c - 21)
  g.lineTo(c - 3.6, c - 14.5)
  g.lineTo(c + 3.6, c - 14.5)
  g.closePath()
  if (est) {
    g.lineWidth = 1.2
    g.stroke()
  } else {
    g.fill()
  }
}

/**
 * Unphotographed bench: hub ring with a facing needle drawn pointing north
 * (the layer rotates it). Without `needle` it is the hub alone, for benches
 * whose facing is not known: nothing pretends to point anywhere.
 */
/**
 * A bench seen from above, facing up (the map rotates it to its facing): a
 * seat slab with the backrest as a thick bar behind it. Backless benches
 * (axis only) are the slab alone, so no front is invented. Estimated facings
 * are an airmail outline; mapped ones solid ink; the selected bench vermilion.
 * No facing at all: an unrotated slab with a hollow middle.
 */
export function benchSprite(kind: MarkerKind | "none", back: boolean): Sprite {
  const S = 44
  const c = S / 2
  const { cv, g } = canvas(S, S)
  const col = kind === "sel" ? VERMILION : kind === "est" ? AIRMAIL : INK
  const W = kind === "sel" ? 34 : 28
  const seatH = kind === "sel" ? 10 : 8
  const top = back ? c - seatH / 2 - 2 : c - seatH / 2
  // A paper halo keeps the mark legible on any map colour.
  g.fillStyle = PAPER
  g.globalAlpha = 0.9
  g.fillRect(c - W / 2 - 3, top - 3, W + 6, seatH + (back ? 11 : 6))
  g.globalAlpha = 1
  g.lineWidth = 2
  g.strokeStyle = col
  g.fillStyle = col
  if (kind === "est" || kind === "none") {
    g.strokeRect(c - W / 2 + 1, top + 1, W - 2, seatH - 2)
  } else {
    g.fillRect(c - W / 2, top, W, seatH)
  }
  if (back) {
    g.fillRect(c - W / 2, top + seatH + 2, W, 4)
  }
  return finish(cv, g)
}

export function dotSprite(kind: MarkerKind, needle = true): Sprite {
  const S = 44
  const c = S / 2
  const { cv, g } = canvas(S, S)
  const col = kind === "sel" ? VERMILION : kind === "est" ? AIRMAIL : INK
  g.strokeStyle = col
  g.fillStyle = col
  g.lineCap = "round"
  if (needle) drawNeedle(g, c, kind === "est")
  g.beginPath()
  g.arc(c, c, kind === "sel" ? 6.5 : 5, 0, Math.PI * 2)
  g.fillStyle = kind === "sel" ? VERMILION : PAPER
  g.fill()
  if (kind !== "sel") {
    g.lineWidth = kind === "est" ? 1.4 : 2
    g.strokeStyle = col
    g.stroke()
  }
  return finish(cv, g)
}

// Thumbnail geometry (CSS px): a 58x42 photo in a 3px card border, a closed
// frame all round, on a small pointer whose tip is the bench. The canvas keeps
// a margin round the card so the selected frame, the shadow and the count
// badge are never clipped.
const PH_W = 58
const PH_H = 42
const BORDER = 3
const POINTER = 7
const CARD_W = PH_W + 2 * BORDER
const CARD_H = PH_H + 2 * BORDER
const SIDE = 14
const TOP = 14
export const THUMB_W = CARD_W + 2 * SIDE
export const THUMB_H = TOP + CARD_H + POINTER

export interface ThumbArgs {
  photo: HTMLImageElement | null
  selected: boolean
  /** Benches this marker stands for; above 1 it shows a count badge. */
  count?: number
}

/** Photographed bench: a tiny postcard on a pointer. Anchor it at the bottom. */
export function thumbSprite({ photo, selected, count = 1 }: ThumbArgs): Sprite {
  const { cv, g } = canvas(THUMB_W, THUMB_H)
  const ink = selected ? VERMILION : INK
  const x0 = SIDE
  const y0 = TOP
  const cx = THUMB_W / 2
  const card = () => {
    g.beginPath()
    g.rect(x0, y0, CARD_W, CARD_H)
    g.moveTo(cx - 5, y0 + CARD_H)
    g.lineTo(cx, y0 + CARD_H + POINTER)
    g.lineTo(cx + 5, y0 + CARD_H)
    g.closePath()
  }
  // A second card peeks out behind a marker that stands for several benches.
  if (count > 1) {
    g.save()
    g.shadowColor = "rgba(20, 20, 20, 0.25)"
    g.shadowBlur = 3
    g.shadowOffsetY = 1
    g.fillStyle = CARD
    g.fillRect(x0 + 4, y0 - 4, CARD_W, CARD_H)
    g.restore()
    g.lineWidth = 1
    g.strokeStyle = INK
    g.strokeRect(x0 + 4.5, y0 - 3.5, CARD_W - 1, CARD_H - 1)
  }
  g.save()
  g.shadowColor = "rgba(20, 20, 20, 0.35)"
  g.shadowBlur = 4
  g.shadowOffsetY = 2
  g.fillStyle = CARD
  card()
  g.fill()
  g.restore()
  g.fillStyle = EMPTY
  g.fillRect(x0 + BORDER, y0 + BORDER, PH_W, PH_H)
  if (photo) {
    const w = photo.naturalWidth || PH_W
    const h = photo.naturalHeight || PH_H
    // object-fit: cover, cropped low like the rail tiles.
    const s = Math.max(PH_W / w, PH_H / h)
    const sw = PH_W / s
    const sh = PH_H / s
    g.drawImage(
      photo,
      (w - sw) / 2,
      (h - sh) * 0.62,
      sw,
      sh,
      x0 + BORDER,
      y0 + BORDER,
      PH_W,
      PH_H
    )
  }
  // The frame: one closed outline round card and pointer.
  g.lineJoin = "miter"
  g.lineWidth = selected ? 2 : 1
  g.strokeStyle = ink
  card()
  g.stroke()
  if (count > 1) {
    const label = String(count)
    g.font = `700 10.5px ${FONT}`
    g.fontStretch = "semi-expanded"
    const w = Math.max(18, g.measureText(label).width + 10)
    const bx = x0 + CARD_W + 4 - w / 2
    const by = y0 - 4
    g.beginPath()
    g.roundRect(bx - w / 2, by - 9, w, 18, 9)
    g.fillStyle = ink
    g.fill()
    g.lineWidth = 1.5
    g.strokeStyle = PAPER
    g.stroke()
    g.fillStyle = PAPER
    g.textAlign = "center"
    g.textBaseline = "middle"
    g.fillText(label, bx, by + 0.5)
  }
  return finish(cv, g)
}
