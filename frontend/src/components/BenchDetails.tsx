import { useState } from "react"
import { seatText } from "../data/describe"
import { facingKind, looksAt, windName } from "../data/facing"
import type { BenchDetail } from "../data/types"
import "../styles/details.css"

const capital = (s: string) => s.replace(/^\w/, (c) => c.toUpperCase())

function facingSource(b: BenchDetail): string {
  if (b.facing_method === "water_edge") return "estimated: turned to the water"
  if (b.facing_method === "water_back") {
    return "estimated: back to the water, checked in the photos"
  }
  if (facingKind(b) === "estimated") {
    return `estimated from street views, ${Math.round((b.facing_confidence ?? 0) * 100)}%`
  }
  return b.facing_method === "human"
    ? "confirmed by a visitor"
    : "mapped in OpenStreetMap"
}

export function Facts({
  bench: b,
  photographed,
}: {
  bench: BenchDetail
  photographed: string | null
}) {
  const kind = facingKind(b)
  const seat = seatText(b.backrest)
  const looks = looksAt(b.faces_category)
  const build = [seat, b.material ? capital(b.material) : null]
    .filter(Boolean)
    .join(" · ")
  return (
    <dl className="facts">
      {looks || b.faces_text ? (
        <>
          <dt className="caps">Looks at</dt>
          <dd>
            {looks ?? capital(b.faces_text as string)}
            {looks && b.faces_text ? <small> · {b.faces_text}</small> : null}
          </dd>
        </>
      ) : null}
      <dt className="caps">Faces</dt>
      <dd>
        {kind && b.facing !== null ? (
          <>
            <span className="num">
              {kind === "estimated" ? "≈ " : ""}
              {windName(b.facing)} {Math.round(b.facing)}°
            </span>{" "}
            <small>· {facingSource(b)}</small>
          </>
        ) : (
          "Not known yet"
        )}
      </dd>
      {build ? (
        <>
          <dt className="caps">Bench</dt>
          <dd>{build}</dd>
        </>
      ) : null}
      {photographed ? (
        <>
          <dt className="caps">Photo</dt>
          <dd>{photographed}</dd>
        </>
      ) : null}
    </dl>
  )
}

const EMBED_KEY = import.meta.env.VITE_GOOGLE_MAPS_EMBED_KEY as
  | string
  | undefined

/**
 * Street View from the best nearby panorama, opened looking at the bench.
 * The iframe only loads on request, so the page stays light; without an Embed API
 * key it links out to Google Maps instead.
 */
export function ViewFromBench({
  pano,
  heading,
  facing,
  street,
}: {
  pano: string
  /** Bearing from the panorama toward the bench. */
  heading: number
  facing: number | null
  street: string
}) {
  const [open, setOpen] = useState(false)
  const h = Math.round(heading)
  const outUrl = `https://www.google.com/maps/@?api=1&map_action=pano&pano=${encodeURIComponent(pano)}&heading=${h}&pitch=0&fov=80`
  return (
    <section className="dblock" aria-labelledby="h-view" id="look">
      <div className="blockhead">
        <h2 id="h-view">This spot in Street View</h2>
        <p>
          Opens looking {windName(h)} at the bench
          {facing === null
            ? ""
            : `; turn ${windName(facing)} to see what it faces`}
        </p>
      </div>
      {!EMBED_KEY ? (
        <p className="embedlink">
          <a href={outUrl} target="_blank" rel="noreferrer">
            Open this view in Google Maps
          </a>
        </p>
      ) : open ? (
        <iframe
          className="embed"
          title={`Street View from the bench on ${street}`}
          src={`https://www.google.com/maps/embed/v1/streetview?key=${EMBED_KEY}&pano=${encodeURIComponent(pano)}&heading=${h}&pitch=0&fov=80`}
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          allowFullScreen
        />
      ) : (
        <div className="embed placeholder">
          <button type="button" className="btn" onClick={() => setOpen(true)}>
            Look around from here
          </button>
        </div>
      )}
    </section>
  )
}
