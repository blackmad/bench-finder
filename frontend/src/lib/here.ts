import { useSyncExternalStore } from "react"
import { metresBetween } from "./nearZoom"

/** Where the visitor is, once they have shared it ([lng, lat]); else null. */
let here: [number, number] | null = null
const subs = new Set<() => void>()

export function setHere(p: [number, number]) {
  here = p
  for (const f of subs) f()
}

export function useHere(): [number, number] | null {
  return useSyncExternalStore(
    (f) => {
      subs.add(f)
      return () => subs.delete(f)
    },
    () => here
  )
}

/** "350 m away", "1.2 km away". */
export function awayText(from: [number, number], lat: number, lng: number) {
  const m = metresBetween(from, [lng, lat])
  if (m < 1000) return `${Math.max(10, Math.round(m / 10) * 10)} m away`
  return `${(m / 1000).toFixed(m < 10_000 ? 1 : 0)} km away`
}
