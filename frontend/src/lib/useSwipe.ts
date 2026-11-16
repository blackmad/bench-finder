import { type TouchEvent, useRef } from "react"

/** Horizontal swipe handlers: left = next (1), right = previous (-1). */
export function useSwipe(onStep?: (dir: 1 | -1) => void) {
  const start = useRef<{ x: number; y: number } | null>(null)
  if (!onStep) return {}
  return {
    onTouchStart: (e: TouchEvent) => {
      const t = e.touches[0]
      start.current = { x: t.clientX, y: t.clientY }
    },
    onTouchEnd: (e: TouchEvent) => {
      const s = start.current
      start.current = null
      const t = e.changedTouches[0]
      if (!s || !t) return
      const dx = t.clientX - s.x
      const dy = t.clientY - s.y
      if (Math.abs(dx) > 60 && Math.abs(dx) > 1.6 * Math.abs(dy)) {
        onStep(dx < 0 ? 1 : -1)
      }
    },
  }
}
