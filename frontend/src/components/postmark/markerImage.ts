export type MarkerKind = "known" | "est" | "sel"

export interface MarkerBitmap {
  width: number
  height: number
  data: Uint8Array
}

const INK = "#141414"
const AIRMAIL = "#1e4fa3"
const VERMILION = "#e23b1e"
const PAPER = "#fbfbf7"

/**
 * Map marker art for unphotographed benches: a hub ring with a facing needle,
 * drawn pointing north (MapLibre rotates it by the heading).
 */
export function markerImage(kind: MarkerKind): MarkerBitmap {
  const S = 44
  const c = S / 2
  const dpr = 2
  const cv = document.createElement("canvas")
  cv.width = S * dpr
  cv.height = S * dpr
  const g = cv.getContext("2d")
  if (!g) throw new Error("2d canvas unavailable")
  g.scale(dpr, dpr)
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
  const px = g.getImageData(0, 0, S * dpr, S * dpr)
  return {
    width: S * dpr,
    height: S * dpr,
    data: new Uint8Array(px.data.buffer),
  }
}
