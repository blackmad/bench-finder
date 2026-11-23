/** Where an `object-fit: cover` image lands in its box: left, top, width, height in px. */
export function coverBox(
  boxW: number,
  boxH: number,
  imgW: number,
  imgH: number,
  posX = 0.5,
  posY = 0.5
): [number, number, number, number] {
  const s = Math.max(boxW / imgW, boxH / imgH)
  const w = imgW * s
  const h = imgH * s
  return [(boxW - w) * posX + 0, (boxH - h) * posY + 0, w, h] // + 0: no -0
}
