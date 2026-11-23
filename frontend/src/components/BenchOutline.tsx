import { type RefObject, useEffect, useState } from "react"
import { coverBox } from "../lib/coverBox"

/**
 * The bench's outline over a cover-cropped photo. `outline` is in 0..1 of the
 * photo; `focus` is the photo's object-position (the stylesheet's default when
 * absent). Shown by CSS on hover or focus of the photo box.
 */
export function BenchOutline({
  box,
  outline,
  width,
  height,
  focus,
}: {
  box: RefObject<HTMLElement | null>
  outline: [number, number][]
  width: number
  height: number
  focus?: [number, number] | null
}) {
  const [size, setSize] = useState<[number, number] | null>(null)
  useEffect(() => {
    const el = box.current
    if (!el || typeof ResizeObserver === "undefined") return
    const ro = new ResizeObserver(([e]) =>
      setSize([e.contentRect.width, e.contentRect.height])
    )
    ro.observe(el)
    return () => ro.disconnect()
  }, [box])
  if (!size) return null
  const [left, top, w, h] = coverBox(
    size[0],
    size[1],
    width,
    height,
    focus?.[0] ?? 0.5,
    focus?.[1] ?? 0.58
  )
  return (
    <svg
      className="outline"
      aria-hidden="true"
      viewBox="0 0 1 1"
      preserveAspectRatio="none"
      style={{ left, top, width: w, height: h }}
    >
      <polygon
        points={outline.map(([x, y]) => `${x},${y}`).join(" ")}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}
