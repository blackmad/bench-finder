/**
 * Canvas-drawn map sprites for the in-GL marker layers: cluster postmark roses
 * and photographed-bench postcard thumbnails. Everything is drawn on demand
 * (MapLibre's `styleimagemissing`), so the map holds one GL symbol per point
 * instead of one DOM node.
 */

const INK = "#141414"
const AIRMAIL = "#1e4fa3"
const VERMILION = "#e23b1e"
const PAPER = "#fbfbf7"
const CARD = "#f6f6f1"
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

/** Unphotographed bench: hub ring with a facing needle drawn pointing north. */
export function dotSprite(kind: MarkerKind): Sprite {
  const S = 44
  const c = S / 2
  const { cv, g } = canvas(S, S)
  const col = kind === "sel" ? VERMILION : kind === "est" ? AIRMAIL : INK
  g.strokeStyle = col
  g.fillStyle = col
  g.lineCap = "round"
  g.lineWidth = kind === "est" ? 1.4 : 2.2
  if (kind === "est") g.setLineDash([2.5, 2.2])
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
  if (kind === "est") {
    g.lineWidth = 1.2
    g.stroke()
  } else {
    g.fill()
  }
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

// Thumbnail geometry (CSS px): a 58x42 photo in a 3px card border on a 9px
// stem, with a 20px needle badge on the bottom-right corner.
const PH_W = 58
const PH_H = 42
const BORDER = 3
const STEM = 9
const CARD_W = PH_W + 2 * BORDER
const CARD_H = PH_H + 2 * BORDER
export const THUMB_W = 84
export const THUMB_H = CARD_H + STEM + 3

export interface ThumbArgs {
  photo: HTMLImageElement | null
  facing: number | null
  known: boolean
  selected: boolean
}

/** Photographed bench: a tiny postcard on a stem. Anchor it at the bottom. */
export function thumbSprite({
  photo,
  facing,
  known,
  selected,
}: ThumbArgs): Sprite {
  const { cv, g } = canvas(THUMB_W, THUMB_H)
  const ink = selected ? VERMILION : INK
  const x0 = (THUMB_W - CARD_W) / 2
  g.save()
  g.shadowColor = "rgba(20, 20, 20, 0.35)"
  g.shadowBlur = 4
  g.shadowOffsetY = 2
  g.fillStyle = CARD
  g.fillRect(x0, 0, CARD_W, CARD_H)
  g.restore()
  if (selected) {
    g.strokeStyle = VERMILION
    g.lineWidth = 2
    g.strokeRect(x0 - 1, -1, CARD_W + 2, CARD_H + 2)
  }
  g.fillStyle = EMPTY
  g.fillRect(x0 + BORDER, BORDER, PH_W, PH_H)
  if (photo) {
    const w = photo.naturalWidth || PH_W
    const h = photo.naturalHeight || PH_H
    // object-fit: cover, cropped low like the rack cards.
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
      BORDER,
      PH_W,
      PH_H
    )
  }
  g.fillStyle = ink
  g.fillRect(THUMB_W / 2 - 0.75, CARD_H, 1.5, STEM + 2)
  if (facing !== null) {
    const bx = x0 + CARD_W
    const by = CARD_H
    g.beginPath()
    g.arc(bx, by, 10, 0, Math.PI * 2)
    g.fillStyle = CARD
    g.fill()
    g.lineWidth = 1.5
    g.strokeStyle = ink
    g.stroke()
    g.save()
    g.translate(bx, by)
    g.rotate((facing * Math.PI) / 180)
    const col = selected ? VERMILION : known ? INK : AIRMAIL
    g.strokeStyle = col
    g.fillStyle = col
    g.lineWidth = known ? 2 : 1.2
    if (!known) g.setLineDash([2, 1.6])
    g.beginPath()
    g.moveTo(0, 5)
    g.lineTo(0, -4)
    g.stroke()
    g.setLineDash([])
    g.beginPath()
    g.moveTo(0, -8)
    g.lineTo(-3.5, -3)
    g.lineTo(3.5, -3)
    g.closePath()
    if (known) {
      g.fill()
    } else {
      g.lineWidth = 1.1
      g.stroke()
    }
    g.restore()
  }
  return finish(cv, g)
}
