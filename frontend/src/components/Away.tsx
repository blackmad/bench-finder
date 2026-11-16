import { awayText, useHere } from "../lib/here"

/** "350 m away" over a photo, once the visitor has shared where they are. */
export function Away({ lat, lng }: { lat: number; lng: number }) {
  const here = useHere()
  if (!here) return null
  return <span className="away">{awayText(here, lat, lng)}</span>
}
